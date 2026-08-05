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
    from app.models import User
    from app.routers.auth import hash_password

    user = User(first_name='Femi',last_name='Adewusi',email='adefemiadewusi07@gmail.com',level=300,department='EIE',role='admin',hashed_password=hash_password('Password'))
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    yield user

    test_db.query(User).where(User.email==user.email).delete()
    test_db.commit()

@pytest.fixture
def sample_pq(test_db):
    from app.models import Pq
    pq = Pq(session='23/24',assessment_type='Test 1',department='EIE',level=300,course='EIE525',file_path='uploads/past_questions\EIE346 Examination 2023-2024.pdf',time_created=datetime.now(),user_id=1)
    with open("uploads/past_questions/EIE346 Examination 2023-2024.pdf", "wb") as f:
        f.write(b"dummy")   
    test_db.add(pq)
    test_db.commit()
    test_db.refresh(pq)

    yield pq
    # os.remove("uploads/past_questions/EIE346 Examination 2023-2024.pdf")  
    test_db.query(Pq).filter(Pq.id==pq.id).delete()
    test_db.commit()




