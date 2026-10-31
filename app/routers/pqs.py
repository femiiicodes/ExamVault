from typing import Annotated, Optional
from app.database import get_db
from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.models import Course, ProgrammeCourse, Pq, User
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi import HTTPException
from app.routers.auth import get_current_user
from fastapi.templating import Jinja2Templates
from fastapi import Request
from botocore.exceptions import ClientError
from services.storage import upload_file, generate_download_url, get_file, get_file_metadata, delete_file


template = Jinja2Templates(directory='templates')

router = APIRouter(tags=['pqs'],prefix='/pqs')

# @router.get('/')
db_dependency = Annotated[Session,Depends(get_db)]

user_dependency = Annotated[User,Depends(get_current_user)]


### PAGES ###


### ROUTES ###
class PastQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session: str
    assessment_type: str
    level: str
    course_id: int
    course_code: str
    course_title: str
    uploader: str
    file_name: str
    time_created: datetime | None


def require_admin(user: User):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='User not authorized')


def resolve_course_level(db: Session, course_id: int) -> tuple[Course, str]:
    course = db.query(Course).filter(Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail='Course not found')

    levels = {
        assignment.level
        for assignment in db.query(ProgrammeCourse).filter(
            ProgrammeCourse.course_id == course_id
        ).all()
    }
    if not levels:
        raise HTTPException(status_code=400, detail='Course has no programme level assigned')
    if len(levels) != 1:
        raise HTTPException(status_code=400, detail='Course has conflicting programme levels')
    return course, str(levels.pop())


def serialize_pq(pq_model: Pq) -> PastQuestionResponse:
    uploader_name = 'Unknown uploader'
    if pq_model.uploader is not None:
        uploader_name = ' '.join(
            part for part in (pq_model.uploader.first_name, pq_model.uploader.last_name)
            if part
        ) or pq_model.uploader.email
    return PastQuestionResponse(
        id=pq_model.id,
        session=pq_model.session,
        assessment_type=pq_model.assessment_type,
        level=str(pq_model.level),
        course_id=pq_model.course_id,
        course_code=pq_model.course.code,
        course_title=pq_model.course.title,
        uploader=uploader_name,
        file_name=pq_model.file_name,
        time_created=pq_model.time_created,
    )


@router.get('', response_model=list[PastQuestionResponse], status_code=200)
def get_pqs(db: db_dependency, user: user_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')

    questions = db.query(Pq).order_by(Pq.time_created.desc()).all()
    return [serialize_pq(pq) for pq in questions]


@router.get('/download_file',status_code=307)
async def get_pq_file(
    id: int,
    db: db_dependency,
    user: user_dependency,
    download: bool = False,
):
    if user is None:
         raise HTTPException(status_code=401,detail='User not authenticated')
    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
        raise HTTPException(status_code=404,detail='Pq not found')
    if not pq_model.file_key:
        raise HTTPException(status_code=404,detail='Pq file not found')
    
    url = generate_download_url(
        pq_model.file_key,
        expires_in=3600
    )
    # Add disposition header to URL if download is requested
    if download:
        url += f"&response-content-disposition=attachment%3B%20filename%3D{pq_model.file_name}"
    return RedirectResponse(url=url, status_code=303)

@router.get('/view_file')
async def view_pq_file(
    request: Request,
    id: int,
    db: db_dependency,
    user: user_dependency,
):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')

    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
        raise HTTPException(status_code=404, detail='Pq not found')
    if not pq_model.file_key:
        raise HTTPException(status_code=404, detail='Pq file not found')

    try:
        metadata = get_file_metadata(pq_model.file_key)
        total_size = metadata['ContentLength']
        range_header = request.headers.get('range')
        response_status = 200
        response_headers = {
            'Accept-Ranges': 'bytes',
            'Content-Type': 'application/pdf',
            'Content-Length': str(total_size),
            'Content-Disposition': 'inline',
            'Cache-Control': 'private, no-store',
        }

        if range_header:
            if not range_header.startswith('bytes=') or ',' in range_header:
                raise HTTPException(status_code=416, detail='Invalid byte range')

            range_value = range_header[6:]
            start_text, separator, end_text = range_value.partition('-')
            if not separator:
                raise HTTPException(status_code=416, detail='Invalid byte range')

            try:
                if start_text:
                    start = int(start_text)
                    end = int(end_text) if end_text else total_size - 1
                else:
                    suffix_length = int(end_text)
            except ValueError as error:
                raise HTTPException(status_code=416, detail='Invalid byte range') from error

            if not start_text:
                start = max(total_size - suffix_length, 0)
                end = total_size - 1

            if start < 0 or start >= total_size or end < start:
                raise HTTPException(status_code=416, detail='Invalid byte range')
            end = min(end, total_size - 1)
            content_length = end - start + 1
            metadata = get_file(pq_model.file_key, f'bytes={start}-{end}')
            response_status = 206
            response_headers['Content-Length'] = str(content_length)
            response_headers['Content-Range'] = f'bytes {start}-{end}/{total_size}'
        else:
            metadata = get_file(pq_model.file_key)

        body = metadata['Body']

        def stream_body():
            try:
                yield from body.iter_chunks(chunk_size=1024 * 1024)
            finally:
                body.close()

        return StreamingResponse(
            stream_body(),
            status_code=response_status,
            headers=response_headers,
            media_type='application/pdf',
        )
    except HTTPException:
        raise
    except ClientError as error:
        raise HTTPException(status_code=404, detail='Pq file not found') from error


@router.get('/pq_details',status_code=200)
def get_pq_details(id:int,db:db_dependency,user:user_dependency):
    if user is None:
         raise HTTPException(status_code=401,detail='User not authenticated')
    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
            raise HTTPException(status_code=404,detail='Pq not found')
    return serialize_pq(pq_model)

@router.patch('/edit-pq',status_code=204)
def edit_pq_details(id:int,
                    db:db_dependency,
                    user:user_dependency,
                    course_id:Optional[int] = Form(None),
                    session:Optional[str] = Form(None),
                    assessment_type:Optional[str] = Form(None),
                    file:Optional[UploadFile] = File(None),):
    require_admin(user)
    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
            raise HTTPException(status_code=404,detail='Pq not found')
    if course_id is not None:
        course, level = resolve_course_level(db, course_id)
        pq_model.course = course
        pq_model.level = level
    if session is not None:
        pq_model.session = session
    if assessment_type is not None:
        pq_model.assessment_type = assessment_type 
    if file is not None:
        file_name = (
            f"{pq_model.course.code} {pq_model.assessment_type} "
            f"{pq_model.session}.pdf"
        )
        # Delete old file from R2 if it exists
        if pq_model.file_key:
            delete_file(pq_model.file_key)
        
        # Upload new file to R2
        object_key = f"past-questions/{pq_model.id}.pdf"
        upload_file(
            file.file,
            object_key,
            "application/pdf"
        )
        pq_model.file_name = file_name
        pq_model.file_key = object_key

    db.commit()

@router.post('/upload',status_code=201)
async def upload_pq(
                    db:db_dependency,
                    user:user_dependency,
                    course_id:int = Form(...),
                    session:str = Form(...),
                    assessment_type:str = Form(...),
                    file:UploadFile = File(...)
                    ):
    require_admin(user)
    course, level = resolve_course_level(db, course_id)
    file_name = f"{course.code} {assessment_type} {session}.pdf"
    
    # Create PQ record first to get the ID
    pq = Pq(course=course, session=session, assessment_type=assessment_type,
                level=level, file_name=file_name, time_created=datetime.now(),
                uploader_id=user.id)
    db.add(pq)
    db.commit()
    db.refresh(pq)

    # Upload to R2 with stable object key based on PQ ID
    object_key = f"past-questions/{pq.id}.pdf"
    upload_file(
        file.file,
        object_key,
        "application/pdf"
    )
    
    # Store the object key in the database
    pq.file_key = object_key
    db.commit()

    return serialize_pq(pq)

@router.delete('/delete-pq',status_code=204)
async def delete_pq(db:db_dependency,
                    id:int,
                    user:user_dependency):
    require_admin(user)
    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
        raise HTTPException(status_code=404,detail='Pq not found')
    
    # Delete file from R2 if it exists
    if pq_model.file_key:
        delete_file(pq_model.file_key)
    
    db.delete(pq_model) 
    db.commit()

@router.get('/check')
async def check_file_name(id:int,
            db:db_dependency):
    pq_model = db.query(Pq).filter(Pq.id == id).first()
    if pq_model is None:
        raise HTTPException(status_code=404,detail='Pq not found')  
    return {"file_name": pq_model.file_name}   
