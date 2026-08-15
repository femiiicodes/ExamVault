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

class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    level: str | None = None
    department: str | None = None
    role: str | None = None

@router.get('/show-user-details',response_model=UserResponse)
async def get_user_details(user:user_dependency):
    return user

@router.patch('/', status_code=204)
async def edit_user_details(
    db: db_dependency,
    user: user_dependency,
    data:UserUpdate
):
    if user is None:
        raise HTTPException(status_code=401, detail="User not authenticated")


    if data.first_name is not None:
        user.first_name = data.first_name

    if data.last_name is not None:
        user.last_name = data.last_name

    if data.email is not None:
        user.email = data.email

    if data.level is not None:
        user.level = data.level

    if data.department is not None:
        user.department = data.department

    if data.role is not None:
        user.role = data.role

    db.commit()

@router.put('/change-password',status_code=204)
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

@router.delete('/delete-user', status_code=204)
async def delete_user(db:db_dependency,
                      user:user_dependency,
                      id:int):
    if user is None:
        raise HTTPException(status_code=401, detail="User not authenticated")
    user_model = db.query(User).filter(User.id == id).first()
    if user_model is None:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user_model)
    # Database cascade will set pqs.uploader_id to NULL for all PQs uploaded by this user
    db.commit()