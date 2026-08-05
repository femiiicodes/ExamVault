def test_login_success(client,sample_user):
    response = client.post('/auth/token',
                data={'username':'adefemiadewusi07@gmail.com','password':'Password'})
    assert response.status_code == 200
    assert 'access_token' in response.json()
    assert response.json()['token_type'] == 'bearer'

def test_login_failure(client,sample_user):
    response = client.post('/auth/token',
                    data={'username':'adefemiadewusi07@gmail.com','password':'Wrong Password'})
    assert response.status_code == 401
    assert response.json() == {'detail':'Incorrect Email or Password'}
    

def test_protected_route_with_token(client,sample_user,sample_pq):
    login_response = client.post('/auth/token',
                    data={'username':'adefemiadewusi07@gmail.com','password':'Password'})
    token = login_response.json()['access_token']

    response = client.get('/pqs/pq_details',params={'id':1},headers={'Authorization':f'Bearer {token}'})

    assert response.status_code == 200

    data = response.json()

    assert data["session"] == "23/24"
    assert data["assessment_type"] == "Test 1"
    assert data["department"] == "EIE"
    assert data["level"] == 300
    assert data["course"] == "EIE525"
    assert data["file_path"] == "uploads/past_questions\\EIE346 Examination 2023-2024.pdf"
    assert data["user_id"] == 1


def test_protected_route_with_token(client,sample_user,sample_pq):
    response = client.get('/pqs/pq_details',params={'id':1},headers={'Authorization':'Bearer invalid_token'})
    assert response.status_code == 401
    assert response.json() == {'detail': 'Unable to validate credentials'}




















