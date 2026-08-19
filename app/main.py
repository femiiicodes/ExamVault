from fastapi import FastAPI, APIRouter, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from app.routers import pqs, auth, users, course_management
from fastapi.templating import Jinja2Templates
from app.database import get_db
from app.routers.auth import get_current_user
from app.models import Pq, Course, Programme, College, User
from typing import Annotated
from sqlalchemy.orm import Session




app = FastAPI()
templates = Jinja2Templates(directory='templates')

app.mount('/static',StaticFiles(directory='static'),name='static')
@app.get('/')
async def render_landing_page(request:Request):
    return templates.TemplateResponse(request=request,name='landing-page.html')

@app.get('/admin')
async def render_admin_dashboard(request:Request, user:Annotated[User,Depends(get_current_user)]=None, db:Annotated[Session,Depends(get_db)]=None):
    if user is None:
        raise HTTPException(status_code=401,detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=403,detail='User not authorized')

    total_past_questions = db.query(Pq).count()
    total_courses = db.query(Course).count()
    total_programmes = db.query(Programme).count()
    total_colleges = db.query(College).count()
    total_students = db.query(User).count()

    return templates.TemplateResponse(
        request=request,
        name='admin-dashboard.html',
        context={
            'total_past_questions': total_past_questions,
            'total_courses': total_courses,
            'total_programmes': total_programmes,
            'total_colleges': total_colleges,
            'total_students': total_students
        }
    )

@app.get('/dashboard')
async def render_student_dashboard(request:Request, user:Annotated[User,Depends(get_current_user)]=None):
    if user is None:
        raise HTTPException(status_code=401,detail='User not authenticated')

    return templates.TemplateResponse(request=request,name='dashboard.html')

@app.get('/admin/colleges')
async def render_colleges_page(request:Request, user:Annotated[User,Depends(get_current_user)]=None):
    if user is None:
        raise HTTPException(status_code=401,detail='User not authenticated')
    if user.role != 'admin':
        raise HTTPException(status_code=403,detail='User not authorized')

    return templates.TemplateResponse(request=request,name='colleges.html')

# @app.get('/')
# async def home():
#     return {'Hi':'Hello'}


app.include_router(pqs.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(course_management.router)