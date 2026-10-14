"""
Signing in through the Gardiner Lab suite (SUITE_AUTH=proxy).

The suite's proxy names the signed-in user in X-Suite-User. MoClo follows it:
no header, nobody signed in; a header, that user. Off unless set, so a
standalone MoClo keeps its own sign-in.
"""

import pytest

from app.models.user import User


@pytest.fixture
def suite(monkeypatch):
    monkeypatch.setenv('SUITE_AUTH', 'proxy')
    monkeypatch.setenv('SUITE_LOGIN_URL', '/account/login')
    monkeypatch.setenv('SUITE_LOGOUT_URL', '/account/logout')
    User.create('alice', 'password123')
    User.create('boss', 'password123', is_admin=True)


def as_user(username):
    return {'X-Suite-User': username}


def test_the_suite_user_is_signed_in(suite, client):
    r = client.get('/api/auth/session', headers=as_user('alice'))
    body = r.get_json()
    assert body['authenticated'] is True
    assert body['user']['username'] == 'alice'
    assert client.get('/parts', headers=as_user('alice')).status_code == 200


def test_protected_api_routes_accept_the_suite_user(suite, client):
    assert client.get('/api/me/account', headers=as_user('alice')).status_code == 200
    assert client.get('/api/me/account').status_code == 401


def test_no_header_means_nobody(suite, client):
    client.get('/parts', headers=as_user('alice'))
    # Signed out of the suite: the next request has no header.
    assert client.get('/api/auth/session').get_json()['authenticated'] is False
    r = client.get('/parts')
    assert r.status_code == 302


def test_switching_users_follows_the_suite(suite, client):
    client.get('/parts', headers=as_user('alice'))
    body = client.get('/api/auth/session', headers=as_user('boss')).get_json()
    assert body['user']['username'] == 'boss'


def test_an_unknown_user_is_nobody(suite, client):
    assert client.get('/api/auth/session',
                      headers=as_user('mallory')).get_json()['authenticated'] is False


def test_administrator_status_follows_the_directory(suite, client):
    client.get('/parts', headers=as_user('alice'))
    User.get_by_username('alice').update(is_admin=True)
    client.get('/parts', headers=as_user('alice'))
    with client.session_transaction() as flask_session:
        assert flask_session['is_admin'] is True


def test_sign_in_and_out_go_to_the_suite(suite, client):
    r = client.get('/login')
    assert r.status_code == 302
    assert r.headers['Location'].startswith('/account/login?next=')
    r = client.get('/login?next=/plasmids')
    assert r.headers['Location'] == '/account/login?next=/plasmids'
    r = client.get('/logout', headers=as_user('alice'))
    assert r.headers['Location'] == '/account/logout'


def test_moclo_has_no_sign_in_of_its_own(suite, client):
    r = client.post('/api/auth/login', json={'username': 'alice', 'password': 'password123'})
    assert r.status_code == 403
    assert r.get_json()['login_url'] == '/account/login'


def test_standalone_ignores_the_header(monkeypatch, client):
    monkeypatch.delenv('SUITE_AUTH', raising=False)
    User.create('alice', 'password123')
    assert client.get('/api/auth/session',
                      headers=as_user('alice')).get_json()['authenticated'] is False
    assert client.get('/login').status_code == 200
    r = client.post('/api/auth/login', json={'username': 'alice', 'password': 'password123'})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# The suite's dashboard
# ---------------------------------------------------------------------------

def test_dashboard_and_admin_go_to_the_suites(suite, client):
    r = client.get('/dashboard', headers=as_user('alice'))
    assert r.status_code == 302 and r.headers['Location'] == '/account/#moclo-parts'
    r = client.get('/admin', headers=as_user('boss'))
    assert r.status_code == 302 and r.headers['Location'] == '/account/#moclo-library'
    page = client.get('/parts', headers=as_user('boss')).get_data(as_text=True)
    assert 'href="/account/"' in page and 'href="/account/#moclo-library"' in page


def test_embedded_pages_leave_out_moclos_navigation(suite, client):
    page = client.get('/admin?embed=1&tab=parts', headers=as_user('boss')).get_data(as_text=True)
    assert 'class="navbar"' not in page
    assert '<base target="_top">' in page
    assert 'data-tab="users"' not in page          # accounts are the suite's
    assert 'data-tab="parts"' in page
    page = client.get('/dashboard?embed=1&tab=saved', headers=as_user('alice')).get_data(as_text=True)
    assert 'class="navbar"' not in page
    assert 'acc-save' not in page                  # so is your account
    assert 'class="dash-tabs" style="display:none"' in page   # one section per dashboard tab


def test_the_manifest_lists_moclos_tabs(suite, client):
    tabs = client.get('/suite-manifest.json').get_json()['tabs']
    assert {t['id'] for t in tabs} == {'moclo-parts', 'moclo-saved', 'moclo-library'}
    assert next(t for t in tabs if t['id'] == 'moclo-library')['roles'] == ['admin']


def test_accounts_cannot_be_managed_here(suite, client):
    boss = as_user('boss')
    assert client.get('/api/admin/users', headers=boss).status_code == 403
    assert client.post('/api/admin/users', headers=boss,
                       json={'username': 'x', 'password': 'password123'}).status_code == 403
    assert client.get('/api/admin/parts', headers=boss).status_code == 200
    r = client.put('/api/me/account', headers=as_user('alice'), json={'username': 'alicia'})
    assert r.status_code == 403
    assert User.get_by_username('alice') is not None


def test_standalone_keeps_its_own_dashboards(monkeypatch, client):
    monkeypatch.delenv('SUITE_AUTH', raising=False)
    User.create('alice', 'password123')
    client.post('/api/auth/login', json={'username': 'alice', 'password': 'password123'})
    page = client.get('/dashboard?embed=1').get_data(as_text=True)
    assert 'class="navbar"' in page and 'acc-save' in page
