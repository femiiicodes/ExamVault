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


def test_register_ignores_public_admin_token(client, sample_user):
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

    assert response.status_code == 201
    assert response.json()['detail'] == 'Account created successfully'


def test_register_creates_regular_user(client, sample_user, test_db):
    payload = {
        'first_name': 'New',
        'last_name': 'User',
        'email': 'new-user@example.com',
        'level': '300',
        'programme_id': sample_user.programme_id,
        'role': 'admin',
        'password': 'Password',
        'admin_token': 'not-used'
    }

    response = client.post('/auth/register', json=payload)

    assert response.status_code == 201
    created = test_db.query(User).filter(User.email == payload['email']).one()
    assert created.role == 'user'


def test_register_hashes_optional_security_answers(client, sample_user, test_db):
    payload = {
        'first_name': 'Recovery',
        'last_name': 'User',
        'email': 'recovery-user@example.com',
        'level': '300',
        'programme_id': sample_user.programme_id,
        'password': 'Password',
        'security_answers': [
            {'question_id': 'q1', 'answer': '  Blue   House '},
            {'question_id': 'q2', 'answer': 'Accra'},
        ],
    }

    response = client.post('/auth/register', json=payload)

    assert response.status_code == 201
    user = test_db.query(User).filter(User.email == payload['email']).one()
    assert len(user.security_answers) == 2
    assert all(answer.answer_hash != 'blue house' for answer in user.security_answers)


def test_check_email_reports_available_and_used_addresses(client, sample_user):
    available = client.get('/auth/check-email', params={'email': 'new-user@example.com'})
    used = client.get('/auth/check-email', params={'email': sample_user.email.upper()})

    assert available.status_code == 200
    assert available.json() == {'available': True}
    assert used.status_code == 200
    assert used.json() == {'available': False}


def test_refresh_rotates_persistent_session(client, sample_user, test_db):
    login_response = client.post(
        '/auth/token',
        data={
            'username': sample_user.email,
            'password': 'Password',
            'client_id': 'remember',
        },
    )
    assert login_response.status_code == 200
    old_refresh = client.cookies.get('refresh_token')

    refresh_response = client.post('/auth/refresh')

    assert refresh_response.status_code == 200
    assert client.cookies.get('refresh_token') != old_refresh
    assert test_db.query(User).filter(User.email == sample_user.email).one()


def test_logout_revokes_refresh_session(client, sample_user, test_db):
    client.post(
        '/auth/token',
        data={'username': sample_user.email, 'password': 'Password', 'client_id': 'remember'},
    )
    client.post('/auth/logout')

    assert client.post('/auth/refresh').status_code == 401

















