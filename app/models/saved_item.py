"""
SavedItem model.

A saved item is a lightweight, user-owned bookmark of something the user wants
to revisit from their dashboard — for example a Guide Designer construct or a
plasmid, together with the per-level MoClo reaction fragment lists so the user
can re-open the reaction calculator later.

The `summary` field is a free-form JSON blob (same convention as
FinalPlasmid.metadata). It typically holds:
    {
        "reactions": [
            {"label": "Level 2", "level": "2", "enzyme": "BpiI",
             "fragments": [{"name": ..., "size": ..., "role": "vector"|"insert"}, ...]},
            ...
        ],
        "records": {"plasmid_id": ..., "l1_plasmid_id": ..., ...}   # optional links
    }
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.models.database import get_connection


class SavedItem:
    def __init__(
        self,
        id: str,
        user_id: str,
        item_type: str,
        title: str,
        summary: Optional[Dict[str, Any]] = None,
        ref_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        self.id = id
        self.user_id = user_id
        self.item_type = item_type
        self.title = title
        self.summary = summary or {}
        self.ref_id = ref_id
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'item_type': self.item_type,
            'title': self.title,
            'summary': self.summary,
            'ref_id': self.ref_id,
            'created_at': self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
        }

    @staticmethod
    def create(
        user_id: str,
        item_type: str,
        title: str,
        summary: Optional[Dict[str, Any]] = None,
        ref_id: Optional[str] = None,
    ) -> 'SavedItem':
        if not user_id:
            raise ValueError("user_id is required")
        if not title or not title.strip():
            raise ValueError("title is required")

        item = SavedItem(
            id=str(uuid.uuid4()),
            user_id=user_id,
            item_type=(item_type or 'item').strip(),
            title=title.strip(),
            summary=summary or {},
            ref_id=ref_id,
        )

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO saved_items (id, user_id, item_type, ref_id, title, summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                item.id, item.user_id, item.item_type, item.ref_id, item.title,
                json.dumps(item.summary), item.created_at.isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return item

    @staticmethod
    def _from_row(row) -> 'SavedItem':
        created = row[6]
        try:
            created = datetime.fromisoformat(created) if created else None
        except (ValueError, TypeError):
            created = None
        return SavedItem(
            id=row[0],
            user_id=row[1],
            item_type=row[2],
            ref_id=row[3],
            title=row[4],
            summary=json.loads(row[5]) if row[5] else {},
            created_at=created,
        )

    @staticmethod
    def get_by_user(user_id: str) -> List['SavedItem']:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT id, user_id, item_type, ref_id, title, summary, created_at
            FROM saved_items WHERE user_id = ?
            ORDER BY created_at DESC
            ''',
            (user_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [SavedItem._from_row(r) for r in rows]

    @staticmethod
    def get_by_id(item_id: str) -> Optional['SavedItem']:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT id, user_id, item_type, ref_id, title, summary, created_at
            FROM saved_items WHERE id = ?
            ''',
            (item_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return SavedItem._from_row(row) if row else None

    def delete(self) -> None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM saved_items WHERE id = ?', (self.id,))
        conn.commit()
        conn.close()
