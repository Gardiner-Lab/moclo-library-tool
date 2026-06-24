"""
Backbone model for MoClo plasmid backbones.

This module provides the Backbone class for managing plasmid backbones
that can accept MoClo cassette insertions.
"""

import uuid
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.models.database import get_connection


class Backbone:
    """
    Represents a MoClo plasmid backbone.
    
    A backbone is a plasmid vector that contains restriction sites
    (e.g., BsaI, BpiI) for inserting MoClo cassettes.
    """
    
    def __init__(
        self,
        id: str,
        name: str,
        owner_id: str,
        sequence: str,
        description: str = "",
        genbank_data: Optional[Dict[str, Any]] = None,
        restriction_sites: Optional[List[Dict[str, Any]]] = None,
        created_at: Optional[datetime] = None,
        contributor: Optional[str] = None,
        donor_organism: Optional[str] = None,
        lab_source: Optional[str] = None,
        overhang_5prime: Optional[str] = None,
        overhang_3prime: Optional[str] = None,
        reference: Optional[str] = None,
        upload_date: Optional[str] = None
    ):
        """
        Initialize a Backbone instance.
        
        Args:
            id: Unique identifier
            name: Backbone name
            owner_id: ID of user who owns this backbone
            sequence: DNA sequence of the backbone
            description: Optional description
            genbank_data: Parsed GenBank features and metadata
            restriction_sites: List of detected MoClo restriction sites
            created_at: Creation timestamp
            contributor: Optional contributor name
            donor_organism: Optional donor organism
            lab_source: Optional lab source
            overhang_5prime: Optional 5' overhang sequence
            overhang_3prime: Optional 3' overhang sequence
            reference: Optional reference
            upload_date: Optional upload date
        """
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.sequence = sequence.upper()
        self.description = description
        self.genbank_data = genbank_data or {}
        self.restriction_sites = restriction_sites or []
        self.created_at = created_at or datetime.now(timezone.utc)
        self.contributor = contributor
        self.donor_organism = donor_organism
        self.lab_source = lab_source
        self.overhang_5prime = overhang_5prime
        self.overhang_3prime = overhang_3prime
        self.reference = reference
        self.upload_date = upload_date
    
    @property
    def size(self) -> int:
        """Get the size of the backbone in base pairs."""
        return len(self.sequence)
    
    @property
    def cassette_slots(self) -> int:
        """Get the number of cassette insertion slots."""
        # Count unique slot numbers in restriction sites
        if not self.restriction_sites:
            return 0
        slots = set(site.get('slot_number', 1) for site in self.restriction_sites)
        return len(slots)
    
    @property
    def features(self) -> List[Dict[str, Any]]:
        """Get the list of features from GenBank data."""
        return self.genbank_data.get('features', [])
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert backbone to dictionary representation.
        
        Returns:
            Dictionary with backbone data
        """
        data = {
            'id': self.id,
            'name': self.name,
            'owner_id': self.owner_id,
            'sequence': self.sequence,
            'size': self.size,
            'description': self.description,
            'genbank_data': self.genbank_data,
            'restriction_sites': self.restriction_sites,
            'cassette_slots': self.cassette_slots,
            'created_at': self.created_at.isoformat()
        }
        
        # Add metadata fields if they exist
        if hasattr(self, 'plasmid_id') and self.plasmid_id:
            data['plasmid_id'] = self.plasmid_id
        if hasattr(self, 'location_80') and self.location_80:
            data['location_80'] = self.location_80
        if hasattr(self, 'location_96_plate') and self.location_96_plate:
            data['location_96_plate'] = self.location_96_plate
        if hasattr(self, 'antibiotic') and self.antibiotic:
            data['antibiotic'] = self.antibiotic
        if hasattr(self, 'level') and self.level:
            data['level'] = self.level
        if hasattr(self, 'unit') and self.unit:
            data['unit'] = self.unit
        if hasattr(self, 'ori_ecoli') and self.ori_ecoli:
            data['ori_ecoli'] = self.ori_ecoli
        if hasattr(self, 'ori_agro') and self.ori_agro:
            data['ori_agro'] = self.ori_agro
        if hasattr(self, 'host_strain') and self.host_strain:
            data['host_strain'] = self.host_strain
        if hasattr(self, 'primer_for_seq') and self.primer_for_seq:
            data['primer_for_seq'] = self.primer_for_seq
        if hasattr(self, 'sequenced') and self.sequenced:
            data['sequenced'] = self.sequenced
        if hasattr(self, 'comments') and self.comments:
            data['comments'] = self.comments
        if hasattr(self, 'contributor') and self.contributor:
            data['contributor'] = self.contributor
        if hasattr(self, 'donor_organism') and self.donor_organism:
            data['donor_organism'] = self.donor_organism
        if hasattr(self, 'lab_source') and self.lab_source:
            data['lab_source'] = self.lab_source
        if hasattr(self, 'overhang_5prime') and self.overhang_5prime:
            data['overhang_5prime'] = self.overhang_5prime
        if hasattr(self, 'overhang_3prime') and self.overhang_3prime:
            data['overhang_3prime'] = self.overhang_3prime
        if hasattr(self, 'reference') and self.reference:
            data['reference'] = self.reference
        if hasattr(self, 'upload_date') and self.upload_date:
            data['upload_date'] = self.upload_date
        
        return data
    
    @staticmethod
    def create(
        name: str,
        owner_id: str,
        sequence: str,
        description: str = "",
        genbank_data: Optional[Dict[str, Any]] = None,
        restriction_sites: Optional[List[Dict[str, Any]]] = None,
        contributor: Optional[str] = None,
        donor_organism: Optional[str] = None,
        lab_source: Optional[str] = None,
        overhang_5prime: Optional[str] = None,
        overhang_3prime: Optional[str] = None,
        reference: Optional[str] = None,
        upload_date: Optional[str] = None
    ) -> 'Backbone':
        """
        Create a new backbone and store it in the database.
        
        Args:
            name: Backbone name
            owner_id: ID of user creating the backbone
            sequence: DNA sequence
            description: Optional description
            genbank_data: Parsed GenBank data
            restriction_sites: Detected restriction sites
            contributor: Optional contributor name
            donor_organism: Optional donor organism
            lab_source: Optional lab source
            overhang_5prime: Optional 5' overhang sequence
            overhang_3prime: Optional 3' overhang sequence
            reference: Optional reference
            upload_date: Optional upload date
            
        Returns:
            Created Backbone instance
            
        Raises:
            ValueError: If name is empty or sequence is invalid
        """
        # Validate inputs
        if not name or not name.strip():
            raise ValueError("Backbone name cannot be empty")
        
        if not sequence or not sequence.strip():
            raise ValueError("Backbone sequence cannot be empty")
        
        # Validate sequence contains only valid DNA bases
        valid_bases = set('ATCGRYSWKMBDHVN')  # Include ambiguity codes
        if not all(base in valid_bases for base in sequence.upper()):
            raise ValueError("Sequence contains invalid characters")
        
        # Generate unique ID
        backbone_id = str(uuid.uuid4())
        
        # Create backbone instance
        backbone = Backbone(
            id=backbone_id,
            name=name.strip(),
            owner_id=owner_id,
            sequence=sequence.strip(),
            description=description.strip(),
            genbank_data=genbank_data,
            restriction_sites=restriction_sites,
            contributor=contributor,
            donor_organism=donor_organism,
            lab_source=lab_source,
            overhang_5prime=overhang_5prime,
            overhang_3prime=overhang_3prime,
            reference=reference,
            upload_date=upload_date
        )
        
        # Store in database
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO backbones (
                id, name, owner_id, sequence, description,
                genbank_data, restriction_sites, created_at,
                contributor, donor_organism, lab_source,
                overhang_5prime, overhang_3prime, reference, upload_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            backbone.id,
            backbone.name,
            backbone.owner_id,
            backbone.sequence,
            backbone.description,
            json.dumps(backbone.genbank_data),
            json.dumps(backbone.restriction_sites),
            backbone.created_at.isoformat(),
            backbone.contributor,
            backbone.donor_organism,
            backbone.lab_source,
            backbone.overhang_5prime,
            backbone.overhang_3prime,
            backbone.reference,
            backbone.upload_date
        ))
        
        conn.commit()
        conn.close()
        
        return backbone
    
    @staticmethod
    def get_by_id(backbone_id: str) -> Optional['Backbone']:
        """
        Retrieve a backbone by its ID.
        
        Args:
            backbone_id: Backbone ID to look up
            
        Returns:
            Backbone instance if found, None otherwise
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, owner_id, sequence, description,
                   genbank_data, restriction_sites, created_at,
                   plasmid_id, location_80, location_96_plate, antibiotic, level, unit,
                   ori_ecoli, ori_agro, size, host_strain, primer_for_seq, sequenced, comments,
                   contributor, donor_organism, lab_source, overhang_5prime, overhang_3prime, reference, upload_date
            FROM backbones
            WHERE id = ?
        ''', (backbone_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return None
        
        backbone = Backbone(
            id=row[0],
            name=row[1],
            owner_id=row[2],
            sequence=row[3],
            description=row[4],
            genbank_data=json.loads(row[5]) if row[5] else {},
            restriction_sites=json.loads(row[6]) if row[6] else [],
            created_at=datetime.fromisoformat(row[7])
        )
        
        # Add metadata fields
        backbone.plasmid_id = row[8]
        backbone.location_80 = row[9]
        backbone.location_96_plate = row[10]
        backbone.antibiotic = row[11]
        backbone.level = row[12]
        backbone.unit = row[13]
        backbone.ori_ecoli = row[14]
        backbone.ori_agro = row[15]
        # row[16] is size (already calculated from sequence)
        backbone.host_strain = row[17]
        backbone.primer_for_seq = row[18]
        backbone.sequenced = row[19]
        backbone.comments = row[20]
        backbone.contributor = row[21]
        backbone.donor_organism = row[22]
        backbone.lab_source = row[23]
        backbone.overhang_5prime = row[24]
        backbone.overhang_3prime = row[25]
        backbone.reference = row[26]
        backbone.upload_date = row[27]
        
        return backbone
    
    @staticmethod
    def get_by_owner(owner_id: str) -> List['Backbone']:
        """
        Get all backbones owned by a specific user.
        
        Args:
            owner_id: User ID
            
        Returns:
            List of Backbone instances
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, owner_id, sequence, description,
                   genbank_data, restriction_sites, created_at,
                   plasmid_id, location_80, location_96_plate, antibiotic, level, unit,
                   ori_ecoli, ori_agro, size, host_strain, primer_for_seq, sequenced, comments,
                   contributor, donor_organism, lab_source, overhang_5prime, overhang_3prime, reference, upload_date
            FROM backbones
            WHERE owner_id = ?
            ORDER BY created_at DESC
        ''', (owner_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        backbones = []
        for row in rows:
            backbone = Backbone(
                id=row[0],
                name=row[1],
                owner_id=row[2],
                sequence=row[3],
                description=row[4],
                genbank_data=json.loads(row[5]) if row[5] else {},
                restriction_sites=json.loads(row[6]) if row[6] else [],
                created_at=datetime.fromisoformat(row[7])
            )
            # Add metadata fields
            backbone.plasmid_id = row[8]
            backbone.location_80 = row[9]
            backbone.location_96_plate = row[10]
            backbone.antibiotic = row[11]
            backbone.level = row[12]
            backbone.unit = row[13]
            backbone.ori_ecoli = row[14]
            backbone.ori_agro = row[15]
            backbone.host_strain = row[17]
            backbone.primer_for_seq = row[18]
            backbone.sequenced = row[19]
            backbone.comments = row[20]
            backbone.contributor = row[21]
            backbone.donor_organism = row[22]
            backbone.lab_source = row[23]
            backbone.overhang_5prime = row[24]
            backbone.overhang_3prime = row[25]
            backbone.reference = row[26]
            backbone.upload_date = row[27]
            backbones.append(backbone)
        
        return backbones
    
    @staticmethod
    def get_all() -> List['Backbone']:
        """
        Get all backbones in the database.
        
        Returns:
            List of all Backbone instances
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, owner_id, sequence, description,
                   genbank_data, restriction_sites, created_at,
                   plasmid_id, location_80, location_96_plate, antibiotic, level, unit,
                   ori_ecoli, ori_agro, size, host_strain, primer_for_seq, sequenced, comments,
                   contributor, donor_organism, lab_source, overhang_5prime, overhang_3prime, reference, upload_date
            FROM backbones
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        backbones = []
        for row in rows:
            backbone = Backbone(
                id=row[0],
                name=row[1],
                owner_id=row[2],
                sequence=row[3],
                description=row[4],
                genbank_data=json.loads(row[5]) if row[5] else {},
                restriction_sites=json.loads(row[6]) if row[6] else [],
                created_at=datetime.fromisoformat(row[7])
            )
            # Add metadata fields
            backbone.plasmid_id = row[8]
            backbone.location_80 = row[9]
            backbone.location_96_plate = row[10]
            backbone.antibiotic = row[11]
            backbone.level = row[12]
            backbone.unit = row[13]
            backbone.ori_ecoli = row[14]
            backbone.ori_agro = row[15]
            backbone.host_strain = row[17]
            backbone.primer_for_seq = row[18]
            backbone.sequenced = row[19]
            backbone.comments = row[20]
            backbone.contributor = row[21]
            backbone.donor_organism = row[22]
            backbone.lab_source = row[23]
            backbone.overhang_5prime = row[24]
            backbone.overhang_3prime = row[25]
            backbone.reference = row[26]
            backbone.upload_date = row[27]
            backbones.append(backbone)
        
        return backbones
    
    def delete(self) -> None:
        """Delete this backbone from the database."""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM backbones WHERE id = ?', (self.id,))
        
        conn.commit()
        conn.close()
    
    def update(self) -> None:
        """Update this backbone in the database."""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE backbones
            SET name = ?, description = ?, sequence = ?,
                genbank_data = ?, restriction_sites = ?
            WHERE id = ?
        ''', (
            self.name,
            self.description,
            self.sequence,
            json.dumps(self.genbank_data),
            json.dumps(self.restriction_sites),
            self.id
        ))
        
        conn.commit()
        conn.close()
