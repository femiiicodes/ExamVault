import pytest
from fastapi.testclient import TestClient
from app.main import app
# from sqlalchemy.ext.declarative import se
from sqlalchemy import create_engine
from app.models import Base
from sqlalchemy.orm import sessionmaker
from app.database import get_db
from datetime import datetime
from app.routers.auth import get_current_user
import os




@pytest.fixture
def engine():
    engine = create_engine('sqlite:///./test.db',connect_args={'check_same_thread':False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def test_db(engine):
    TestingSessionLocal = sessionmaker(bind=engine,autoflush=False,autocommit=False)
    session =  TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db,sample_user):

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides

    with TestClient(app) as c:
        yield c

    app.dependency_overrides = {}

@pytest.fixture
def authenticated_client(test_db,sample_user):

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: sample_user
    

    with TestClient(app) as c:
        yield c

    app.dependency_overrides = {}

@pytest.fixture 
def sample_user(test_db):
    import uuid
    from app.models import User, College, Programme
    from app.routers.auth import hash_password

    unique_id = str(uuid.uuid4())[:8]
    college = College(name=f'Test College {unique_id}')
    test_db.add(college)
    test_db.commit()
    test_db.refresh(college)

    programme = Programme(name=f'Test Programme {unique_id}', college_id=college.id)
    test_db.add(programme)
    test_db.commit()
    test_db.refresh(programme)

    user = User(
        first_name='Femi',
        last_name='Adewusi',
        email='adefemiadewusi07@gmail.com',
        level='300',
        programme_id=programme.id,
        role='admin',
        hashed_password=hash_password('Password')
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    yield user

    test_db.query(User).where(User.email==user.email).delete()
    test_db.query(Programme).filter(Programme.id == programme.id).delete()
    test_db.query(College).filter(College.id == college.id).delete()
    test_db.commit()

@pytest.fixture
def sample_pq(test_db):
    from app.models import College, Course, Programme, ProgrammeCourse, Pq
    college = College(name='PQ Test College')
    test_db.add(college)
    test_db.commit()
    programme = Programme(name='PQ Test Programme', college_id=college.id)
    course = Course(code='EIE525', title='Test Course')
    test_db.add_all([programme, course])
    test_db.commit()
    test_db.add(ProgrammeCourse(programme_id=programme.id, course_id=course.id, level=300, semester=1))
    test_db.commit()
    pq = Pq(session='23/24', assessment_type='Test 1', level='300', course_id=course.id, 
            file_name='EIE525 Test 1 23-24.pdf', file_key='past-questions/1.pdf',
            time_created=datetime.now(), uploader_id=1)
    test_db.add(pq)
    test_db.commit()
    test_db.refresh(pq)

    yield pq
    test_db.query(Pq).filter(Pq.id==pq.id).delete()
    test_db.query(ProgrammeCourse).filter(ProgrammeCourse.course_id == course.id).delete()
    test_db.query(Course).filter(Course.id == course.id).delete()
    test_db.query(Programme).filter(Programme.id == programme.id).delete()
    test_db.query(College).filter(College.id == college.id).delete()
    test_db.commit()




