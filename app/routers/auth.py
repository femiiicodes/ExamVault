from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette import status
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.models import AuthSession, Programme, SecurityAnswer, User


router = APIRouter(tags=['auth'], prefix='/auth')
templates = Jinja2Templates(directory='templates')
db_dependency = Annotated[Session, Depends(get_db)]

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
    security_answers: list[dict[str, str]] = Field(default_factory=list, max_length=2)

    @model_validator(mode='after')
    def validate_security_answers(self):
        if len(self.security_answers) not in (0, 2):
            raise ValueError('Provide exactly two security answers or skip this step')
        question_ids = [item.get('question_id') for item in self.security_answers]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError('Security questions must be different')
        for item in self.security_answers:
            if item.get('question_id') not in SECURITY_QUESTIONS or not normalize_answer(item.get('answer', '')):
                raise ValueError('Both security questions and answers are required')
        return self


class RefreshRequest(BaseModel):
    remember_me: bool | None = None


@router.get('/register-page')
async def render_register_page(request: Request):
    return templates.TemplateResponse(request=request, name='register-page.html')


@router.get('/login-page')
async def render_login_page(request: Request):
    return templates.TemplateResponse(request=request, name='login-page.html')


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
    credential_exception = HTTPException(status_code=401, detail='Unable to validate credentials')
    token = token or request.cookies.get(SESSION_COOKIE)
    if token is None:
        if 'text/html' in request.headers.get('accept', ''):
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
