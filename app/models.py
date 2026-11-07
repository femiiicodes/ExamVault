from sqlalchemy import Boolean, Column, String, Integer, ForeignKey, DateTime, Index, UniqueConstraint
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

    past_questions = relationship('Pq', back_populates='uploader')
    programme = relationship('Programme', back_populates='users')
    auth_sessions = relationship(
        'AuthSession',
        back_populates='user',
        cascade='all, delete-orphan',
    )
    security_answers = relationship(
        'SecurityAnswer',
        back_populates='user',
        cascade='all, delete-orphan',
    )
    payments = relationship('Payment', back_populates='user')
    entitlements = relationship('Entitlement', back_populates='user')
    daily_views = relationship('DailyPqView', back_populates='user')


class AuthSession(Base):
    __tablename__ = 'auth_sessions'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    is_persistent = Column(Boolean, nullable=False, default=False)

    user = relationship('User', back_populates='auth_sessions')


class SecurityAnswer(Base):
    __tablename__ = 'security_answers'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    question_id = Column(String, nullable=False)
    answer_hash = Column(String, nullable=False)

    user = relationship('User', back_populates='security_answers')


class PasswordResetToken(Base):
    __tablename__ = 'password_reset_tokens'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)

    user = relationship('User')



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


class AcademicPeriod(Base):
    __tablename__ = 'academic_periods'

    id = Column(Integer, primary_key=True, index=True)
    academic_session = Column(String, nullable=False)
    semester = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint('academic_session', 'semester', name='uq_academic_period_session_semester'),
        Index('ix_academic_periods_active', 'is_active'),
    )


class AcademicPeriodSwitch(Base):
    __tablename__ = 'academic_period_switches'

    id = Column(Integer, primary_key=True, index=True)
    previous_period_id = Column(Integer, ForeignKey('academic_periods.id'), nullable=True)
    new_period_id = Column(Integer, ForeignKey('academic_periods.id'), nullable=False)
    admin_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    switched_at = Column(DateTime, nullable=False)


class Payment(Base):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    academic_period_id = Column(Integer, ForeignKey('academic_periods.id'), nullable=False)
    reference = Column(String, nullable=False, unique=True, index=True)
    authorization_url = Column(String, nullable=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    status = Column(String, nullable=False)
    paystack_transaction_id = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)

    user = relationship('User', back_populates='payments')


class Entitlement(Base):
    __tablename__ = 'entitlements'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    academic_period_id = Column(Integer, ForeignKey('academic_periods.id'), nullable=False)
    payment_id = Column(Integer, ForeignKey('payments.id'), nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    user = relationship('User', back_populates='entitlements')
    payment = relationship('Payment')

    __table_args__ = (
        UniqueConstraint('user_id', 'academic_period_id', name='uq_entitlement_user_period'),
    )


class DailyPqView(Base):
    __tablename__ = 'daily_pq_views'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    past_question_id = Column(Integer, ForeignKey('pqs.id', ondelete='CASCADE'), nullable=False)
    view_date = Column(String, nullable=False)
    viewed_at = Column(DateTime, nullable=False)

    user = relationship('User', back_populates='daily_views')
    past_question = relationship('Pq')

    __table_args__ = (
        UniqueConstraint(
            'user_id', 'past_question_id', 'view_date',
            name='uq_daily_pq_view_user_question_date',
        ),
        Index('ix_daily_pq_views_user_date', 'user_id', 'view_date'),
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