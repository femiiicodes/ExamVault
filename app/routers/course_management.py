from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models import Programme, Course, College, ProgrammeCourse, User

router = APIRouter(prefix='/course-management', tags=['course-management'])

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[User, Depends(get_current_user)]


class ProgrammeCreate(BaseModel):
    name: str
    college_id: int


class ProgrammeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    college_id: int


class CourseCreate(BaseModel):
    code: str
    title: str


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    title: str


@router.post('/programmes', response_model=ProgrammeResponse, status_code=201)
async def create_programme(
    db: db_dependency,
    user: user_dependency,
    payload: ProgrammeCreate,
):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='User not authorized')

    college = db.query(College).filter(College.id == payload.college_id).first()
    if college is None:
        raise HTTPException(status_code=404, detail='College not found')

    existing = db.query(Programme).filter(Programme.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail='Programme with this name already exists')

    programme = Programme(name=payload.name, college_id=payload.college_id)
    db.add(programme)
    db.commit()
    db.refresh(programme)
    return programme


@router.post('/courses', response_model=CourseResponse, status_code=201)
async def create_course(
    db: db_dependency,
    user: user_dependency,
    payload: CourseCreate,
):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='User not authorized')

    existing = db.query(Course).filter(Course.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=409, detail='Course with this code already exists')

    course = Course(code=payload.code, title=payload.title)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


class ProgrammeUpdate(BaseModel):
    name: str | None = None
    college_id: int | None = None


class CourseUpdate(BaseModel):
    code: str | None = None
    title: str | None = None


@router.patch('/programmes', status_code=204)
async def edit_programme(
    id: int,
    db: db_dependency,
    user: user_dependency,
    data: ProgrammeUpdate,
):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='User not authorized')

    programme = db.query(Programme).filter(Programme.id == id).first()
    if programme is None:
        raise HTTPException(status_code=404, detail='Programme not found')

    if data.name is not None:
        existing = db.query(Programme).filter(Programme.name == data.name, Programme.id != id).first()
        if existing:
            raise HTTPException(status_code=409, detail='Programme with this name already exists')
        programme.name = data.name

    if data.college_id is not None:
        college = db.query(College).filter(College.id == data.college_id).first()
        if college is None:
            raise HTTPException(status_code=404, detail='College not found')
        programme.college_id = data.college_id

    db.commit()


@router.patch('/courses', status_code=204)
async def edit_course(
    id: int,
    db: db_dependency,
    user: user_dependency,
    data: CourseUpdate,
):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='User not authorized')

    course = db.query(Course).filter(Course.id == id).first()
    if course is None:
        raise HTTPException(status_code=404, detail='Course not found')

    if data.code is not None:
        existing = db.query(Course).filter(Course.code == data.code, Course.id != id).first()
        if existing:
            raise HTTPException(status_code=409, detail='Course with this code already exists')
        course.code = data.code

    if data.title is not None:
        course.title = data.title

    db.commit()


class CollegeCreate(BaseModel):
    name: str


class CollegeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class CollegeUpdate(BaseModel):
    name: str | None = None


class ProgrammeCourseCreate(BaseModel):
    programme_id: int
    course_id: int
    level: int
    semester: int


class ProgrammeCourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    programme_id: int
    course_id: int
    level: int
    semester: int


@router.post('/colleges', response_model=CollegeResponse, status_code=201)
async def create_college(
    db: db_dependency,
    user: user_dependency,
    payload: CollegeCreate,
):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='User not authorized')

    existing = db.query(College).filter(College.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail='College with this name already exists')

    college = College(name=payload.name)
    db.add(college)
    db.commit()
    db.refresh(college)
    return college


@router.patch('/colleges', status_code=204)
async def edit_college(
    id: int,
    db: db_dependency,
    user: user_dependency,
    data: CollegeUpdate,
):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='User not authorized')

    college = db.query(College).filter(College.id == id).first()
    if college is None:
        raise HTTPException(status_code=404, detail='College not found')

    if data.name is not None:
        existing = db.query(College).filter(College.name == data.name, College.id != id).first()
        if existing:
            raise HTTPException(status_code=409, detail='College with this name already exists')
        college.name = data.name

    db.commit()


@router.post('/programme-courses', response_model=ProgrammeCourseResponse, status_code=201)
async def create_programme_course(
    db: db_dependency,
    user: user_dependency,
    payload: ProgrammeCourseCreate,
):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='User not authorized')

    programme = db.query(Programme).filter(Programme.id == payload.programme_id).first()
    if programme is None:
        raise HTTPException(status_code=404, detail='Programme not found')

    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail='Course not found')

    existing = db.query(ProgrammeCourse).filter(
        ProgrammeCourse.programme_id == payload.programme_id,
        ProgrammeCourse.course_id == payload.course_id,
        ProgrammeCourse.level == payload.level,
        ProgrammeCourse.semester == payload.semester,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail='ProgrammeCourse already exists')

    pc = ProgrammeCourse(
        programme_id=payload.programme_id,
        course_id=payload.course_id,
        level=payload.level,
        semester=payload.semester,
    )
    db.add(pc)
    db.commit()
    db.refresh(pc)
    return pc


@router.delete('/programmes', status_code=204)
async def delete_programme(
    id: int,
    db: db_dependency,
    user: user_dependency,
):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='User not authorized')

    programme = db.query(Programme).filter(Programme.id == id).first()
    if programme is None:
        raise HTTPException(status_code=404, detail='Programme not found')

    # Database cascade will handle deletion of related programme_courses
    # and set users.programme_id to NULL
    db.delete(programme)
    db.commit()


@router.delete('/courses', status_code=204)
async def delete_course(
    id: int,
    db: db_dependency,
    user: user_dependency,
):
    if user is None:
        raise HTTPException(status_code=401, detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='User not authorized')

    course = db.query(Course).filter(Course.id == id).first()
    if course is None:
        raise HTTPException(status_code=404, detail='Course not found')

    # Database cascade will handle deletion of related programme_courses
    db.delete(course)
    db.commit()
