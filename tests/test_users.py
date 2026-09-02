def test_get_user_details(authenticated_client, sample_user):
    response = authenticated_client.get('/users/show-user-details')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == sample_user.id
    assert data['first_name'] == 'Femi'
    assert data['last_name'] == 'Adewusi'
    assert data['email'] == 'adefemiadewusi07@gmail.com'
    assert data['level'] == '300'
    assert data['programme_id'] == sample_user.programme_id
    assert data['role'] == 'admin'

def test_change_password(authenticated_client):
    response = authenticated_client.put('/users/change-password', params ={'old_password':'Password',
                                                     'new_password':'New Password'})
    assert response.status_code == 204
    
    
