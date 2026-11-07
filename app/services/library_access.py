"""
Who sees what in the MoClo library, inside Trellis Tools.

A part, backbone or assembled plasmid belongs to the labs of the person who
added it (a part's contributor, a backbone's or plasmid's owner). It is seen by:

* its chair group: every lab in a chair group with one of those labs (labs that
  work together, set by an administrator on the suite's dashboard). A lab in no
  chair group keeps its records to itself;
* the chair groups its chair group shares its library with (`library_shares`,
  below): read-only, like the rest of the chair group. A lab admin of one of the
  chair group's labs (or an administrator) decides that;
* everyone, when it is a reference record: a public kit rather than a lab's own
  work. The built-in MoClo toolkit (contributor "system", or owned by the
  "system" account) always is; others are marked in `library_reference` (the
  bundled Plant MoClo kit, when it is loaded; every part and backbone an
  administrator adds, as it is added; and whatever else an administrator marks);
* administrators, always.

The suite's teaching demo (its chair group is the suite.db setting
'demo.chair_group') is kept to itself: its accounts see the demo's records and
the kits MoClo ships with, never another chair group's library or what an
administrator added. See in_demo().

Changing a record stays with its owner (and administrators), as before.

Outside the suite (no SUITE_DATABASE_PATH, or a suite from before labs) there
are no labs to go by, and everyone sees everything, as before.

Labs and chair groups are the suite's, read from suite.db and never written.
The two tables here are MoClo's own, in moclo.db:

    library_reference (kind, record_id)       records everyone sees
    library_shares    (from_group, to_group)  chair group from_group's library
                                              is seen by chair group to_group

The Sequence Editor reads moclo.db directly for its MoClo library card, and
applies this same rule (plasmid-editor app/services/moclo_bridge.py); keep the
two in step.
"""

import os
import sqlite3
import threading
from typing import Dict, Iterable, List, Optional, Set, Tuple

KINDS = ('part', 'backbone', 'plasmid')
SYSTEM = 'system'
# The bundled Plant MoClo kit's parts (app/init_db.py): a public Addgene kit.
PLANT_KIT_SOURCE = 'Plant MoClo (Addgene #1000000044)'

SCHEMA = """
CREATE TABLE IF NOT EXISTS library_reference (
    kind TEXT NOT NULL,
    record_id TEXT NOT NULL,
    marked_by TEXT,
    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (kind, record_id)
);
CREATE TABLE IF NOT EXISTS library_flags (
    name TEXT PRIMARY KEY,
    set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS library_shares (
    from_group TEXT NOT NULL,
    to_group TEXT NOT NULL,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (from_group, to_group)
);
"""

_lock = threading.Lock()
_suite_cache: Tuple[Optional[tuple], dict] = (None, {})


# ---------------------------------------------------------------------------
# The suite's labs and chair groups (read-only)
# ---------------------------------------------------------------------------

def _suite_path() -> str:
    return os.environ.get('SUITE_DATABASE_PATH', '/suite/suite.db')


def _read_suite() -> dict:
    """
    {'labs_of': username -> {lab name (casefolded)}, 'leads': username -> {lab},
     'group_of': lab -> chair group id or None, 'groups': {id: name}}, or {}
    outside the suite. Cached until suite.db changes.
    """
    global _suite_cache
    path = _suite_path()
    try:
        info = os.stat(path)
        stamp = (info.st_mtime_ns, info.st_size)
    except OSError:
        return {}
    with _lock:
        if _suite_cache[0] == stamp:
            return _suite_cache[1]
        try:
            conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=5)
            try:
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                if 'labs' not in tables or not ({'lab_members', 'members'} & tables):
                    found: dict = {}
                else:
                    lab_cols = {r[1] for r in conn.execute('PRAGMA table_info(labs)')}
                    labs = conn.execute(
                        'SELECT id, name, chair_group_id FROM labs' if 'chair_group_id' in lab_cols
                        else 'SELECT id, name, NULL FROM labs').fetchall()
                    member_table = 'lab_members' if 'lab_members' in tables else 'members'
                    member_cols = {r[1] for r in conn.execute(f'PRAGMA table_info({member_table})')}
                    # A lab admin is a lab lead with lab_admin set (the suite's portal/labs.py).
                    admin_col = 'lab_admin' if 'lab_admin' in member_cols else '0'
                    members = conn.execute(f'SELECT username, lab_id, role, {admin_col} FROM {member_table}').fetchall()
                    groups = dict(conn.execute('SELECT id, name FROM chair_groups').fetchall()) \
                        if 'chair_groups' in tables else {}
                    name_of = {lab_id: (name or '').casefold() for lab_id, name, _ in labs}
                    # The teaching demo's chair group (the suite's demo/accounts.py records it).
                    demo = conn.execute("SELECT value FROM settings WHERE key = 'demo.chair_group'").fetchone()                         if 'settings' in tables else None
                    found = {'labs_of': {}, 'leads': {}, 'lab_admins': {}, 'groups': groups,
                             'demo_group': demo[0] if demo and demo[0] else None,
                             'group_of': {(name or '').casefold(): group for _, name, group in labs if name}}
                    for username, lab_id, role, lab_admin in members:
                        lab = name_of.get(lab_id)
                        if not username or not lab:
                            continue
                        found['labs_of'].setdefault(username, set()).add(lab)
                        if role == 'lab_lead':
                            found['leads'].setdefault(username, set()).add(lab)
                            if lab_admin:
                                found['lab_admins'].setdefault(username, set()).add(lab)
            finally:
                conn.close()
        except sqlite3.Error:
            return _suite_cache[1]
        _suite_cache = (stamp, found)
        return found


def enabled() -> bool:
    """Inside a suite with labs: the chair-group rule applies."""
    return bool(_read_suite())


def labs_of(username: Optional[str]) -> Set[str]:
    return set(_read_suite().get('labs_of', {}).get(username or '', set()))


def groups_of(username: Optional[str]) -> Set[str]:
    """The chair groups this person's labs are in."""
    group_of = _read_suite().get('group_of', {})
    return {group_of.get(lab) for lab in labs_of(username)} - {None}


def chair_groups() -> Dict[str, str]:
    """Every chair group in the suite: id -> name."""
    return dict(_read_suite().get('groups', {}))


def can_manage_shares(user, group_id: str) -> bool:
    """
    Administrators, and the lab admins of a lab in the chair group, share its library with other
    chair groups. A lab lead who is not the lab's admin does not: sharing a whole chair group's
    library is the lab admin's call, as it is for notebooks.
    """
    if getattr(user, 'is_admin', False):
        return True
    suite = _read_suite()
    group_of = suite.get('group_of', {})
    return any(group_of.get(lab) == group_id for lab in suite.get('lab_admins', {}).get(user.username, set()))


# ---------------------------------------------------------------------------
# MoClo's own tables
# ---------------------------------------------------------------------------

def _connect():
    """moclo.db, committed and closed at the end of the with-block."""
    from app.models.database import get_database
    return get_database().get_connection()


def ensure_schema(cursor) -> None:
    """Create the tables (moclo.db's migrations call this, inside their transaction)."""
    for statement in SCHEMA.split(';'):
        if statement.strip():
            cursor.execute(statement)


def mark_plant_kit(cursor, parts_db_path: Optional[str] = None) -> None:
    """
    Mark the bundled Plant MoClo kit's parts as reference, once: the first time
    they are found. After that an administrator's choice stands, and a restart
    does not mark again a part they un-marked.
    """
    if cursor.execute("SELECT 1 FROM library_flags WHERE name = 'plant_kit_marked'").fetchone():
        return
    path = parts_db_path or os.environ.get('PARTS_DATABASE_PATH', '/data/parts.db')
    if not os.path.exists(path):
        return
    try:
        parts = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=5)
        try:
            ids = [r[0] for r in parts.execute('SELECT id FROM parts WHERE lab_source = ?', (PLANT_KIT_SOURCE,))]
        finally:
            parts.close()
    except sqlite3.Error:
        return
    if not ids:
        return   # not loaded yet: init_db marks them when it loads the kit
    cursor.executemany("INSERT OR IGNORE INTO library_reference (kind, record_id, marked_by) "
                       "VALUES ('part', ?, 'system')", [(i,) for i in ids])
    cursor.execute("INSERT OR IGNORE INTO library_flags (name) VALUES ('plant_kit_marked')")


def reference_ids(kind: str, kits_only: bool = False) -> Set[str]:
    """Records everyone sees; kits_only, just the kits shipped with MoClo (marked by 'system')."""
    try:
        with _connect() as conn:
            return {r[0] for r in conn.execute(
                'SELECT record_id FROM library_reference WHERE kind = ?' + (" AND marked_by = 'system'" if kits_only else ''),
                (kind,))}
    except sqlite3.Error:
        return set()


def in_demo(username: Optional[str]) -> bool:
    """
    In the suite's teaching demo: every lab of theirs is in the demo's chair group. They see the
    demo's records and the kits MoClo ships with, which the demo is built from, and nothing else:
    no other chair group's library, even one shared with theirs, and no part or backbone an
    administrator added or marked.
    """
    suite = _read_suite()
    demo = suite.get('demo_group')
    own = suite.get('labs_of', {}).get(username or '', set())
    return bool(demo and own) and all(suite.get('group_of', {}).get(lab) == demo for lab in own)


def set_reference(kind: str, record_id: str, on: bool, by: str) -> None:
    if kind not in KINDS:
        raise ValueError(f'Unknown kind {kind!r}')
    with _connect() as conn:
        if on:
            conn.execute('INSERT OR IGNORE INTO library_reference (kind, record_id, marked_by) VALUES (?, ?, ?)',
                         (kind, record_id, by))
        else:
            conn.execute('DELETE FROM library_reference WHERE kind = ? AND record_id = ?', (kind, record_id))


def mark_if_administrators(kind: str, record_id: str, owner: Optional[str]) -> bool:
    """
    A part or backbone an administrator adds is public: marked reference, seen by every lab, as the
    built-in kits are. Marked when it is added (not worked out each time), so an administrator can
    still un-mark one, and the Sequence Editor, which reads these marks too, sees the same. Returns
    whether it was marked. Outside the suite everyone sees everything anyway, and nothing is marked.
    """
    if not owner or not enabled():
        return False
    try:
        with _connect() as conn:
            row = conn.execute('SELECT username FROM users WHERE (username = ? OR id = ?) AND is_admin = 1',
                               (owner, owner)).fetchone()
    except sqlite3.Error:
        return False
    if not row or row[0] == SYSTEM:
        return False
    set_reference(kind, record_id, True, row[0])
    return True


def shares() -> List[dict]:
    names = chair_groups()
    try:
        with _connect() as conn:
            rows = conn.execute('SELECT from_group, to_group, created_by, created_at FROM library_shares '
                                'ORDER BY created_at').fetchall()
    except sqlite3.Error:
        return []
    return [{'from_group': f, 'from_name': names.get(f, f), 'to_group': t, 'to_name': names.get(t, t),
             'created_by': by, 'created_at': at} for f, t, by, at in rows]


def add_share(from_group: str, to_group: str, by: str) -> None:
    groups = chair_groups()
    if from_group not in groups or to_group not in groups:
        raise ValueError('Both chair groups must exist in the suite')
    if from_group == to_group:
        raise ValueError('A chair group already sees its own library')
    with _connect() as conn:
        conn.execute('INSERT OR IGNORE INTO library_shares (from_group, to_group, created_by) VALUES (?, ?, ?)',
                     (from_group, to_group, by))


def remove_share(from_group: str, to_group: str) -> None:
    with _connect() as conn:
        conn.execute('DELETE FROM library_shares WHERE from_group = ? AND to_group = ?', (from_group, to_group))


def _groups_sharing_with(groups: Set[str]) -> Set[str]:
    if not groups:
        return set()
    try:
        with _connect() as conn:
            marks = ','.join('?' * len(groups))
            return {r[0] for r in conn.execute(
                f'SELECT from_group FROM library_shares WHERE to_group IN ({marks})', tuple(groups))}
    except sqlite3.Error:
        return set()


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

class Viewer:
    """
    What one person sees. Build one per request (Viewer(user)) and ask it about
    each record: it reads the suite, the shares and the reference marks once.
    """

    def __init__(self, user):
        self.user = user
        self.username = getattr(user, 'username', None)
        self.everything = bool(getattr(user, 'is_admin', False)) or not enabled()
        self._reference: Dict[str, Set[str]] = {}
        self._user_names: Optional[Dict[str, str]] = None
        self.demo = False
        if self.everything:
            self.labs: Set[str] = set()
            return
        suite = _read_suite()
        group_of = suite.get('group_of', {})
        own = labs_of(self.username)
        mine = {group_of.get(lab) for lab in own} - {None}
        self.demo = in_demo(self.username)
        # The demo sees its own chair group's only: not what a real chair group shares with it.
        seen_groups = mine if self.demo else mine | _groups_sharing_with(mine)
        # Their own labs (a lab in no chair group still sees itself), and every
        # lab of their chair groups and of the groups sharing with them.
        self.labs = own | {lab for lab, group in group_of.items() if group in seen_groups}

    def _owner_username(self, who: Optional[str]) -> Optional[str]:
        """A contributor or owner, as a username: older parts recorded a user id."""
        if not who:
            return None
        if self._user_names is None:
            try:
                with _connect() as conn:
                    self._user_names = dict(conn.execute('SELECT id, username FROM users').fetchall())
            except sqlite3.Error:
                self._user_names = {}
        return self._user_names.get(who, who)

    def is_reference(self, kind: str, record_id: str, owner: Optional[str]) -> bool:
        if self._owner_username(owner) == SYSTEM:
            return True
        if kind not in self._reference:
            self._reference[kind] = reference_ids(kind, kits_only=getattr(self, 'demo', False))
        return record_id in self._reference[kind]

    def sees(self, kind: str, record_id: str, owner: Optional[str]) -> bool:
        """owner: a part's contributor, a backbone's or plasmid's owner_id."""
        if self.everything:
            return True
        username = self._owner_username(owner)
        if username and username == self.username:
            return True
        if self.is_reference(kind, record_id, owner):
            return True
        return bool(self.labs & labs_of(username))

    # Conveniences for the model objects
    def sees_part(self, part) -> bool:
        return part is not None and self.sees('part', part.id, part.contributor)

    def sees_backbone(self, backbone) -> bool:
        return backbone is not None and self.sees('backbone', backbone.id, backbone.owner_id)

    def sees_plasmid(self, plasmid) -> bool:
        return plasmid is not None and self.sees('plasmid', plasmid.id, plasmid.owner_id)

    def parts(self, parts: Iterable) -> list:
        return [p for p in parts if self.sees_part(p)]

    def backbones(self, backbones: Iterable) -> list:
        return [b for b in backbones if self.sees_backbone(b)]

    def plasmids(self, plasmids: Iterable) -> list:
        return [p for p in plasmids if self.sees_plasmid(p)]


NOT_YOURS = 'This belongs to a lab outside your chair group'


def current_viewer() -> Viewer:
    """The signed-in person's Viewer, for routes that only check the session."""
    from flask import session
    from app.services.auth import AuthService
    session_id = session.get('session_id')
    user = AuthService.get_user_from_session(session_id) if session_id else None
    return Viewer(user)


def refused():
    """The response for a record outside the person's chair group."""
    from flask import jsonify
    return jsonify({'error': NOT_YOURS}), 403
