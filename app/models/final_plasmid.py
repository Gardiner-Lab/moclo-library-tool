"""
Final Plasmid model for assembled MoClo plasmids.

This module provides the FinalPlasmid class for managing complete
plasmids assembled from backbones and cassettes.
"""

import uuid
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.models.database import get_connection


class FinalPlasmid:
    """
    Represents a final assembled MoClo plasmid.
    
    A final plasmid is created by inserting one or more cassettes
    into a backbone vector.
    """
    
    def __init__(
        self,
        id: str,
        name: str,
        owner_id: str,
        backbone_id: str,
        cassette_ids: List[str],
        assembled_sequence: str,
        features: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None
    ):
        """
        Initialize a FinalPlasmid instance.
        
        Args:
            id: Unique identifier
            name: Plasmid name
            owner_id: ID of user who created this plasmid
            backbone_id: ID of the backbone used
            cassette_ids: List of cassette IDs inserted
            assembled_sequence: Final assembled DNA sequence
            features: List of all features (from backbone + cassettes)
            metadata: Additional metadata
            created_at: Creation timestamp
        """
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.backbone_id = backbone_id
        self.cassette_ids = cassette_ids
        self.assembled_sequence = assembled_sequence.upper()
        self.features = features or []
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now(timezone.utc)
    
    @property
    def size(self) -> int:
        """Get the size of the plasmid in base pairs."""
        return len(self.assembled_sequence)
    
    @property
    def cassette_count(self) -> int:
        """Get the number of cassettes in this plasmid."""
        return len(self.cassette_ids)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert plasmid to dictionary representation.
        
        Returns:
            Dictionary with plasmid data
        """
        return {
            'id': self.id,
            'name': self.name,
            'owner_id': self.owner_id,
            'backbone_id': self.backbone_id,
            'cassette_ids': self.cassette_ids,
            'cassette_count': self.cassette_count,
            'assembled_sequence': self.assembled_sequence,
            'size': self.size,
            'features': self.features,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }
    
    @staticmethod
    def create(
        name: str,
        owner_id: str,
        backbone_id: str,
        cassette_ids: List[str],
        assembled_sequence: str,
        features: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'FinalPlasmid':
        """
        Create a new final plasmid and store it in the database.
        
        Args:
            name: Plasmid name
            owner_id: ID of user creating the plasmid
            backbone_id: ID of backbone used
            cassette_ids: List of cassette IDs
            assembled_sequence: Final assembled sequence
            features: List of features
            metadata: Additional metadata
            
        Returns:
            Created FinalPlasmid instance
            
        Raises:
            ValueError: If required fields are invalid
        """
        # Validate inputs
        if not name or not name.strip():
            raise ValueError("Plasmid name cannot be empty")
        
        if not assembled_sequence or not assembled_sequence.strip():
            raise ValueError("Assembled sequence cannot be empty")
        
        if not cassette_ids:
            raise ValueError("At least one cassette is required")
        
        # Generate unique ID
        plasmid_id = str(uuid.uuid4())
        
        # Create plasmid instance
        plasmid = FinalPlasmid(
            id=plasmid_id,
            name=name.strip(),
            owner_id=owner_id,
            backbone_id=backbone_id,
            cassette_ids=cassette_ids,
            assembled_sequence=assembled_sequence.strip(),
            features=features,
            metadata=metadata
        )
        
        # Store in database
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO final_plasmids (
                id, name, owner_id, backbone_id, cassette_ids,
                assembled_sequence, features, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            plasmid.id,
            plasmid.name,
            plasmid.owner_id,
            plasmid.backbone_id,
            json.dumps(plasmid.cassette_ids),
            plasmid.assembled_sequence,
            json.dumps(plasmid.features),
            json.dumps(plasmid.metadata),
            plasmid.created_at.isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        return plasmid
    
    @staticmethod
    def get_by_id(plasmid_id: str) -> Optional['FinalPlasmid']:
        """
        Retrieve a plasmid by its ID.
        
        Args:
            plasmid_id: Plasmid ID to look up
            
        Returns:
            FinalPlasmid instance if found, None otherwise
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, owner_id, backbone_id, cassette_ids,
                   assembled_sequence, features, metadata, created_at
            FROM final_plasmids
            WHERE id = ?
        ''', (plasmid_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return None
        
        return FinalPlasmid(
            id=row[0],
            name=row[1],
            owner_id=row[2],
            backbone_id=row[3],
            cassette_ids=json.loads(row[4]),
            assembled_sequence=row[5],
            features=json.loads(row[6]) if row[6] else [],
            metadata=json.loads(row[7]) if row[7] else {},
            created_at=datetime.fromisoformat(row[8])
        )
    
    @staticmethod
    def get_by_owner(owner_id: str) -> List['FinalPlasmid']:
        """
        Get all plasmids owned by a specific user.
        
        Args:
            owner_id: User ID
            
        Returns:
            List of FinalPlasmid instances
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, owner_id, backbone_id, cassette_ids,
                   assembled_sequence, features, metadata, created_at
            FROM final_plasmids
            WHERE owner_id = ?
            ORDER BY created_at DESC
        ''', (owner_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        plasmids = []
        for row in rows:
            plasmid = FinalPlasmid(
                id=row[0],
                name=row[1],
                owner_id=row[2],
                backbone_id=row[3],
                cassette_ids=json.loads(row[4]),
                assembled_sequence=row[5],
                features=json.loads(row[6]) if row[6] else [],
                metadata=json.loads(row[7]) if row[7] else {},
                created_at=datetime.fromisoformat(row[8])
            )
            plasmids.append(plasmid)
        
        return plasmids
    
    @staticmethod
    def get_all() -> List['FinalPlasmid']:
        """
        Get all plasmids in the database.
        
        Returns:
            List of all FinalPlasmid instances
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, owner_id, backbone_id, cassette_ids,
                   assembled_sequence, features, metadata, created_at
            FROM final_plasmids
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        plasmids = []
        for row in rows:
            plasmid = FinalPlasmid(
                id=row[0],
                name=row[1],
                owner_id=row[2],
                backbone_id=row[3],
                cassette_ids=json.loads(row[4]),
                assembled_sequence=row[5],
                features=json.loads(row[6]) if row[6] else [],
                metadata=json.loads(row[7]) if row[7] else {},
                created_at=datetime.fromisoformat(row[8])
            )
            plasmids.append(plasmid)
        
        return plasmids
    
    def delete(self) -> None:
        """Delete this plasmid from the database."""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM final_plasmids WHERE id = ?', (self.id,))
        
        conn.commit()
        conn.close()
    
    def update(self) -> None:
        """Update this plasmid in the database."""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE final_plasmids
            SET name = ?, assembled_sequence = ?,
                features = ?, metadata = ?
            WHERE id = ?
        ''', (
            self.name,
            self.assembled_sequence,
            json.dumps(self.features),
            json.dumps(self.metadata),
            self.id
        ))
        
        conn.commit()
        conn.close()
