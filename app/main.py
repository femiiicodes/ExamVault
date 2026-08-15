from fastapi import FastAPI, APIRouter, Request
from fastapi.staticfiles import StaticFiles
from app.routers import pqs, auth, users, course_management
from fastapi.templating import Jinja2Templates




app = FastAPI()
templates = Jinja2Templates(directory='templates')

app.mount('/static',StaticFiles(directory='static'),name='static')
@app.get('/')
async def render_landing_page(request:Request):
    return templates.TemplateResponse(request=request,name='landing-page.html')

# @app.get('/')
# async def home():
#     return {'Hi':'Hello'}


app.include_router(pqs.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(course_management.router)