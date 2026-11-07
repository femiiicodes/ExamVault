import json
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AcademicPeriod, AcademicPeriodSwitch, Entitlement, Payment, User
from app.routers.auth import check_password, get_current_user
from app.services.access_control import free_views_remaining
from app.services.payments import (
    PAYMENT_AMOUNT,
    PAYMENT_CURRENCY,
    PAYSTACK_API,
    active_period,
    fulfill_payment,
    initialize_payment,
    paystack_secret_key,
    verify_webhook_signature,
)


router = APIRouter(tags=['payments'])


class PaymentInitResponse(BaseModel):
    already_paid: bool
    academic_period_id: int
    reference: str | None = None
    authorization_url: str | None = None


class AcademicPeriodRequest(BaseModel):
    academic_session: str = Field(min_length=4, max_length=20)
    semester: str = Field(pattern=r'^(First Semester|Second Semester)$')


class SwitchPeriodRequest(AcademicPeriodRequest):
    password: str = Field(min_length=1)
    confirmation: bool


def admin_only(user: User) -> None:
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail='Administrator access required.')


@router.get('/access/status')
def access_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == 'admin':
        return {
            'is_admin': True,
            'academic_period_id': None,
            'academic_session': None,
            'semester': None,
            'has_access': True,
            'remaining_free_views': None,
        }
    period = active_period(db)
    entitled = db.query(Entitlement).filter(
        Entitlement.user_id == user.id,
        Entitlement.academic_period_id == period.id,
        Entitlement.status == 'active',
    ).first() is not None
    return {
        'is_admin': user.role == 'admin',
        'academic_period_id': period.id,
        'academic_session': period.academic_session,
        'semester': period.semester,
        'has_access': user.role == 'admin' or entitled,
        'remaining_free_views': None if user.role == 'admin' or entitled else free_views_remaining(db, user),
    }


@router.post('/payments/initialize', response_model=PaymentInitResponse)
async def payment_initialize(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == 'admin':
        raise HTTPException(status_code=403, detail='Administrators do not make payments.')
    callback_url = f'{str(request.base_url).rstrip("/")}/dashboard'
    return await initialize_payment(db, user, callback_url=callback_url)


@router.get('/payments/verify/{reference}')
async def payment_verify(reference: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payment = db.query(Payment).filter(
        Payment.reference == reference,
        Payment.user_id == user.id,
    ).first()
    if payment is None:
        raise HTTPException(status_code=404, detail='Payment reference not found.')
    if payment.status == 'successful':
        return {'status': 'success', 'academic_period_id': payment.academic_period_id}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f'{PAYSTACK_API}/transaction/verify/{reference}',
                headers={'Authorization': f'Bearer {paystack_secret_key()}'},
            )
        response.raise_for_status()
        data = response.json().get('data') or {}
        fulfilled = fulfill_payment(
            db,
            reference,
            paystack_status=data.get('status'),
            amount=data.get('amount'),
            currency=data.get('currency'),
            transaction_id=str(data.get('id')) if data.get('id') is not None else None,
        )
        return {'status': fulfilled.status, 'academic_period_id': fulfilled.academic_period_id}
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail='Unable to verify payment.') from error


@router.post('/webhooks/paystack')
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    if not verify_webhook_signature(raw_body, request.headers.get('Paystack-Signature')):
        raise HTTPException(status_code=400, detail='Invalid webhook signature.')
    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail='Invalid webhook payload.') from error
    if event.get('event') != 'charge.success':
        return {'status': 'acknowledged'}
    data = event.get('data') or {}
    fulfill_payment(
        db,
        data.get('reference', ''),
        paystack_status=data.get('status'),
        amount=data.get('amount'),
        currency=data.get('currency'),
        transaction_id=str(data.get('id')) if data.get('id') is not None else None,
    )
    return {'status': 'acknowledged'}


@router.get('/admin/academic-periods')
def list_periods(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    admin_only(user)
    periods = db.query(AcademicPeriod).order_by(AcademicPeriod.created_at.desc()).all()
    return [{
        'id': period.id,
        'academic_session': period.academic_session,
        'semester': period.semester,
        'is_active': period.is_active,
    } for period in periods]


@router.post('/admin/academic-periods')
def create_period(payload: AcademicPeriodRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    admin_only(user)
    existing = db.query(AcademicPeriod).filter(
        AcademicPeriod.academic_session == payload.academic_session,
        AcademicPeriod.semester == payload.semester,
    ).first()
    if existing:
        return {'id': existing.id, 'is_active': existing.is_active}
    period = AcademicPeriod(
        academic_session=payload.academic_session,
        semester=payload.semester,
        is_active=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return {'id': period.id, 'is_active': False}


@router.post('/admin/academic-periods/switch')
def switch_period(payload: SwitchPeriodRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    admin_only(user)
    if not payload.confirmation:
        raise HTTPException(status_code=400, detail='Explicit confirmation is required.')
    if not check_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=403, detail='Password confirmation failed.')
    target = db.query(AcademicPeriod).filter(
        AcademicPeriod.academic_session == payload.academic_session,
        AcademicPeriod.semester == payload.semester,
    ).with_for_update().first()
    if target is None:
        raise HTTPException(status_code=404, detail='Academic period not found.')
    current = db.query(AcademicPeriod).filter(AcademicPeriod.is_active.is_(True)).with_for_update().first()
    if current and current.id == target.id:
        return {'id': target.id, 'is_active': True}
    try:
        if current:
            current.is_active = False
        target.is_active = True
        db.add(AcademicPeriodSwitch(
            previous_period_id=current.id if current else None,
            new_period_id=target.id,
            admin_user_id=user.id,
            switched_at=datetime.now(timezone.utc),
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'id': target.id, 'is_active': True}
