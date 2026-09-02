from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()
class Pq(Base):

    __tablename__ = 'pqs'
    id = Column(Integer,nullable=False,primary_key=True,index=True,autoincrement=True)
    session = Column(String)
    assessment_type = Column(String)
    level = Column(String)
    course_id = Column(Integer, ForeignKey('courses.id', ondelete='RESTRICT'), nullable=False)
    file_name = Column(String)
    file_key = Column(String, nullable=True)
    time_created = Column(DateTime)
    uploader_id = Column(Integer, ForeignKey('users.id'))
    course = relationship('Course', back_populates='past_questions')
    uploader = relationship('User',back_populates='past_questions')

class User(Base):
    
    __tablename__ = 'users'
    id = Column(Integer,index=True,primary_key=True,autoincrement=True,nullable=False)
    programme_id = Column(Integer,ForeignKey('programmes.id'),nullable=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    level = Column(String)
    role = Column(String)
    hashed_password = Column(String)

    past_questions = relationship('Pq',back_populates='uploader')
    programme = relationship('Programme', back_populates='users')



class College(Base):
    __tablename__ = "colleges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    programmes = relationship(
        "Programme",
        back_populates="college"
    )

class Programme(Base):
    __tablename__ = "programmes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    college_id = Column(
        Integer,
        ForeignKey("colleges.id"),
        nullable=False
    )

    college = relationship(
        "College",
        back_populates="programmes"
    )

    programme_courses = relationship(
        "ProgrammeCourse",
        back_populates="programme",
        cascade="all, delete-orphan"
    )

    users = relationship(
        "User",
        back_populates="programme"
    )

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)

    code = Column(
        String,
        unique=True,
        nullable=False
    )

    title = Column(
        String,
        nullable=False
    )

    programme_courses = relationship(
        "ProgrammeCourse",
        back_populates="course",
        cascade="all, delete-orphan"
    )

    past_questions = relationship("Pq", back_populates="course")


class ProgrammeCourse(Base):
    __tablename__ = "programme_courses"

    id = Column(Integer, primary_key=True, index=True)

    programme_id = Column(
        Integer,
        ForeignKey("programmes.id"),
        nullable=False
    )

    course_id = Column(
        Integer,
        ForeignKey("courses.id"),
        nullable=False
    )

    level = Column(
        Integer,
        nullable=False
    )

    semester = Column(
        Integer,
        nullable=False
    )

    programme = relationship(
        "Programme",
        back_populates="programme_courses"
    )

    course = relationship(
        "Course",
        back_populates="programme_courses"
    )


# class UserCourse(Base):
#     __tablename__ = "user_courses"

#     id = Column(Integer, primary_key=True, index=True)

#     user_id = Column(
#         Integer,
#         ForeignKey("users.id"),
#         nullable=False
#     )

#     course_id = Column(
#         Integer,
#         ForeignKey("courses.id"),
#         nullable=False
#     )

#     user = relationship(
#         "User",
#         back_populates="user_courses"
#     )

#     course = relationship(
#         "Course",
#         back_populates="user_courses"
#     )