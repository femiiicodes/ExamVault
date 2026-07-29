from sqlalchemy import Column, String, Integer, ForeignKey,DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()
class Pq(Base):

    __tablename__ = 'pqs'
    id = Column(Integer,nullable=False,primary_key=True,index=True,autoincrement=True)
    session = Column(String)
    assessment_type = Column(String)
    department = Column(String)
    level = Column(String)
    course = Column(String)
    
    file_path = Column(String)
    time_created = Column(DateTime)
    user_id = Column(Integer,ForeignKey('users.id'))
    uploader = relationship('User',back_populates='past_questions')

class User(Base):
    
    __tablename__ = 'users'
    id = Column(Integer,index=True,primary_key=True,autoincrement=True,nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    level = Column(String)
    department=Column(String)
    role = Column(String)
    hashed_password = Column(String)

    past_questions = relationship('Pq',back_populates='uploader')



