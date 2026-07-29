from pydantic import BaseModel,ConfigDict

from app.models import User
from typing import Annotated
from fastapi import Depends
from app.routers.auth import get_current_user,check_password, hash_password
from fastapi import APIRouter,Form
from typing import Optional
from fastapi import HTTPException,status
from app.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix='/users',tags=['users'])
db_dependency = Annotated[Session,Depends(get_db)]

user_dependency = Annotated[User,Depends(get_current_user)]
class UserResponse(BaseModel):
    model_config= ConfigDict(from_attributes=True)
    id: int
    first_name:str
    last_name:str
    email:str
    level:str
    department:str
    role:str


@router.get('/show-user-details',response_model=UserResponse)
async def get_user_details(user:user_dependency):
    return user

@router.put('/', status_code=204)
async def edit_user_details(
    db: db_dependency,
    user: user_dependency,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    level: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
):
    if user is None:
        raise HTTPException(status_code=401, detail="User not authenticated")


    if first_name is not None:
        user.first_name = first_name

    if last_name is not None:
        user.last_name = last_name

    if email is not None:
        user.email = email

    if level is not None:
        user.level = level

    if department is not None:
        user.department = department

    if role is not None:
        user.role = role

    db.commit()

@router.put('/change-password')
async def change_password(
                          db:db_dependency,
                          user:user_dependency,
                          old_password:str,
                          new_password:str):

    if user is None:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    if check_password(old_password,user.hashed_password) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Old password incorrect')

    user.hashed_password = hash_password(new_password)
    db.commit()