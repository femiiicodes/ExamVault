def test_get_pq_details(authenticated_client,sample_pq):
    response= authenticated_client.get('/pqs/pq_details',params={'id':1})
    assert response.status_code == 200
    data = response.json()
    expected = {
    "session": "23/24",
    "assessment_type": "Test 1",
    "department": "EIE",
    "level": '300',
    "course": "EIE525",
    "file_path": "uploads/past_questions\EIE346 Examination 2023-2024.pdf",
    "user_id": 1,
}

    for key, value in expected.items():
        assert data[key] == value



# def test_edit_pq_details(authenticated_client,sample_pq):
#     response = authenticated_client.put('pqs/edit-pq',params={'id':1},data={
#         'department':'MEE'
#     })
#     assert response.status_code == 204
#     data = response.json()
#     assert data['department'] == 'MEE'


def test_delete_pq(authenticated_client,sample_pq):
    response = authenticated_client.delete('/pqs/delete-pq',params={'id':1})
    assert response.status_code == 204


def test_upload_pq(authenticated_client):
    with open('tests/files/question.pdf','rb') as f:
        response = authenticated_client.post('/pqs/upload',data={
            'course':'CHE515',
            'session':'25-26',
            'assessment_type':'Examination',
            'department':'Chemical Engineering',
            'level':'500',
            },files={
                'file': ('question.pdf',f, 'application/pdf')

            })
        assert response.status_code == 201


