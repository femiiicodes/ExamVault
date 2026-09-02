def test_get_pq_details(authenticated_client,sample_pq):
    response= authenticated_client.get('/pqs/pq_details',params={'id':1})
    assert response.status_code == 200
    data = response.json()
    expected = {
    "session": "23/24",
    "assessment_type": "Test 1",
    "level": '300',
    "course_id": sample_pq.course_id,
    "course_code": "EIE525",
}

    for key, value in expected.items():
        assert data[key] == value



def test_edit_pq_details_updates_only_supplied_fields(authenticated_client, sample_pq):
    response = authenticated_client.patch(
        '/pqs/edit-pq',
        params={'id': sample_pq.id},
        data={'session': '24/25'},
    )

    assert response.status_code == 204
    assert response.content == b''

    details_response = authenticated_client.get(
        '/pqs/pq_details',
        params={'id': sample_pq.id},
    )
    details = details_response.json()
    assert details['course_code'] == 'EIE525'
    assert details['session'] == '24/25'
    assert details['assessment_type'] == 'Test 1'
    assert details['level'] == '300'


def test_delete_pq(authenticated_client,sample_pq):
    response = authenticated_client.delete('/pqs/delete-pq',params={'id':1})
    assert response.status_code == 204


def test_pq_file_download_returns_signed_url(authenticated_client, sample_pq):
    """Test that download endpoint redirects to a signed R2 URL"""
    response = authenticated_client.get('/pqs/download_file', params={'id': sample_pq.id}, follow_redirects=False)
    
    # Should return a redirect to the signed URL
    assert response.status_code == 303
    assert 'location' in response.headers
    # The location should contain the R2 bucket URL
    location = response.headers['location']
    assert '.r2.cloudflarestorage.com' in location or 'http' in location


def test_upload_pq(authenticated_client, test_db):
    from app.models import College, Course, Programme, ProgrammeCourse
    college = College(name='Upload Test College')
    test_db.add(college)
    test_db.commit()
    programme = Programme(name='Upload Test Programme', college_id=college.id)
    course = Course(code='CHE515', title='Chemistry Test Course')
    test_db.add_all([programme, course])
    test_db.commit()
    test_db.add(ProgrammeCourse(programme_id=programme.id, course_id=course.id, level=500, semester=1))
    test_db.commit()
    with open('tests/files/question.pdf','rb') as f:
        response = authenticated_client.post('/pqs/upload',data={
            'course_id':str(course.id),
            'session':'2025-2026',
            'assessment_type':'Examination',
            },files={
                'file': ('question.pdf',f, 'application/pdf')

            })
        assert response.status_code == 201


def test_list_pqs_returns_course_and_level(authenticated_client, sample_pq):
    response = authenticated_client.get('/pqs')

    assert response.status_code == 200
    assert response.json()[0]['course_code'] == 'EIE525'
    assert response.json()[0]['level'] == '300'


def test_upload_rejects_course_without_programme_level(authenticated_client, test_db):
    from app.models import Course
    course = Course(code='UNASSIGNED101', title='Unassigned Course')
    test_db.add(course)
    test_db.commit()

    with open('tests/files/question.pdf', 'rb') as file:
        response = authenticated_client.post(
            '/pqs/upload',
            data={'course_id': str(course.id), 'session': '2025-2026', 'assessment_type': 'Test 1'},
            files={'file': ('question.pdf', file, 'application/pdf')},
        )

    assert response.status_code == 400
    assert response.json()['detail'] == 'Course has no programme level assigned'


def test_upload_rejects_conflicting_programme_levels(authenticated_client, test_db):
    from app.models import College, Course, Programme, ProgrammeCourse
    college = College(name='Conflict Test College')
    test_db.add(college)
    test_db.commit()
    first = Programme(name='Conflict Programme One', college_id=college.id)
    second = Programme(name='Conflict Programme Two', college_id=college.id)
    course = Course(code='CONFLICT101', title='Conflicting Course')
    test_db.add_all([first, second, course])
    test_db.commit()
    test_db.add_all([
        ProgrammeCourse(programme_id=first.id, course_id=course.id, level=100, semester=1),
        ProgrammeCourse(programme_id=second.id, course_id=course.id, level=200, semester=1),
    ])
    test_db.commit()

    with open('tests/files/question.pdf', 'rb') as file:
        response = authenticated_client.post(
            '/pqs/upload',
            data={'course_id': str(course.id), 'session': '2025-2026', 'assessment_type': 'Test 1'},
            files={'file': ('question.pdf', file, 'application/pdf')},
        )

    assert response.status_code == 400
    assert response.json()['detail'] == 'Course has conflicting programme levels'


