from app.models import User


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
    assert data["level"] == "300"
    assert data["course_code"] == "EIE525"
    assert data["course_id"] == sample_pq.course_id
    assert data["uploader"] == "Femi Adewusi"


def test_protected_route_with_token(client,sample_user,sample_pq):
    response = client.get('/pqs/pq_details',params={'id':1},headers={'Authorization':'Bearer invalid_token'})
    assert response.status_code == 401
    assert response.json() == {'detail': 'Unable to validate credentials'}


def test_register_rejects_invalid_admin_token(client, sample_user, monkeypatch):
    monkeypatch.setenv('ADMIN_KEY', 'test-admin-key')
    payload = {
        'first_name': 'New',
        'last_name': 'User',
        'email': 'new-user@example.com',
        'level': '300',
        'programme_id': sample_user.programme_id,
        'role': 'user',
        'password': 'Password',
        'admin_token': 'wrong-key'
    }

    response = client.post('/auth/register', json=payload)

    assert response.status_code == 403
    assert response.json() == {'detail': 'Invalid admin token'}


def test_register_accepts_admin_token_from_environment(client, sample_user, test_db, monkeypatch):
    monkeypatch.setenv('ADMIN_KEY', 'test-admin-key')
    payload = {
        'first_name': 'New',
        'last_name': 'User',
        'email': 'new-user@example.com',
        'level': '300',
        'programme_id': sample_user.programme_id,
        'role': 'user',
        'password': 'Password',
        'admin_token': 'test-admin-key'
    }

    response = client.post('/auth/register', json=payload)

    assert response.status_code == 201
    assert test_db.query(User).filter(User.email == payload['email']).one_or_none() is not None




















