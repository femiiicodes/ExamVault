from datetime import datetime
import hashlib
import hmac
import json

from app.models import AcademicPeriod, AcademicPeriodSwitch, Entitlement, Payment, Pq
from app.services.payments import PAYMENT_AMOUNT


def test_admin_can_create_and_activate_first_period(authenticated_client, sample_user, test_db):
    response = authenticated_client.post(
        '/admin/academic-periods',
        json={'academic_session': '2026/2027', 'semester': 'First Semester'},
    )
    assert response.status_code == 200
    period = test_db.query(AcademicPeriod).one()

    response = authenticated_client.post(
        '/admin/academic-periods/switch',
        json={
            'academic_session': period.academic_session,
            'semester': period.semester,
            'password': 'Password',
            'confirmation': True,
        },
    )
    assert response.status_code == 200
    assert test_db.query(AcademicPeriod).filter(AcademicPeriod.is_active.is_(True)).one().id == period.id
    assert test_db.query(AcademicPeriodSwitch).count() == 1


def test_unpaid_student_is_blocked_from_download(authenticated_client, sample_user, sample_pq, test_db):
    sample_user.role = 'user'
    period = AcademicPeriod(
        academic_session='2026/2027',
        semester='First Semester',
        is_active=True,
        created_at=datetime.utcnow(),
    )
    test_db.add(period)
    test_db.commit()

    response = authenticated_client.get('/pqs/download_file', params={'id': sample_pq.id})
    assert response.status_code == 402


def test_free_view_limit_is_global_and_reopening_is_free(
    authenticated_client, sample_user, sample_pq, test_db, monkeypatch
):
    sample_user.role = 'user'
    period = AcademicPeriod(
        academic_session='2026/2027',
        semester='First Semester',
        is_active=True,
        created_at=datetime.utcnow(),
    )
    second = Pq(
        session='23/24',
        assessment_type='Test 2',
        level='300',
        course_id=sample_pq.course_id,
        file_name='second.pdf',
        file_key='second.pdf',
        time_created=datetime.utcnow(),
        uploader_id=sample_user.id,
    )
    third = Pq(
        session='23/24',
        assessment_type='Examination',
        level='300',
        course_id=sample_pq.course_id,
        file_name='third.pdf',
        file_key='third.pdf',
        time_created=datetime.utcnow(),
        uploader_id=sample_user.id,
    )
    test_db.add_all([period, second, third])
    test_db.commit()

    class FakeBody:
        def iter_chunks(self, chunk_size):
            yield b'%PDF-test'

        def close(self):
            pass

    from app.routers import pqs
    monkeypatch.setattr(pqs, 'get_file_metadata', lambda object_key: {'ContentLength': 9})
    monkeypatch.setattr(pqs, 'get_file', lambda object_key, byte_range=None: {'Body': FakeBody()})

    assert authenticated_client.get('/pqs/view_file', params={'id': sample_pq.id}).status_code == 200
    assert authenticated_client.get('/pqs/view_file', params={'id': sample_pq.id}).status_code == 200
    assert authenticated_client.get('/pqs/view_file', params={'id': second.id}).status_code == 200
    assert authenticated_client.get('/pqs/view_file', params={'id': third.id}).status_code == 402


def test_paid_user_can_view_pdf_without_consuming_free_view(
    authenticated_client, sample_user, sample_pq, test_db, monkeypatch
):
    sample_user.role = 'user'
    period = AcademicPeriod(
        academic_session='2026/2027',
        semester='First Semester',
        is_active=True,
        created_at=datetime.utcnow(),
    )
    test_db.add(period)
    test_db.commit()
    payment = Payment(
        user_id=sample_user.id,
        academic_period_id=period.id,
        reference='paid-view-reference',
        amount=PAYMENT_AMOUNT,
        currency='NGN',
        status='success',
        created_at=datetime.utcnow(),
    )
    test_db.add(payment)
    test_db.commit()
    test_db.add(Entitlement(
        user_id=sample_user.id,
        academic_period_id=period.id,
        payment_id=payment.id,
        status='active',
        created_at=datetime.utcnow(),
    ))
    test_db.commit()

    class FakeBody:
        def iter_chunks(self, chunk_size):
            yield b'%PDF-test'

        def close(self):
            pass

    from app.routers import pqs
    monkeypatch.setattr(pqs, 'get_file_metadata', lambda object_key: {'ContentLength': 9})
    monkeypatch.setattr(
        pqs,
        'get_file',
        lambda object_key, byte_range=None: {'Body': FakeBody(), 'ContentLength': 9},
    )

    response = authenticated_client.get('/pqs/view_file', params={'id': sample_pq.id})

    assert response.status_code == 200
    assert test_db.query(Entitlement).count() == 1


def test_webhook_signature_is_required(client, monkeypatch):
    monkeypatch.setenv('PAYSTACK_WEBHOOK_SECRET', 'webhook-secret')
    payload = {'event': 'charge.success', 'data': {}}
    response = client.post('/webhooks/paystack', content=json.dumps(payload))
    assert response.status_code == 400


def test_successful_payment_fulfillment_is_idempotent(test_db, sample_user):
    period = AcademicPeriod(
        academic_session='2026/2027',
        semester='Second Semester',
        is_active=True,
        created_at=datetime.utcnow(),
    )
    payment = Payment(
        user_id=sample_user.id,
        academic_period_id=period.id if period.id else 1,
        reference='reference-1',
        amount=PAYMENT_AMOUNT,
        currency='NGN',
        status='pending',
        created_at=datetime.utcnow(),
    )
    test_db.add(period)
    test_db.flush()
    payment.academic_period_id = period.id
    test_db.add(payment)
    test_db.commit()

    from app.services.payments import fulfill_payment
    fulfill_payment(
        test_db,
        'reference-1',
        paystack_status='success',
        amount=PAYMENT_AMOUNT,
        currency='NGN',
        transaction_id='tx-1',
    )
    fulfill_payment(
        test_db,
        'reference-1',
        paystack_status='success',
        amount=PAYMENT_AMOUNT,
        currency='NGN',
        transaction_id='tx-1',
    )
    assert test_db.query(Entitlement).filter(
        Entitlement.user_id == sample_user.id,
        Entitlement.academic_period_id == period.id,
    ).count() == 1
