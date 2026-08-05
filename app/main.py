from fastapi import FastAPI, APIRouter
from app.routers import pqs, auth, users
app = FastAPI()



@app.get('/')
async def home():
    return {'Hi':'Hello'}


app.include_router(pqs.router)
app.include_router(auth.router)
app.include_router(users.router)