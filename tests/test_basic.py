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


def test_the_about_and_help_pages_are_there_and_point_at_each_other(client):
    for path, heading in (('/about', 'MoClo Library Tool'), ('/help', 'How to use the MoClo Library Tool')):
        r = client.get(path)
        assert r.status_code == 200, path
        assert heading in r.get_data(as_text=True)
    assert '/help' in client.get('/about').get_data(as_text=True)
    assert '/about' in client.get('/help').get_data(as_text=True)
