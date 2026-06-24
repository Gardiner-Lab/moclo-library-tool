"""
Cassette model with CRUD operations for assembled MoClo constructs.
"""

import uuid
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.database import get_database


class Cassette:
    """Cassette model representing an assembled construct from multiple parts."""
    
    def __init__(
        self,
        id: str,
        name: str,
        owner_id: str,
        part_ids: List[str],
        assembled_sequence: str,
        created_at: Optional[str] = None,
        level: Optional[str] = None,
        translation_data: Optional[Dict[str, Any]] = None,
        parts_metadata: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Initialize a Cassette instance.
        
        Args:
            id: Unique identifier (UUID)
            name: Cassette name
            owner_id: ID of the user who owns this cassette
            part_ids: Ordered list of part IDs that make up this cassette
            assembled_sequence: Complete DNA sequence of the assembled cassette
            created_at: Timestamp of cassette creation (ISO format)
            level: MoClo level of this cassette ('0', '1', '2')
            translation_data: Persisted translation analysis from assembly
            parts_metadata: Snapshot of part info at assembly time (type, name, overhangs, introns)
        """
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.part_ids = part_ids
        self.assembled_sequence = assembled_sequence
        self.created_at = created_at
        self.level = level
        self.translation_data = translation_data
        self.parts_metadata = parts_metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert cassette to dictionary representation.
        
        Returns:
            Dictionary with cassette data
        """
        data = {
            'id': self.id,
            'name': self.name,
            'owner_id': self.owner_id,
            'part_ids': self.part_ids,
            'assembled_sequence': self.assembled_sequence,
            'created_at': self.created_at,
            'length': len(self.assembled_sequence),
            'part_count': len(self.part_ids),
            'level': self.level
        }
        if self.translation_data:
            data['translation_data'] = self.translation_data
        if self.parts_metadata:
            data['parts_metadata'] = self.parts_metadata
        return data
    
    @staticmethod
    def create(
        name: str,
        owner_id: str,
        part_ids: List[str],
        assembled_sequence: str,
        level: Optional[str] = None,
        translation_data: Optional[Dict[str, Any]] = None,
        parts_metadata: Optional[List[Dict[str, Any]]] = None
    ) -> 'Cassette':
        """
        Create a new cassette in the database.
        
        Args:
            name: Cassette name
            owner_id: ID of the user who owns this cassette
            part_ids: Ordered list of part IDs that make up this cassette
            assembled_sequence: Complete DNA sequence of the assembled cassette
            level: MoClo level ('0', '1', etc.)
            translation_data: Translation analysis to persist
            parts_metadata: Snapshot of part info at assembly time
            
        Returns:
            Created Cassette instance
            
        Raises:
            ValueError: If validation fails
        """
        # Validate inputs
        Cassette._validate_cassette_data(name, owner_id, part_ids, assembled_sequence)
        
        # Generate unique ID
        cassette_id = str(uuid.uuid4())
        
        # Convert to JSON for storage
        part_ids_json = json.dumps(part_ids)
        translation_data_json = json.dumps(translation_data) if translation_data else None
        parts_metadata_json = json.dumps(parts_metadata) if parts_metadata else None
        
        # Insert into database
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert new cassette
            cursor.execute(
                """
                INSERT INTO cassettes (
                    id, name, owner_id, part_ids, assembled_sequence, 
                    level, translation_data, parts_metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cassette_id, name, owner_id, part_ids_json, assembled_sequence, 
                 level, translation_data_json, parts_metadata_json)
            )
            
            # Retrieve the created cassette
            cursor.execute(
                "SELECT * FROM cassettes WHERE id = ?",
                (cassette_id,)
            )
            row = cursor.fetchone()
            
            return Cassette._from_row(row)
    
    @staticmethod
    def get_by_id(cassette_id: str) -> Optional['Cassette']:
        """
        Retrieve a cassette by ID.
        
        Args:
            cassette_id: Cassette ID to look up
            
        Returns:
            Cassette instance if found, None otherwise
        """
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cassettes WHERE id = ?",
                (cassette_id,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return Cassette._from_row(row)
    
    @staticmethod
    def get_by_owner(owner_id: str) -> List['Cassette']:
        """
        Retrieve all cassettes owned by a specific user.
        
        Args:
            owner_id: User ID to filter by
            
        Returns:
            List of Cassette instances owned by the user
        """
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cassettes WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,)
            )
            rows = cursor.fetchall()
            
            return [Cassette._from_row(row) for row in rows]
    
    @staticmethod
    def get_all() -> List['Cassette']:
        """
        Retrieve all cassettes from the database.
        
        Note: This method is primarily for testing/admin purposes.
        In production, use get_by_owner() to respect user isolation.
        
        Returns:
            List of all Cassette instances
        """
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cassettes ORDER BY created_at DESC")
            rows = cursor.fetchall()
            
            return [Cassette._from_row(row) for row in rows]
    
    def delete(self) -> None:
        """
        Delete this cassette from the database.
        """
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM cassettes WHERE id = ?",
                (self.id,)
            )
    
    def update_name(self, new_name: str) -> None:
        """
        Update the cassette name.
        
        Args:
            new_name: New name for the cassette
            
        Raises:
            ValueError: If name is empty
        """
        if not new_name or not new_name.strip():
            raise ValueError("Cassette name cannot be empty")
        
        db = get_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE cassettes SET name = ? WHERE id = ?",
                (new_name, self.id)
            )
        
        self.name = new_name
    
    @staticmethod
    def _from_row(row) -> 'Cassette':
        """
        Create a Cassette instance from a database row.
        
        Args:
            row: Database row (sqlite3.Row)
            
        Returns:
            Cassette instance
        """
        # Parse part_ids from JSON string
        part_ids = json.loads(row['part_ids'])
        
        # Safely get optional columns (may not exist in older databases)
        level = None
        translation_data = None
        parts_metadata = None
        try:
            level = row['level']
        except (KeyError, IndexError):
            pass
        try:
            td_raw = row['translation_data']
            if td_raw:
                translation_data = json.loads(td_raw)
        except (KeyError, IndexError):
            pass
        try:
            pm_raw = row['parts_metadata']
            if pm_raw:
                parts_metadata = json.loads(pm_raw)
        except (KeyError, IndexError):
            pass
        
        return Cassette(
            id=row['id'],
            name=row['name'],
            owner_id=row['owner_id'],
            part_ids=part_ids,
            assembled_sequence=row['assembled_sequence'],
            created_at=row['created_at'],
            level=level,
            translation_data=translation_data,
            parts_metadata=parts_metadata
        )
    
    @staticmethod
    def _validate_cassette_data(
        name: str,
        owner_id: str,
        part_ids: List[str],
        assembled_sequence: str
    ) -> None:
        """
        Validate cassette data before creation.
        
        Args:
            name: Cassette name
            owner_id: Owner user ID
            part_ids: List of part IDs
            assembled_sequence: Assembled DNA sequence
            
        Raises:
            ValueError: If any validation fails
        """
        # Validate name
        if not name or not name.strip():
            raise ValueError("Cassette name cannot be empty")
        
        # Validate owner_id
        if not owner_id or not owner_id.strip():
            raise ValueError("Owner ID cannot be empty")
        
        # Validate part_ids
        if not part_ids or len(part_ids) < 2:
            raise ValueError("Cassette must contain at least 2 parts")
        
        # Validate assembled_sequence
        if not assembled_sequence or not assembled_sequence.strip():
            raise ValueError("Assembled sequence cannot be empty")
        
        # Validate that assembled_sequence contains only valid DNA bases
        if not all(base in 'ATCG' for base in assembled_sequence.upper()):
            raise ValueError("Assembled sequence must contain only A, T, C, G characters")
    
    def __repr__(self) -> str:
        """String representation of Cassette."""
        return (
            f"Cassette(id='{self.id}', name='{self.name}', "
            f"owner_id='{self.owner_id}', parts={len(self.part_ids)})"
        )
    
    def __eq__(self, other) -> bool:
        """Check equality based on cassette ID."""
        if not isinstance(other, Cassette):
            return False
        return self.id == other.id
