from datetime import datetime
import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import AcademicPeriod, DailyPqView, Entitlement, Pq, User


LAGOS = ZoneInfo('Africa/Lagos')
DAILY_FREE_VIEW_LIMIT = 2
VIEW_GRANT_COOKIE = 'examvault_pdf_view_grant'
VIEW_GRANT_TTL_SECONDS = 15
_VIEW_GRANT_SECRET = (
    os.getenv('PDF_VIEW_GRANT_SECRET')
    or os.getenv('JWT_SECRET_KEY')
    or secrets.token_urlsafe(32)
).encode('utf-8')


def current_lagos_date() -> str:
    return datetime.now(LAGOS).date().isoformat()


def create_view_grant(user: User, pq: Pq, file_size: int) -> str:
    payload = {
        'exp': int(time.time()) + VIEW_GRANT_TTL_SECONDS,
        'date': current_lagos_date(),
        'file_size': file_size,
        'pq_id': pq.id,
        'role': user.role,
        'user_id': user.id,
    }
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    ).rstrip(b'=')
    signature = hmac.new(
        _VIEW_GRANT_SECRET,
        encoded_payload,
        hashlib.sha256,
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b'=')
    return f'{encoded_payload.decode()}.{encoded_signature.decode()}'


def get_valid_view_grant(
    grant: str | None,
    user: User,
    pq: Pq,
) -> dict | None:
    if not grant or grant.count('.') != 1:
        return None

    encoded_payload, encoded_signature = grant.split('.', 1)
    try:
        encoded_payload_bytes = encoded_payload.encode('ascii')
        padding = '=' * (-len(encoded_payload) % 4)
        payload_bytes = base64.urlsafe_b64decode(encoded_payload + padding)
        signature = base64.urlsafe_b64decode(
            encoded_signature + '=' * (-len(encoded_signature) % 4)
        )
        payload = json.loads(payload_bytes)
    except (UnicodeError, ValueError, TypeError, binascii.Error, json.JSONDecodeError):
        return None

    expected_signature = hmac.new(
        _VIEW_GRANT_SECRET,
        encoded_payload_bytes,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    if not (
        isinstance(payload, dict)
        and payload.get('exp', 0) >= int(time.time())
        and payload.get('date') == current_lagos_date()
        and payload.get('pq_id') == pq.id
        and payload.get('role') == user.role
        and payload.get('user_id') == user.id
        and isinstance(payload.get('file_size'), int)
        and payload.get('file_size') >= 0
    ):
        return None
    return payload


def has_valid_view_grant(grant: str | None, user: User, pq: Pq) -> bool:
    return get_valid_view_grant(grant, user, pq) is not None


def get_active_period(db: Session) -> AcademicPeriod:
    period = db.query(AcademicPeriod).filter(AcademicPeriod.is_active.is_(True)).first()
    if period is None:
        raise HTTPException(
            status_code=503,
            detail='No active academic period has been configured.',
        )
    return period


def has_current_entitlement(db: Session, user: User, period_id: int) -> bool:
    return db.query(Entitlement).filter(
        Entitlement.user_id == user.id,
        Entitlement.academic_period_id == period_id,
        Entitlement.status == 'active',
    ).first() is not None


def free_views_remaining(db: Session, user: User) -> int:
    viewed = db.query(func.count(DailyPqView.id)).filter(
        DailyPqView.user_id == user.id,
        DailyPqView.view_date == current_lagos_date(),
    ).scalar() or 0
    return max(DAILY_FREE_VIEW_LIMIT - int(viewed), 0)


def preauthorize_view(db: Session, user: User, pq: Pq) -> None:
    if user.role == 'admin':
        return
    period = get_active_period(db)
    if has_current_entitlement(db, user, period.id):
        return
    today = current_lagos_date()
    existing = db.query(DailyPqView).filter(
        DailyPqView.user_id == user.id,
        DailyPqView.past_question_id == pq.id,
        DailyPqView.view_date == today,
    ).first()
    if existing is None and free_views_remaining(db, user) <= 0:
        raise HTTPException(
            status_code=402,
            detail={
                'code': 'daily_view_limit_reached',
                'message': 'Daily free-view limit reached.',
                'academic_period_id': period.id,
                'academic_session': period.academic_session,
                'semester': period.semester,
            },
        )


def finalize_view_authorization(db: Session, user: User, pq: Pq) -> None:
    if user.role == 'admin':
        return

    db.rollback()
    try:
        locked_user = db.query(User).filter(User.id == user.id).with_for_update().one()
        period = get_active_period(db)
        if has_current_entitlement(db, locked_user, period.id):
            db.commit()
            return

        today = current_lagos_date()
        viewed_count, existing_count = db.query(
            func.count(DailyPqView.id),
            func.sum(
                case(
                    (DailyPqView.past_question_id == pq.id, 1),
                    else_=0,
                )
            ),
        ).filter(
            DailyPqView.user_id == locked_user.id,
            DailyPqView.view_date == today,
        ).one()
        if existing_count:
            db.commit()
            return

        if DAILY_FREE_VIEW_LIMIT - int(viewed_count or 0) <= 0:
            db.rollback()
            raise HTTPException(
                status_code=402,
                detail={
                    'code': 'daily_view_limit_reached',
                    'message': 'Daily free-view limit reached.',
                    'academic_period_id': period.id,
                    'academic_session': period.academic_session,
                    'semester': period.semester,
                },
            )

        db.add(DailyPqView(
            user_id=locked_user.id,
            past_question_id=pq.id,
            view_date=today,
            viewed_at=datetime.utcnow(),
        ))
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


def require_download_access(db: Session, user: User) -> AcademicPeriod:
    if user.role == 'admin':
        return db.query(AcademicPeriod).filter(AcademicPeriod.is_active.is_(True)).first()
    period = get_active_period(db)
    if not has_current_entitlement(db, user, period.id):
        raise HTTPException(
            status_code=402,
            detail={
                'code': 'payment_required',
                'message': 'A current academic-period entitlement is required to download PDFs.',
                'academic_period_id': period.id,
                'academic_session': period.academic_session,
                'semester': period.semester,
            },
        )
    return period
