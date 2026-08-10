from typing import Annotated, Optional
from app.database import get_db
from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field
import os
import shutil
from datetime import datetime
from app.models import Pq,User
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from fastapi import HTTPException
from app.routers.auth import get_current_user
from fastapi.templating import Jinja2Templates

template = Jinja2Templates(directory='templates')

router = APIRouter(tags=['pqs'],prefix='/pqs')

# @router.get('/')
db_dependency = Annotated[Session,Depends(get_db)]

user_dependency = Annotated[User,Depends(get_current_user)]


### PAGES ###


### ROUTES ###
class PastQuestion(BaseModel):
    session:str
    assessment_type:str
    department:str
    level:str
    # file_path: str
    # time_created:datetime


@router.get('/download_file',status_code=200)
async def get_pq_file(id:int, db:db_dependency,user:user_dependency):
    if user is None:
         raise HTTPException(status_code=401,detail='User not authenticated')
    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
            raise HTTPException(status_code=404,detail='Pq not found')
    return FileResponse(path= pq_model.file_path,
                        media_type='application/pdf',
                        filename=f'Pastquestion{id}.pdf')
    

@router.get('/pq_details',status_code=200)
def get_pq_details(id:int,db:db_dependency,user:user_dependency):
    if user is None:
         raise HTTPException(status_code=401,detail='User not authenticated')
    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
            raise HTTPException(status_code=404,detail='Pq not found')
    return pq_model

@router.put('/edit-pq',status_code=204)
def edit_pq_details(id:int,
                    db:db_dependency,
                    user:user_dependency,
                    course:Optional[str] = Form(None),
                    session:Optional[str] = Form(None),
                    assessment_type:Optional[str] = Form(None),
                    department:Optional[str] = Form(None),
                    level:Optional[str] = Form(None),

                    file:Optional[UploadFile] = File(None),):
    if user is None:
        raise HTTPException(status_code=401,detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401,detail='User not authorized')
    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
            raise HTTPException(status_code=404,detail='Pq not found')
    if course is not None:
        pq_model.session = session
    if assessment_type is not None:
        pq_model.assessment_type = assessment_type 
    if department is not None:
        pq_model.department = department
    if level is not None:
        pq_model.level = level
    

    UPLOAD_URL = 'uploads/past_questions'
    file_name = f"{course} {assessment_type} {session}.pdf"
    if file is not None:
         os.remove(pq_model.file_path)
         new_file_path = os.path.join(UPLOAD_URL,file_name)
         pq_model.file_path = new_file_path
         with open(new_file_path, 'wb') as buffer:
              shutil.copyfileobj(file.file,buffer)

    db.commit()
    new_pq_model = db.query(Pq).filter(Pq.id == id).first()
    return new_pq_model

@router.post('/upload',status_code=201)
async def upload_pq(
                    db:db_dependency,
                    user:user_dependency,
                    course:str = Form(...),
                    session:str = Form(...),
                    assessment_type:str = Form(...),
                    department:str = Form(...),
                    level:str = Form(...),

                    file:UploadFile = File(...)
                    ):
    if user is None:
        raise HTTPException(status_code=401,detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401,detail='User not authorized')
    UPLOAD_DIR = 'uploads/past_questions'
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_name = f"{course} {assessment_type} {session}.pdf"
    file_path = os.path.join(UPLOAD_DIR,file_name)
    with open(file_path,'wb') as buffer:
        shutil.copyfileobj(file.file,buffer)
    print(level)
    print(file_path)
    new_pq = Pq(course=course,session=session,assessment_type=assessment_type,department=department,level=level,file_path=file_path, time_created = datetime.now())
    db.add(new_pq)
    db.commit()

    return 'File pasted successfully'

@router.delete('/delete-pq',status_code=204)
async def delete_pq(db:db_dependency,
                    id:int,
                    user:user_dependency):
    if user is None:
        raise HTTPException(status_code=401,detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401,detail='User not authorized')
    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
        raise HTTPException(status_code=404,detail='Pq not found')
    db.delete(pq_model) 
    db.commit()
    os.remove(pq_model.file_path)

@router.get('/check')
async def check_file_name(id:int,
            db:db_dependency):
    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
        raise HTTPException(status_code=404,detail='Pq not found')  
    print(pq_model.file_path.split("\\")[-1])   

