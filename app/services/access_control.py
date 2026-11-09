from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AcademicPeriod, DailyPqView, Entitlement, Pq, User


LAGOS = ZoneInfo('Africa/Lagos')
DAILY_FREE_VIEW_LIMIT = 5


def current_lagos_date() -> str:
    return datetime.now(LAGOS).date().isoformat()


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
        existing = db.query(DailyPqView).filter(
            DailyPqView.user_id == locked_user.id,
            DailyPqView.past_question_id == pq.id,
            DailyPqView.view_date == today,
        ).first()
        if existing is not None:
            db.commit()
            return

        if free_views_remaining(db, locked_user) <= 0:
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
