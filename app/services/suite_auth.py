"""
Signing in through Trellis Tools.

With SUITE_AUTH=proxy, the suite's proxy says who is signed in, in an
X-Suite-User header it sets on every request (and strips from what the browser
sends). This tool then has no sign-in of its own: before each request, the
Flask session is made to match that header, so every page and API route that
already checks the session keeps working unchanged. Signing out of the suite
signs out here at the next request.

Only enable this behind the suite's proxy. Reachable directly, anyone could set
the header themselves.

    SUITE_AUTH         "proxy" to take the signed-in user from the proxy
    SUITE_LOGIN_URL    the suite's sign-in page        (default /account/login)
    SUITE_LOGOUT_URL   the suite's sign-out address    (default /account/logout)
    SUITE_DASHBOARD_URL the suite's dashboard          (default /account/)

The suite's dashboard is also where accounts and the MoClo library are managed:
it shows MoClo's own Dashboard and Admin pages in its tabs (``?embed=1``, which
leaves out MoClo's navigation), listed in /suite-manifest.json.
"""

import os
from typing import Optional
from urllib.parse import quote

from flask import request, session

from app.models.user import User
from app.services.auth import AuthService

HEADER = 'X-Suite-User'


def enabled() -> bool:
    return os.environ.get('SUITE_AUTH', '').strip().lower() == 'proxy'


def login_url(next_path: Optional[str] = None) -> str:
    base = os.environ.get('SUITE_LOGIN_URL', '').strip() or '/account/login'
    return f'{base}?next={quote(next_path, safe="/")}' if next_path else base


def logout_url() -> str:
    return os.environ.get('SUITE_LOGOUT_URL', '').strip() or '/account/logout'


def dashboard_url(tab: str = '') -> str:
    base = os.environ.get('SUITE_DASHBOARD_URL', '').strip() or '/account/'
    return f'{base}#{tab}' if tab else base


def embedded() -> bool:
    """Shown inside a tab of the suite's dashboard, without MoClo's own navigation."""
    return enabled() and request.args.get('embed') == '1'


# The tabs MoClo adds to the suite's dashboard. "src" is where each one's page is.
MANIFEST = {
    'tool': 'MoClo Library Tool',
    'tabs': [
        {'id': 'moclo-parts', 'title': 'My parts', 'icon': '🧩', 'section': 'me',
         'src': '/dashboard?embed=1&tab=parts'},
        {'id': 'moclo-saved', 'title': 'Saved constructs', 'icon': '⭐', 'section': 'me',
         'src': '/dashboard?embed=1&tab=saved'},
        {'id': 'moclo-library', 'title': 'MoClo library', 'icon': '🧬', 'section': 'admin',
         'roles': ['admin'], 'src': '/admin?embed=1&tab=parts'},
    ],
}


def _sign_out_here() -> None:
    session_id = session.get('session_id')
    if session_id:
        AuthService.logout(session_id)
    session.clear()


def follow_suite_sign_in() -> None:
    """Make this tool's session match whoever the suite says is signed in."""
    if not enabled():
        return
    username = request.headers.get(HEADER, '').strip()
    user = User.get_by_username(username) if username else None
    if user is None:
        if session:
            _sign_out_here()
        return

    session_id = session.get('session_id')
    current = AuthService.get_user_from_session(session_id) if session_id else None
    if current is None or current.id != user.id:
        # Someone new, or a session this process no longer holds (they are
        # kept in memory, so a restart loses them): start one for this user.
        _sign_out_here()
        session['session_id'] = AuthService._create_session(user).session_id
        session['user_id'] = user.id
        session['username'] = user.username
    # Administrator status is the directory's, so a change shows at once.
    session['is_admin'] = user.is_admin
