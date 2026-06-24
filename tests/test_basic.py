"""
Basic tests to verify the application setup.
"""

import pytest


@pytest.mark.unit
def test_app_exists(app):
    """Test that the Flask app instance is created."""
    assert app is not None


@pytest.mark.unit
def test_app_is_testing(app):
    """Test that the app is in testing mode."""
    assert app.config['TESTING'] is True


@pytest.mark.unit
def test_index_route(client):
    """Test the index route redirects to login when not authenticated."""
    response = client.get('/')
    assert response.status_code == 302
    assert '/login' in response.location


@pytest.mark.unit
def test_health_route(client):
    """Test the health check route."""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
