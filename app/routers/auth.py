from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.database import get_db
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Form, Request
from sqlalchemy.orm import Session
from app.models import User
from pydantic import BaseModel
from datetime import datetime,timedelta, timezone
from starlette import status
from fastapi.templating import Jinja2Templates
import os


router = APIRouter(tags=['auth'],prefix='/auth')
templates = Jinja2Templates(directory='templates')

db_dependency = Annotated[Session,Depends(get_db)]

pwd_context = CryptContext(schemes=['bcrypt'],deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/token', auto_error=False)

ALGORITHM = 'HS256'
SECRET_KEY = 'GY8WTFG7FG34F348GVG73FTTGFH8476'
TOKEN_EXPIRES_MINUTES = 30

def check_password(plain_password:str,hashed_password:str):
    is_verified = pwd_context.verify(plain_password,hashed_password)
    if not is_verified:
        return None
    return True

def get_user(db:db_dependency,email:str):
    return db.query(User).filter(User.email==email).first()
    
def authenticate_user(db:db_dependency,email:str,password:str):
    user = get_user(db,email)
    if user is None:
        return None
    authenticated = check_password(password,user.hashed_password)
    if authenticated is None:
        return None
    return user

def create_access_token(data:dict,expires_delta:timedelta):
    to_encode = data.copy()
    if expires_delta:
        exp = datetime.now(timezone.utc) + expires_delta
    else:
        exp = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({'exp':exp})
    encoded_jwt = jwt.encode(to_encode,key=SECRET_KEY,algorithm=ALGORITHM)
    return encoded_jwt

def hash_password(password:str):
    return pwd_context.hash(password)
    
class UserResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    level: str
    role: str

class Token(BaseModel):
    access_token:str
    token_type:str

class UserRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    level: str
    programme_id: int
    role: str
    password: str
    admin_token: str | None = None



### PAGES ###
@router.get('/register-page')
async def render_resgister_page(request:Request):
    return templates.TemplateResponse(request=request,name='register-page.html')

@router.get('/login-page')
async def render_resgister_page(request:Request):
    return templates.TemplateResponse(request=request,name='login-page.html')


@router.post('/token')
async def login_for_access_token(request:Request, db:db_dependency,form_data= Depends(OAuth2PasswordRequestForm),admin: str | None = Form(None)):
    user = authenticate_user(db,form_data.username,form_data.password)
    if user is None:
        raise HTTPException(status_code=401,detail='Incorrect Email or Password')

    is_admin_toggle = admin == 'true'
    user_is_admin = user.role == 'admin'

    if is_admin_toggle and not user_is_admin:
        raise HTTPException(status_code=403,detail='You do not have admin privileges')

    access_token = create_access_token({'sub':user.email},expires_delta=timedelta(minutes=30))
    response = JSONResponse(content={
        'detail':'Login successful',
        'access_token': access_token,
        'token_type': 'bearer',
        'is_admin': user_is_admin
    })
    response.set_cookie(
        key='access_token',
        value=access_token,
        httponly=True,
        samesite='lax',
        max_age=2592000,
        secure=request.url.scheme == 'https'
    )
    return response



async def get_current_user(request:Request, db:db_dependency,token = Depends(oauth2_scheme)):
    credential_exception = HTTPException(status_code=401,detail='Unable to validate credentials')
    token = token or request.cookies.get('access_token')
    if token is None:
        raise credential_exception

    try:
        payload = jwt.decode(token,key=SECRET_KEY,algorithms=[ALGORITHM])
        email: str = payload.get('sub')
        if email is None:
            raise credential_exception

    except JWTError:
        raise credential_exception
    user = get_user(db,email)
    if not user:
        raise credential_exception

    return user

@router.post('/logout')
async def logout():
    """Clear the auth cookie to log out the user"""
    response = JSONResponse(content={'detail': 'Logged out successfully'})
    response.delete_cookie(
        key='access_token',
        samesite='lax',
        secure=False
    )
    return response

@router.post('/register',status_code=status.HTTP_201_CREATED)
async def add_user(db:db_dependency,new_user:UserRequest):
    if new_user.admin_token != os.getenv('ADMIN_KEY'):
        raise HTTPException(status_code=403, detail='Invalid admin token')

    new_user_obj = User(first_name=new_user.first_name,
                        last_name=new_user.last_name,
                        email=new_user.email,
                        level=new_user.level,
                        programme_id=new_user.programme_id,
                        role=new_user.role,
                        hashed_password=hash_password(new_user.password))

    db.add(new_user_obj)
    db.commit()






        
        



