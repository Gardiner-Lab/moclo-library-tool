"""
Settings for running inside Trellis Tools.

All of them are off unless set, so a standalone MoClo behaves exactly as before:

    SUITE_HOME_URL     a "Lab tools" link back to the suite's landing page
    REGISTRATION_URL   accounts are created on the suite's registration page
    ADMIN_PASSWORD     the first admin's password, instead of the published default
"""

from app.init_db import DEFAULT_ADMIN_PASSWORD, _ensure_default_admin
from app.models.user import User


def test_standalone_pages_are_unchanged(monkeypatch, client):
    monkeypatch.delenv('SUITE_HOME_URL', raising=False)
    monkeypatch.delenv('REGISTRATION_URL', raising=False)
    page = client.get('/login').get_data(as_text=True)
    assert 'navbar-home' not in page
    assert 'href="/register"' in page
    assert client.get('/register').status_code == 200


def test_lab_tools_link(monkeypatch, client):
    monkeypatch.setenv('SUITE_HOME_URL', '/')
    page = client.get('/login').get_data(as_text=True)
    assert 'class="navbar-home"' in page
    assert 'Lab tools' in page


def test_registration_goes_to_the_suite(monkeypatch, client):
    monkeypatch.setenv('REGISTRATION_URL', '/editor/login?register')
    page = client.get('/login').get_data(as_text=True)
    assert 'href="/editor/login?register"' in page
    assert 'href="/register"' not in page

    r = client.get('/register')
    assert r.status_code == 302
    assert r.headers['Location'].endswith('/editor/login?register')

    # The suite's page asks for the lab and its code; this one must not be a way round it.
    r = client.post('/api/auth/register', json={'username': 'mallory', 'password': 'password123'})
    assert r.status_code == 403
    assert User.get_by_username('mallory') is None


def test_registration_still_works_standalone(monkeypatch, client):
    monkeypatch.delenv('REGISTRATION_URL', raising=False)
    r = client.post('/api/auth/register', json={'username': 'alice', 'password': 'password123'})
    assert r.status_code == 201


def test_admin_password_from_the_environment(monkeypatch):
    monkeypatch.setenv('ADMIN_PASSWORD', 'a-real-password')
    _ensure_default_admin()
    admin = User.get_by_username('admin')
    assert admin.is_admin
    assert User.verify_password('a-real-password', admin.password_hash)
    assert not User.verify_password(DEFAULT_ADMIN_PASSWORD, admin.password_hash)


def test_the_default_admin_password_without_it(monkeypatch):
    monkeypatch.delenv('ADMIN_PASSWORD', raising=False)
    _ensure_default_admin()
    assert User.verify_password(DEFAULT_ADMIN_PASSWORD, User.get_by_username('admin').password_hash)


def test_an_existing_admin_is_left_alone(monkeypatch):
    User.create('admin', 'the-labs-own', is_admin=True)
    monkeypatch.setenv('ADMIN_PASSWORD', 'something-else')
    _ensure_default_admin()
    assert User.verify_password('the-labs-own', User.get_by_username('admin').password_hash)
