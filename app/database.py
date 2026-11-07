
from fastapi.params import Depends

import app.models as models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Annotated
from dotenv import load_dotenv
import os

env_file = os.getenv('ENV_FILE', '.env')
load_dotenv(env_file)

engine = create_engine(os.getenv('DATABASE_URL'))

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
