from datetime import datetime, timedelta, timezone

from app.models import AuthSession, User


def test_login_success(client,sample_user):
    response = client.post('/auth/token',
                data={'username':'adefemiadewusi07@gmail.com','password':'Password'})
    assert response.status_code == 200
    assert 'access_token' in response.json()
    assert response.json()['token_type'] == 'bearer'


def test_remember_me_login_persists_refresh_session(client, sample_user, test_db):
    response = client.post(
        '/auth/token',
        data={'username': sample_user.email, 'password': 'Password', 'client_id': 'remember'},
    )
    assert response.status_code == 200
    session = test_db.query(AuthSession).filter(AuthSession.user_id == sample_user.id).order_by(AuthSession.id.desc()).first()
    assert session is not None
    assert session.is_persistent is True
    assert session.expires_at is None
    assert client.cookies.get('refresh_token') is not None


def test_non_persistent_login_expires_after_30_minutes(client, sample_user, test_db):
    response = client.post(
        '/auth/token',
        data={'username': sample_user.email, 'password': 'Password', 'client_id': 'session'},
    )
    assert response.status_code == 200
    session = test_db.query(AuthSession).filter(AuthSession.user_id == sample_user.id).order_by(AuthSession.id.desc()).first()
    assert session is not None
    assert session.is_persistent is False
    assert session.expires_at is not None
    expires_in_seconds = (session.expires_at - session.created_at).total_seconds()
    assert abs(expires_in_seconds - 1800) < 5


def test_refresh_preserves_non_persistent_absolute_expiry(client, sample_user, test_db):
    login_response = client.post(
        '/auth/token',
        data={'username': sample_user.email, 'password': 'Password', 'client_id': 'session'},
    )
    assert login_response.status_code == 200
    session = test_db.query(AuthSession).filter(AuthSession.user_id == sample_user.id).order_by(AuthSession.id.desc()).first()
    original_expiry = session.expires_at

    refresh_response = client.post('/auth/refresh')
    assert refresh_response.status_code == 200

    sessions = test_db.query(AuthSession).filter(AuthSession.user_id == sample_user.id).order_by(AuthSession.id).all()
    assert len(sessions) == 2
    assert sessions[0].revoked_at is not None
    assert sessions[1].expires_at == original_expiry
    assert sessions[1].revoked_at is None


def test_access_token_type_is_validated(client, sample_user):
    from app.routers.auth import create_access_token

    invalid_token = create_access_token({'sub': sample_user.email}, timedelta(minutes=15))
    response = client.get(
        '/dashboard',
        headers={'Authorization': f'Bearer {invalid_token}', 'Accept': 'application/json'},
    )
    assert response.status_code == 401
    assert response.json() == {'detail': 'Unable to validate credentials'}


def test_root_redirects_authenticated_user(client, sample_user):
    login_response = client.post(
        '/auth/token',
        data={'username': sample_user.email, 'password': 'Password'},
    )
    assert login_response.status_code == 200
    response = client.get('/', follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/dashboard'


def test_login_page_redirects_authenticated_user(client, sample_user):
    login_response = client.post(
        '/auth/token',
        data={'username': sample_user.email, 'password': 'Password'},
    )
    assert login_response.status_code == 200
    response = client.get('/auth/login-page', follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/dashboard'

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
        'security_answers': [
            {'question_id': 'q1', 'answer': 'Blue House'},
            {'question_id': 'q2', 'answer': 'Accra'},
        ],
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
        'security_answers': [
            {'question_id': 'q1', 'answer': 'Blue House'},
            {'question_id': 'q2', 'answer': 'Accra'},
        ],
        'admin_token': 'not-used'
    }

    response = client.post('/auth/register', json=payload)

    assert response.status_code == 201
    created = test_db.query(User).filter(User.email == payload['email']).one()
    assert created.role == 'user'


def test_register_hashes_security_answers(client, sample_user, test_db):
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


def test_register_requires_security_answers(client, sample_user):
    payload = {
        'first_name': 'No',
        'last_name': 'Recovery',
        'email': 'no-recovery@example.com',
        'level': '300',
        'programme_id': sample_user.programme_id,
        'password': 'Password',
    }

    response = client.post('/auth/register', json=payload)

    assert response.status_code == 422


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


def test_security_question_recovery_returns_single_use_token(client, sample_user, test_db):
    from app.models import SecurityAnswer
    from app.routers.auth import hash_password

    test_db.add_all([
        SecurityAnswer(
            user_id=sample_user.id,
            question_id='q1',
            answer_hash=hash_password('blue house'),
        ),
        SecurityAnswer(
            user_id=sample_user.id,
            question_id='q2',
            answer_hash=hash_password('accra'),
        ),
    ])
    test_db.commit()

    questions = client.post(
        '/auth/password-recovery/security-questions',
        json={'email': sample_user.email},
    )
    assert questions.status_code == 200
    assert [question['id'] for question in questions.json()['questions']] == ['q1', 'q2']

    verified = client.post(
        '/auth/password-recovery/security-verify',
        json={
            'email': sample_user.email,
            'answers': [
                {'question_id': 'q1', 'answer': ' Blue   House '},
                {'question_id': 'q2', 'answer': 'Accra'},
            ],
        },
    )
    assert verified.status_code == 200
    token = verified.json()['token']

    reset = client.post(
        '/auth/password-reset/confirm',
        json={'token': token, 'password': 'NewPassword', 'confirm_password': 'NewPassword'},
    )
    assert reset.status_code == 200
    assert client.post(
        '/auth/password-reset/confirm',
        json={'token': token, 'password': 'AnotherPassword', 'confirm_password': 'AnotherPassword'},
    ).status_code == 400


def test_recovery_start_chooses_security_questions_without_sending_email(
    client,
    sample_user,
    monkeypatch,
    test_db,
):
    from app.models import SecurityAnswer
    from app.routers.auth import hash_password

    sent = []
    monkeypatch.setattr(
        'app.routers.auth.send_password_reset_email',
        lambda recipient, reset_url: sent.append((recipient, reset_url)),
    )
    test_db.add_all([
        SecurityAnswer(user_id=sample_user.id, question_id='q1', answer_hash=hash_password('one')),
        SecurityAnswer(user_id=sample_user.id, question_id='q2', answer_hash=hash_password('two')),
    ])
    test_db.commit()

    response = client.post(
        '/auth/password-recovery/start',
        json={'email': sample_user.email},
    )

    assert response.status_code == 200
    assert response.json()['method'] == 'security_questions'
    assert len(response.json()['questions']) == 2
    assert sent == []


def test_recovery_start_sends_email_only_without_security_questions(
    client,
    sample_user,
    monkeypatch,
):
    monkeypatch.setenv('APP_BASE_URL', 'https://example.com')
    sent = []
    monkeypatch.setattr(
        'app.routers.auth.send_password_reset_email',
        lambda recipient, reset_url: sent.append((recipient, reset_url)),
    )

    response = client.post(
        '/auth/password-recovery/start',
        json={'email': sample_user.email},
    )

    assert response.status_code == 200
    assert response.json()['method'] == 'email'
    assert sent[0][0] == sample_user.email


def test_security_question_recovery_rejects_incorrect_answer(client, sample_user, test_db):
    from app.models import SecurityAnswer
    from app.routers.auth import hash_password

    test_db.add_all([
        SecurityAnswer(user_id=sample_user.id, question_id='q1', answer_hash=hash_password('one')),
        SecurityAnswer(user_id=sample_user.id, question_id='q2', answer_hash=hash_password('two')),
    ])
    test_db.commit()

    response = client.post(
        '/auth/password-recovery/security-verify',
        json={
            'email': sample_user.email,
            'answers': [
                {'question_id': 'q1', 'answer': 'wrong'},
                {'question_id': 'q2', 'answer': 'two'},
            ],
        },
    )

    assert response.status_code == 400
    assert 'could not be verified' in response.json()['detail']


def test_password_reset_rejects_expired_token(client, sample_user, test_db):
    from datetime import datetime, timedelta, timezone
    from app.models import PasswordResetToken
    from app.routers.auth import hash_token

    raw_token = 'expired-recovery-token-' + ('x' * 32)
    test_db.add(PasswordResetToken(
        user_id=sample_user.id,
        token_hash=hash_token(raw_token),
        expires_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).replace(tzinfo=None),
        created_at=(datetime.now(timezone.utc) - timedelta(minutes=31)).replace(tzinfo=None),
    ))
    test_db.commit()
    stored_token = test_db.query(PasswordResetToken).filter_by(token_hash=hash_token(raw_token)).one()
    assert stored_token.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)

    response = client.post(
        '/auth/password-reset/confirm',
        json={'token': raw_token, 'password': 'NewPassword', 'confirm_password': 'NewPassword'},
    )

    assert response.status_code == 400
    assert 'invalid or has expired' in response.json()['detail']


def test_password_reset_revokes_existing_sessions_and_email_is_generic(
    client,
    sample_user,
    monkeypatch,
    test_db,
):
    monkeypatch.setenv('APP_BASE_URL', 'https://example.com')
    sent = []
    monkeypatch.setattr(
        'app.routers.auth.send_password_reset_email',
        lambda recipient, reset_url: sent.append((recipient, reset_url)),
    )
    from app.routers import auth
    auth._recovery_attempts.clear()

    response = client.post(
        '/auth/password-reset/request-email',
        json={'email': sample_user.email},
    )
    unknown_response = client.post(
        '/auth/password-reset/request-email',
        json={'email': 'unknown@example.com'},
    )

    assert response.status_code == unknown_response.status_code == 202
    assert response.json() == unknown_response.json()
    assert sent[0][0] == sample_user.email

    client.post(
        '/auth/token',
        data={'username': sample_user.email, 'password': 'Password', 'client_id': 'remember'},
    )
    token = sent[0][1].split('token=', 1)[1]
    reset = client.post(
        '/auth/password-reset/confirm',
        json={'token': token, 'password': 'NewPassword', 'confirm_password': 'NewPassword'},
    )
    assert reset.status_code == 200
    assert test_db.query(AuthSession).filter(
        AuthSession.user_id == sample_user.id,
        AuthSession.revoked_at.is_(None),
    ).count() == 0


def test_forgot_password_page_contains_valid_submit_flow(client):
    response = client.get('/auth/forgot-password-page')

    assert response.status_code == 200
    html = response.text
    assert 'event.preventDefault();' in html
    assert "requestJson('/auth/password-recovery/start', {email})" in html
    assert "recovery.method === 'security_questions'" in html
    assert "window.location.href = '/auth/reset-password-page?token='" in html






