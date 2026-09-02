import pytest
from app.models import Programme, Course, ProgrammeCourse, User, College, Pq
from app.routers.auth import hash_password
from datetime import datetime


def test_delete_programme_cascades_programme_courses(authenticated_client, test_db):
    """Test that deleting a programme cascades to delete programme_courses"""
    # Create college
    college = College(name='Test College')
    test_db.add(college)
    test_db.commit()
    
    # Create programme
    programme = Programme(name='Test Programme', college_id=college.id)
    test_db.add(programme)
    test_db.commit()
    
    # Create course
    course = Course(code='CS101', title='Intro to CS')
    test_db.add(course)
    test_db.commit()
    
    # Create programme_course
    pc = ProgrammeCourse(programme_id=programme.id, course_id=course.id, level=100, semester=1)
    test_db.add(pc)
    test_db.commit()
    
    pc_id = pc.id
    
    # Verify programme_course exists
    assert test_db.query(ProgrammeCourse).filter(ProgrammeCourse.id == pc_id).first() is not None
    
    # Delete programme with password
    response = authenticated_client.delete(
        '/course-management/programmes',
        params={'id': programme.id}
    )
    
    assert response.status_code == 204
    
    # Verify programme is deleted
    assert test_db.query(Programme).filter(Programme.id == programme.id).first() is None
    
    # Verify programme_course is cascaded deleted
    assert test_db.query(ProgrammeCourse).filter(ProgrammeCourse.id == pc_id).first() is None


def test_delete_course_cascades_programme_courses(authenticated_client, test_db):
    """Test that deleting a course cascades to delete programme_courses"""
    # Create college and programme
    college = College(name='Test College 2')
    test_db.add(college)
    test_db.commit()
    
    programme = Programme(name='Test Programme 2', college_id=college.id)
    test_db.add(programme)
    test_db.commit()
    
    # Create course
    course = Course(code='CS201', title='Data Structures')
    test_db.add(course)
    test_db.commit()
    
    # Create programme_course
    pc = ProgrammeCourse(programme_id=programme.id, course_id=course.id, level=200, semester=2)
    test_db.add(pc)
    test_db.commit()
    
    pc_id = pc.id
    course_id = course.id
    
    # Verify programme_course exists
    assert test_db.query(ProgrammeCourse).filter(ProgrammeCourse.id == pc_id).first() is not None
    
    # Delete course
    response = authenticated_client.delete(
        '/course-management/courses',
        params={'id': course_id}
    )
    
    assert response.status_code == 204
    
    # Verify course is deleted
    assert test_db.query(Course).filter(Course.id == course_id).first() is None
    
    # Verify programme_course is cascaded deleted
    assert test_db.query(ProgrammeCourse).filter(ProgrammeCourse.id == pc_id).first() is None


def test_delete_programme_sets_user_programme_id_null(authenticated_client, test_db):
    """Test that deleting a programme sets users.programme_id to NULL"""
    # Create college
    college = College(name='Test College 3')
    test_db.add(college)
    test_db.commit()
    
    # Create programme
    programme = Programme(name='Test Programme 3', college_id=college.id)
    test_db.add(programme)
    test_db.commit()
    
    # Create user assigned to programme
    user_obj = User(
        first_name='John',
        last_name='Doe',
        email='john.doe@test.com',
        level='300',
        role='student',
        programme_id=programme.id,
        hashed_password=hash_password('password123')
    )
    test_db.add(user_obj)
    test_db.commit()
    
    user_id = user_obj.id
    programme_id = programme.id
    
    # Verify user has programme_id
    user_check = test_db.query(User).filter(User.id == user_id).first()
    assert user_check.programme_id == programme_id
    
    # Delete programme
    response = authenticated_client.delete(
        '/course-management/programmes',
        params={'id': programme_id}
    )
    
    assert response.status_code == 204
    
    # Verify user's programme_id is NULL
    user_after = test_db.query(User).filter(User.id == user_id).first()
    assert user_after is not None
    assert user_after.programme_id is None


def test_delete_user_sets_pq_uploader_id_null(authenticated_client, test_db):
    """Test that deleting a user sets pqs.uploader_id to NULL"""
    college = College(name='Uploader Test College')
    test_db.add(college)
    test_db.commit()
    programme = Programme(name='Uploader Test Programme', college_id=college.id)
    course = Course(code='EIE525', title='Uploader Test Course')
    test_db.add_all([programme, course])
    test_db.commit()
    test_db.add(ProgrammeCourse(programme_id=programme.id, course_id=course.id, level=400, semester=1))
    test_db.commit()

    # Create user
    user_obj = User(
        first_name='Jane',
        last_name='Smith',
        email='jane.smith@test.com',
        level='400',
        role='student',
        programme_id=programme.id,
        hashed_password=hash_password('password456')
    )
    test_db.add(user_obj)
    test_db.commit()
    
    # Create PQ uploaded by user
    pq = Pq(
        session='23/24',
        assessment_type='Test',
        level='400',
        course_id=course.id,
        file_name='EIE525 Test 23-24.pdf',
        file_key='past-questions/1.pdf',
        time_created=datetime.now(),
        uploader_id=user_obj.id
    )
    test_db.add(pq)
    test_db.commit()
    
    user_id = user_obj.id
    pq_id = pq.id
    
    # Verify PQ has uploader_id
    pq_check = test_db.query(Pq).filter(Pq.id == pq_id).first()
    assert pq_check.uploader_id == user_id
    
    # Delete user
    response = authenticated_client.delete(
        '/users/delete-user',
        params={'id': user_id}
    )
    
    assert response.status_code == 204
    
    # Verify PQ's uploader_id is NULL
    pq_after = test_db.query(Pq).filter(Pq.id == pq_id).first()
    assert pq_after is not None
    assert pq_after.uploader_id is None








def test_delete_programme_not_found(authenticated_client, test_db):
    """Test that deleting non-existent programme returns 404"""
    response = authenticated_client.delete(
        '/course-management/programmes',
        params={'id': 9999}
    )
    
    assert response.status_code == 404
    assert 'Programme not found' in response.json()['detail']


def test_delete_course_not_found(authenticated_client, test_db):
    """Test that deleting non-existent course returns 404"""
    response = authenticated_client.delete(
        '/course-management/courses',
        params={'id': 9999}
    )
    
    assert response.status_code == 404
    assert 'Course not found' in response.json()['detail']
