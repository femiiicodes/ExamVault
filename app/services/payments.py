import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AcademicPeriod, Entitlement, Payment, User


PAYSTACK_API = 'https://api.paystack.co'
PAYMENT_AMOUNT = 300000
PAYMENT_CURRENCY = 'NGN'
logger = logging.getLogger(__name__)


def paystack_secret_key() -> str:
    value = os.getenv('PAYSTACK_SECRET_KEY', '').strip()
    if not value:
        raise HTTPException(status_code=503, detail='Payment service is not configured.')
    return value


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    secret = os.getenv('PAYSTACK_WEBHOOK_SECRET')
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, signature)


def active_period(db: Session) -> AcademicPeriod:
    period = db.query(AcademicPeriod).filter(AcademicPeriod.is_active.is_(True)).first()
    if period is None:
        raise HTTPException(status_code=503, detail='No active academic period has been configured.')
    return period


async def initialize_payment(
    db: Session,
    user: User,
    callback_url: str | None = None,
) -> dict:
    period = active_period(db)
    entitlement = db.query(Entitlement).filter(
        Entitlement.user_id == user.id,
        Entitlement.academic_period_id == period.id,
        Entitlement.status == 'active',
    ).first()
    if entitlement:
        return {'already_paid': True, 'academic_period_id': period.id}

    pending = db.query(Payment).filter(
        Payment.user_id == user.id,
        Payment.academic_period_id == period.id,
        Payment.status == 'pending',
        Payment.authorization_url.is_not(None),
    ).order_by(Payment.created_at.desc()).first()
    if pending:
        return {
            'already_paid': False,
            'reference': pending.reference,
            'authorization_url': pending.authorization_url,
            'academic_period_id': period.id,
        }

    reference = f'examvault-{user.id}-{secrets.token_urlsafe(18)}'
    payment = Payment(
        user_id=user.id,
        academic_period_id=period.id,
        reference=reference,
        amount=PAYMENT_AMOUNT,
        currency=PAYMENT_CURRENCY,
        status='pending',
        created_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    db.commit()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f'{PAYSTACK_API}/transaction/initialize',
                headers={'Authorization': f'Bearer {paystack_secret_key()}'},
                json={
                    'email': user.email,
                    'amount': PAYMENT_AMOUNT,
                    'currency': PAYMENT_CURRENCY,
                    'reference': reference,
                    'callback_url': callback_url or os.getenv('PAYSTACK_CALLBACK_URL'),
                    'metadata': {'user_id': user.id, 'academic_period_id': period.id},
                },
            )
        response.raise_for_status()
        data = response.json().get('data') or {}
        payment.authorization_url = data.get('authorization_url')
        db.commit()
        if not payment.authorization_url:
            raise HTTPException(status_code=502, detail='Paystack returned no authorization URL.')
        return {
            'already_paid': False,
            'reference': reference,
            'authorization_url': payment.authorization_url,
            'academic_period_id': period.id,
        }
    except HTTPException:
        payment.status = 'failed'
        db.commit()
        raise
    except httpx.HTTPStatusError as error:
        message = None
        try:
            message = response.json().get('message')
        except ValueError:
            pass
        logger.error(
            'Paystack initialization failed: status=%s message=%s',
            error.response.status_code,
            message or 'unparseable response',
        )
        payment.status = 'failed'
        db.commit()
        raise HTTPException(status_code=502, detail='Unable to initialize payment.') from error
    except httpx.RequestError as error:
        logger.error('Paystack initialization request failed: %s', error)
        payment.status = 'failed'
        db.commit()
        raise HTTPException(status_code=502, detail='Unable to initialize payment.') from error
    except ValueError as error:
        logger.error('Paystack initialization returned invalid JSON: %s', error)
        payment.status = 'failed'
        db.commit()
        raise HTTPException(status_code=502, detail='Unable to initialize payment.') from error


def fulfill_payment(
    db: Session,
    reference: str,
    *,
    paystack_status: str,
    amount: int,
    currency: str,
    transaction_id: str | None = None,
) -> Payment:
    payment = db.query(Payment).filter(Payment.reference == reference).with_for_update().first()
    if payment is None:
        raise HTTPException(status_code=404, detail='Payment reference not found.')
    if payment.status == 'successful':
        return payment
    if paystack_status != 'success' or amount != PAYMENT_AMOUNT or currency != PAYMENT_CURRENCY:
        payment.status = 'failed'
        db.commit()
        raise HTTPException(status_code=400, detail='Payment verification failed.')

    payment.status = 'successful'
    payment.paystack_transaction_id = transaction_id
    payment.paid_at = datetime.now(timezone.utc)
    try:
        db.flush()
        existing = db.query(Entitlement).filter(
            Entitlement.user_id == payment.user_id,
            Entitlement.academic_period_id == payment.academic_period_id,
        ).first()
        if existing is None:
            db.add(Entitlement(
                user_id=payment.user_id,
                academic_period_id=payment.academic_period_id,
                payment_id=payment.id,
                status='active',
                created_at=datetime.now(timezone.utc),
            ))
        db.commit()
        return payment
    except IntegrityError:
        db.rollback()
        payment = db.query(Payment).filter(Payment.reference == reference).first()
        if payment and payment.status == 'successful':
            return payment
        raise HTTPException(status_code=409, detail='Payment fulfillment conflicted; retry safely.')
