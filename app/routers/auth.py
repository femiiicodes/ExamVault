import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
import secrets
import time
from threading import Lock
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, update
from sqlalchemy.orm import Session
from starlette import status
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.models import AuthSession, PasswordResetToken, Programme, SecurityAnswer, User
from app.services.email_service import EmailDeliveryError, send_password_reset_email


router = APIRouter(tags=['auth'], prefix='/auth')
templates = Jinja2Templates(directory='templates')
db_dependency = Annotated[Session, Depends(get_db)]
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/token', auto_error=False)

ALGORITHM = 'HS256'
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    if os.getenv('ENVIRONMENT', '').lower() == 'production':
        raise RuntimeError('JWT_SECRET_KEY must be configured in production')
    JWT_SECRET_KEY = secrets.token_urlsafe(32)

ACCESS_TOKEN_MINUTES = 15
SESSION_COOKIE = 'access_token'
REFRESH_COOKIE = 'refresh_token'
REFRESH_TOKEN_DAYS = 30
PERSISTENT_COOKIE_DAYS = 3650
SECURITY_QUESTIONS = {
    'q1': "What is your mother's first name?",
    'q2': 'What state were you born in?',
    'q3': 'What was your first school?',
    'q4': 'What year were you born?',
    'q5': 'What is your best sport?',
}
PASSWORD_RESET_MINUTES = 30
RATE_LIMIT_WINDOW_SECONDS = 15 * 60
RATE_LIMIT_MAX_ATTEMPTS = 5
_recovery_attempts: dict[str, list[float]] = {}
_recovery_attempts_lock = Lock()


def check_password(plain_password: str, hashed_password: str):
    return True if pwd_context.verify(plain_password, hashed_password) else None


def hash_password(password: str):
    return pwd_context.hash(password)


def normalize_answer(answer: str) -> str:
    return ' '.join(answer.strip().casefold().split())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def get_user(db: db_dependency, email: str):
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: db_dependency, email: str, password: str):
    user = get_user(db, email)
    if user is None or check_password(password, user.hashed_password) is None:
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta):
    payload = data.copy()
    payload['exp'] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, key=JWT_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_session(db: Session, user: User, persistent: bool) -> str:
    raw_token = secrets.token_urlsafe(48)
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        created_at=datetime.now(timezone.utc),
        expires_at=(
            datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS)
            if not persistent else None
        ),
        is_persistent=persistent,
    )
    db.add(session)
    db.commit()
    return raw_token


def set_auth_cookies(response, access_token: str, refresh_token: str, persistent: bool, request: Request):
    secure = request.url.scheme == 'https'
    response.set_cookie(
        key=SESSION_COOKIE,
        value=access_token,
        httponly=True,
        samesite='lax',
        max_age=ACCESS_TOKEN_MINUTES * 60,
        secure=secure,
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        samesite='lax',
        max_age=(PERSISTENT_COOKIE_DAYS * 86400 if persistent else None),
        secure=secure,
    )


def revoke_session(db: Session, raw_token: str | None):
    if not raw_token:
        return
    session = db.query(AuthSession).filter(
        AuthSession.token_hash == hash_token(raw_token),
        AuthSession.revoked_at.is_(None),
    ).first()
    if session:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: str
    email: str
    level: str
    role: str


class UserRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    level: str = Field(pattern=r'^(100|200|300|400|500)$')
    programme_id: int
    password: str = Field(min_length=8, max_length=128)
    remember_me: bool = False
    security_answers: list[dict[str, str]] = Field(min_length=2, max_length=2)

    @model_validator(mode='after')
    def validate_security_answers(self):
        if len(self.security_answers) != 2:
            raise ValueError('Provide exactly two security answers')
        question_ids = [item.get('question_id') for item in self.security_answers]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError('Security questions must be different')
        for item in self.security_answers:
            if item.get('question_id') not in SECURITY_QUESTIONS or not normalize_answer(item.get('answer', '')):
                raise ValueError('Both security questions and answers are required')
        return self


class RefreshRequest(BaseModel):
    remember_me: bool | None = None


class RecoveryEmailRequest(BaseModel):
    email: EmailStr


class SecurityVerificationRequest(BaseModel):
    email: EmailStr
    answers: list[dict[str, str]] = Field(min_length=2, max_length=2)


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


def _recovery_is_rate_limited(request: Request, email: str) -> bool:
    now = datetime.now(timezone.utc).timestamp()
    client_key = request.client.host if request.client else 'unknown'
    keys = (f'ip:{client_key}', f'email:{email.casefold()}')
    with _recovery_attempts_lock:
        for key in keys:
            recent = [
                timestamp for timestamp in _recovery_attempts.get(key, [])
                if now - timestamp < RATE_LIMIT_WINDOW_SECONDS
            ]
            if len(recent) >= RATE_LIMIT_MAX_ATTEMPTS:
                _recovery_attempts[key] = recent
                return True
            recent.append(now)
            _recovery_attempts[key] = recent
    return False


GENERIC_RECOVERY_MESSAGE = 'If an account exists for this email, recovery instructions will be sent.'


def _create_recovery_token(db: Session, user: User) -> str:
    raw_token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({'used_at': now}, synchronize_session=False)
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=now + timedelta(minutes=PASSWORD_RESET_MINUTES),
        created_at=now,
    ))
    db.commit()
    return raw_token


async def _send_password_reset_email_for_user(db: Session, user: User) -> None:
    token = _create_recovery_token(db, user)
    base_url = os.getenv('APP_BASE_URL', '').rstrip('/')
    if not base_url:
        logger.error('Password reset email not sent because APP_BASE_URL is not configured')
        return

    reset_url = f'{base_url}/auth/reset-password-page?token={quote(token)}'
    try:
        await asyncio.to_thread(send_password_reset_email, user.email, reset_url)
    except EmailDeliveryError:
        logger.exception('Password reset email delivery failed for configured account')


@router.get('/register-page')
async def render_register_page(request: Request):
    return templates.TemplateResponse(request=request, name='register-page.html')


@router.get('/login-page')
async def render_login_page(request: Request):
    return templates.TemplateResponse(request=request, name='login-page.html')


@router.get('/forgot-password-page')
async def render_forgot_password_page(request: Request):
    return templates.TemplateResponse(request=request, name='forgot-password.html')


@router.get('/reset-password-page')
async def render_reset_password_page(request: Request):
    return templates.TemplateResponse(request=request, name='reset-password.html')


@router.get('/security-questions')
async def security_questions():
    return [{'id': key, 'text': value} for key, value in SECURITY_QUESTIONS.items()]


@router.get('/check-email')
async def check_email(email: str, db: db_dependency):
    normalized_email = email.strip().lower()
    if not normalized_email:
        return {'available': False}
    return {
        'available': db.query(User).filter(func.lower(User.email) == normalized_email).first() is None
    }


@router.post('/password-reset/request-email', status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset_email(
    request: Request,
    payload: RecoveryEmailRequest,
    db: db_dependency,
):
    email = str(payload.email).strip().lower()
    if _recovery_is_rate_limited(request, email):
        return {'detail': GENERIC_RECOVERY_MESSAGE}

    user = get_user(db, email)
    if user is None:
        return {'detail': GENERIC_RECOVERY_MESSAGE}

    await _send_password_reset_email_for_user(db, user)
    return {'detail': GENERIC_RECOVERY_MESSAGE}


@router.post('/password-recovery/start')
async def start_password_recovery(
    request: Request,
    payload: RecoveryEmailRequest,
    db: db_dependency,
):
    email = str(payload.email).strip().lower()
    if _recovery_is_rate_limited(request, email):
        return {'method': 'email', 'detail': GENERIC_RECOVERY_MESSAGE}

    user = get_user(db, email)
    configured_questions = [
        {'id': answer.question_id, 'text': SECURITY_QUESTIONS[answer.question_id]}
        for answer in (user.security_answers if user else [])
        if answer.question_id in SECURITY_QUESTIONS
    ]
    if len(configured_questions) == 2:
        return {'method': 'security_questions', 'questions': configured_questions}

    if user is not None:
        await _send_password_reset_email_for_user(db, user)
    return {'method': 'email', 'detail': GENERIC_RECOVERY_MESSAGE}


@router.post('/password-recovery/security-questions')
async def get_recovery_questions(
    request: Request,
    payload: RecoveryEmailRequest,
    db: db_dependency,
):
    email = str(payload.email).strip().lower()
    if _recovery_is_rate_limited(request, email):
        raise HTTPException(status_code=429, detail='Too many recovery attempts. Try again later.')
    user = get_user(db, email)
    if user is None:
        return {'questions': []}
    return {
        'questions': [
            {'id': answer.question_id, 'text': SECURITY_QUESTIONS[answer.question_id]}
            for answer in user.security_answers
            if answer.question_id in SECURITY_QUESTIONS
        ]
    }


@router.post('/password-recovery/security-verify')
async def verify_recovery_questions(
    request: Request,
    payload: SecurityVerificationRequest,
    db: db_dependency,
):
    email = str(payload.email).strip().lower()
    if _recovery_is_rate_limited(request, email):
        raise HTTPException(status_code=429, detail='Too many recovery attempts. Try again later.')
    user = get_user(db, email)
    answers = {item.get('question_id'): normalize_answer(item.get('answer', '')) for item in payload.answers}
    configured_answers = {answer.question_id: answer.answer_hash for answer in (user.security_answers if user else [])}
    valid = (
        user is not None
        and len(configured_answers) == 2
        and len(answers) == 2
        and set(answers) == set(configured_answers)
        and all(check_password(answers[question_id], configured_answers[question_id]) for question_id in answers)
    )
    if not valid:
        raise HTTPException(status_code=400, detail='The recovery answers could not be verified.')
    return {'token': _create_recovery_token(db, user)}


@router.post('/password-reset/confirm')
async def confirm_password_reset(payload: PasswordResetRequest, db: db_dependency):
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=422, detail='Passwords do not match.')

    now = datetime.now(timezone.utc)
    token_hash = hash_token(payload.token)
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
    ).first()
    expires_at = (
        reset_token.expires_at.replace(tzinfo=timezone.utc)
        if reset_token and reset_token.expires_at.tzinfo is None
        else reset_token.expires_at if reset_token else None
    )
    if reset_token is None or expires_at <= now:
        raise HTTPException(status_code=400, detail='This password reset link is invalid or has expired.')

    consumed = db.execute(update(PasswordResetToken).where(
        PasswordResetToken.id == reset_token.id,
        PasswordResetToken.used_at.is_(None),
    ).values(used_at=now).execution_options(synchronize_session=False))
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=400, detail='This password reset link is invalid or has expired.')

    user = reset_token.user
    user.hashed_password = hash_password(payload.password)
    db.query(AuthSession).filter(
        AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None),
    ).update({'revoked_at': now}, synchronize_session=False)
    db.commit()
    return {'detail': 'Password reset successfully. You can now log in.'}


@router.post('/token')
async def login_for_access_token(
    request: Request,
    db: db_dependency,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(status_code=401, detail='Incorrect Email or Password')

    is_admin_toggle = form_data.scopes and 'admin' in form_data.scopes
    user_is_admin = user.role == 'admin'
    if is_admin_toggle and not user_is_admin:
        raise HTTPException(status_code=403, detail='You do not have admin privileges')

    persistent = form_data.client_id == 'remember'
    access_token = create_access_token(
        {'sub': user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_MINUTES),
    )
    refresh_token = create_refresh_session(db, user, persistent)
    response = JSONResponse(content={
        'detail': 'Login successful',
        'access_token': access_token,
        'token_type': 'bearer',
        'is_admin': user_is_admin,
    })
    set_auth_cookies(response, access_token, refresh_token, persistent, request)
    return response


@router.post('/refresh')
async def refresh_access_token(request: Request, db: db_dependency):
    raw_token = request.cookies.get(REFRESH_COOKIE)
    if not raw_token:
        raise HTTPException(status_code=401, detail='Refresh session missing')

    session = db.query(AuthSession).filter(
        AuthSession.token_hash == hash_token(raw_token),
        AuthSession.revoked_at.is_(None),
    ).first()
    now = datetime.now(timezone.utc)
    if session is None or (session.expires_at and session.expires_at <= now):
        raise HTTPException(status_code=401, detail='Refresh session expired')

    session.revoked_at = now
    new_refresh = create_refresh_session(db, session.user, session.is_persistent)
    access_token = create_access_token(
        {'sub': session.user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_MINUTES),
    )
    response = JSONResponse(content={'access_token': access_token, 'token_type': 'bearer'})
    set_auth_cookies(response, access_token, new_refresh, session.is_persistent, request)
    return response


async def get_current_user(
    request: Request,
    db: db_dependency,
    token=Depends(oauth2_scheme),
):
    auth_started_at = time.perf_counter()
    credential_exception = HTTPException(status_code=401, detail='Unable to validate credentials')
    token = token or request.cookies.get(SESSION_COOKIE)
    if token is None:
        if 'text/html' in request.headers.get('accept', ''):
            request.state.auth_duration_ms = (time.perf_counter() - auth_started_at) * 1000
            return RedirectResponse(
                url=f'/auth/login-page?next={request.url.path}',
                status_code=303,
            )
        raise credential_exception

    try:
        payload = jwt.decode(token, key=JWT_SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get('sub')
        if email is None:
            raise credential_exception
    except JWTError:
        raise credential_exception

    user = get_user(db, email)
    if not user:
        raise credential_exception
    request.state.auth_duration_ms = (time.perf_counter() - auth_started_at) * 1000
    return user


@router.post('/logout')
async def logout(request: Request, db: db_dependency):
    revoke_session(db, request.cookies.get(REFRESH_COOKIE))
    response = JSONResponse(content={'detail': 'Logged out successfully'})
    response.delete_cookie(key=SESSION_COOKIE, samesite='lax', secure=request.url.scheme == 'https')
    response.delete_cookie(key=REFRESH_COOKIE, samesite='lax', secure=request.url.scheme == 'https')
    return response


@router.post('/register', status_code=status.HTTP_201_CREATED)
async def add_user(request: Request, db: db_dependency, new_user: UserRequest):
    if db.query(User).filter(func.lower(User.email) == str(new_user.email).lower()).first():
        raise HTTPException(status_code=409, detail='This email has already been used.')
    if db.query(Programme).filter(Programme.id == new_user.programme_id).first() is None:
        raise HTTPException(status_code=422, detail='Programme not found')

    new_user_obj = User(
        first_name=new_user.first_name.strip(),
        last_name=new_user.last_name.strip(),
        email=str(new_user.email).lower(),
        level=new_user.level,
        programme_id=new_user.programme_id,
        role='user',
        hashed_password=hash_password(new_user.password),
    )
    db.add(new_user_obj)
    try:
        db.flush()
        for answer in new_user.security_answers:
            db.add(SecurityAnswer(
                user_id=new_user_obj.id,
                question_id=answer['question_id'],
                answer_hash=hash_password(normalize_answer(answer['answer'])),
            ))
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail='Unable to create this account') from error
    access_token = create_access_token(
        {'sub': new_user_obj.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_MINUTES),
    )
    refresh_token = create_refresh_session(db, new_user_obj, new_user.remember_me)
    response = JSONResponse(
        content={'detail': 'Account created successfully', 'redirect': '/dashboard'},
        status_code=status.HTTP_201_CREATED,
    )
    set_auth_cookies(response, access_token, refresh_token, new_user.remember_me, request)
    return response
