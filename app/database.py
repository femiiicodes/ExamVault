from fastapi.params import Depends

import app.models as models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Annotated
from dotenv import load_dotenv
import os
load_dotenv()

# DATABASE_URL = "postgresql+psycopg2://postgres:Preserved28/4@localhost:5432/PastQuestionHub"
engine = create_engine(os.getenv('DATABASE_URL'))
SessionLocal = sessionmaker(bind=engine,autoflush=False,autocommit=False)

models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



