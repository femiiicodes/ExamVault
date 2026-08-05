def test_get_user_details(authenticated_client):
    response = authenticated_client.get('/users/show-user-details')
    assert response.status_code == 200
    assert response.json() == {'id': 1, 'first_name': 'Femi', 'last_name': 'Adewusi', 'email': 'adefemiadewusi07@gmail.com', 'level': '300', 'department': 'EIE', 'role': 'admin'}

def test_change_password(authenticated_client):
    response = authenticated_client.put('/users/change-password', params ={'old_password':'Password',
                                                     'new_password':'New Password'})
    assert response ==  204
    
    
