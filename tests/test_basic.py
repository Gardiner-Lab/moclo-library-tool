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


def test_the_cassette_card_lets_its_buttons_wrap():
    """
    A fourth export button (SnapGene) once pushed SVG and delete out of the card, which clips what
    overflows it. The row must wrap, and the buttons must keep their own width rather than being
    squeezed to nothing.
    """
    from pathlib import Path
    css = Path('app/templates/cassettes.html').read_text()
    for rule in ('.cassette-actions {', '.detail-actions {'):
        block = css.split(rule, 1)[1].split('}', 1)[0]
        assert 'flex-wrap: wrap' in block, f'{rule} must let its buttons wrap onto another line'
    buttons = css.split('.btn-export {', 1)[1].split('}', 1)[0]
    assert 'flex: 1 1 ' in buttons and 'flex: 1;' not in buttons, \
        'an export button needs a width of its own, so it wraps instead of being cut off'


def test_every_page_reaches_the_suite_and_its_other_tools():
    """The bar must carry the tool switcher, so every tool reaches every other one."""
    from pathlib import Path
    html = Path('app/templates/base.html').read_text()
    assert 'trellis/modules.js' in html, 'the other tools are not linked from the bar'
