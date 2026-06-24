"""
Part model with CRUD operations for MoClo genetic parts.
"""

import uuid
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.parts_database import get_parts_database


class Part:
    """Part model representing a DNA sequence element in the MoClo library."""
    
    # Valid part types as defined in requirements
    VALID_PART_TYPES = [
        'Coding',
        'NonCodingPromoter',
        'NonCodingTerminator',
        'NonCodingIntron',
        'NonCodingOther'
    ]
    
    def __init__(
        self,
        id: str,
        name: str,
        part_type: str,
        sequence: str,
        overhang_5prime: str,
        overhang_3prime: str,
        lab_source: str,
        contributor: str,
        upload_date: Optional[str] = None,
        description: Optional[str] = None,
        # Extended metadata fields (all optional)
        plasmid_id: Optional[str] = None,
        location_80: Optional[str] = None,
        location_96_plate: Optional[str] = None,
        antibiotic: Optional[str] = None,
        level: Optional[str] = None,
        unit: Optional[str] = None,
        donor_organism: Optional[str] = None,
        reference: Optional[str] = None,
        size: Optional[int] = None,
        host_strain: Optional[str] = None,
        sequenced: Optional[str] = None,
        comments: Optional[str] = None,
        ori_ecoli: Optional[str] = None,
        ori_agro: Optional[str] = None,
        primer_for_seq: Optional[str] = None,
        features: Optional[List] = None
    ):
        """
        Initialize a Part instance.
        
        Args:
            id: Unique identifier (UUID)
            name: Part name
            part_type: Type of part (Coding, NonCodingPromoter, etc.)
            sequence: DNA sequence (ATCG)
            overhang_5prime: 5' overhang sequence (4 bases)
            overhang_3prime: 3' overhang sequence (4 bases)
            lab_source: Lab name associated with the part
            contributor: Username of the user who uploaded the part
            upload_date: Timestamp of part upload (ISO format)
            description: Optional description of the part
            plasmid_id: Plasmid identifier (e.g., pICH41373)
            location_80: Location in -80°C freezer
            location_96_plate: Location in 96-well plate
            antibiotic: Antibiotic resistance marker
            level: MoClo level (0, 1, 2, etc.)
            unit: Part unit type (Pro, 5U, CDS, etc.)
            donor_organism: Source organism
            reference: Literature reference
            size: Plasmid size in base pairs
            host_strain: Bacterial host strain
            sequenced: Sequencing date or status
            comments: Additional comments
            ori_ecoli: Origin of replication in E. coli
            ori_agro: Origin of replication in Agrobacterium
            primer_for_seq: Sequencing primer name
        """
        self.id = id
        self.name = name
        self.part_type = part_type
        self.sequence = sequence
        self.overhang_5prime = overhang_5prime
        self.overhang_3prime = overhang_3prime
        self.lab_source = lab_source
        self.contributor = contributor
        self.upload_date = upload_date
        self.description = description
        # Extended metadata
        self.plasmid_id = plasmid_id
        self.location_80 = location_80
        self.location_96_plate = location_96_plate
        self.antibiotic = antibiotic
        self.level = level
        self.unit = unit
        self.donor_organism = donor_organism
        self.reference = reference
        self.size = size
        self.host_strain = host_strain
        self.sequenced = sequenced
        self.comments = comments
        self.ori_ecoli = ori_ecoli
        self.ori_agro = ori_agro
        self.primer_for_seq = primer_for_seq
        self.features = features
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert part to dictionary representation.
        
        Returns:
            Dictionary with part data
        """
        data = {
            'id': self.id,
            'name': self.name,
            'part_type': self.part_type,
            'sequence': self.sequence,
            'overhang_5prime': self.overhang_5prime,
            'overhang_3prime': self.overhang_3prime,
            'lab_source': self.lab_source,
            'contributor': self.contributor,
            'upload_date': self.upload_date,
            'description': self.description,
            'length': len(self.sequence)
        }
        
        # Add extended metadata if present
        if self.plasmid_id:
            data['plasmid_id'] = self.plasmid_id
        if self.location_80:
            data['location_80'] = self.location_80
        if self.location_96_plate:
            data['location_96_plate'] = self.location_96_plate
        if self.antibiotic:
            data['antibiotic'] = self.antibiotic
        if self.level:
            data['level'] = self.level
        if self.unit:
            data['unit'] = self.unit
        if self.donor_organism:
            data['donor_organism'] = self.donor_organism
        if self.reference:
            data['reference'] = self.reference
        if self.size:
            data['size'] = self.size
        if self.host_strain:
            data['host_strain'] = self.host_strain
        if self.sequenced:
            data['sequenced'] = self.sequenced
        if self.comments:
            data['comments'] = self.comments
        if self.ori_ecoli:
            data['ori_ecoli'] = self.ori_ecoli
        if self.ori_agro:
            data['ori_agro'] = self.ori_agro
        if self.primer_for_seq:
            data['primer_for_seq'] = self.primer_for_seq
        if self.features:
            data['features'] = self.features
        
        return data
    
    @staticmethod
    def create(
        name: str,
        part_type: str,
        sequence: str,
        overhang_5prime: str,
        overhang_3prime: str,
        lab_source: str,
        contributor: str,
        description: Optional[str] = None,
        # Extended metadata fields (all optional)
        plasmid_id: Optional[str] = None,
        location_80: Optional[str] = None,
        location_96_plate: Optional[str] = None,
        antibiotic: Optional[str] = None,
        level: Optional[str] = None,
        unit: Optional[str] = None,
        donor_organism: Optional[str] = None,
        reference: Optional[str] = None,
        size: Optional[int] = None,
        host_strain: Optional[str] = None,
        sequenced: Optional[str] = None,
        comments: Optional[str] = None,
        ori_ecoli: Optional[str] = None,
        ori_agro: Optional[str] = None,
        primer_for_seq: Optional[str] = None,
        features: Optional[List] = None
    ) -> 'Part':
        """
        Create a new part in the database.
        
        Args:
            name: Part name
            part_type: Type of part (must be one of VALID_PART_TYPES)
            sequence: DNA sequence (ATCG)
            overhang_5prime: 5' overhang sequence (4 bases)
            overhang_3prime: 3' overhang sequence (4 bases)
            lab_source: Lab name associated with the part
            contributor: Username of the user who uploaded the part
            description: Optional description of the part
            plasmid_id: Plasmid identifier (optional)
            location_80: Location in -80°C freezer (optional)
            location_96_plate: Location in 96-well plate (optional)
            antibiotic: Antibiotic resistance marker (optional)
            level: MoClo level (optional)
            unit: Part unit type (optional)
            donor_organism: Source organism (optional)
            reference: Literature reference (optional)
            size: Plasmid size in base pairs (optional)
            host_strain: Bacterial host strain (optional)
            sequenced: Sequencing date or status (optional)
            comments: Additional comments (optional)
            
        Returns:
            Created Part instance
            
        Raises:
            ValueError: If validation fails
        """
        # Validate inputs
        Part._validate_part_data(
            name, part_type, sequence, overhang_5prime, overhang_3prime, lab_source
        )
        
        # Generate unique ID
        part_id = str(uuid.uuid4())
        
        # Insert into database
        db = get_parts_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert new part with extended metadata
            cursor.execute(
                """
                INSERT INTO parts (
                    id, name, part_type, sequence, overhang_5prime, overhang_3prime,
                    lab_source, contributor, description,
                    plasmid_id, location_80, location_96_plate, antibiotic, level, unit,
                    donor_organism, reference, size, host_strain, sequenced, comments,
                    ori_ecoli, ori_agro, primer_for_seq, features
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (part_id, name, part_type, sequence, overhang_5prime, overhang_3prime,
                 lab_source, contributor, description,
                 plasmid_id, location_80, location_96_plate, antibiotic, level, unit,
                 donor_organism, reference, size, host_strain, sequenced, comments,
                 ori_ecoli, ori_agro, primer_for_seq,
                 json.dumps(features) if features else None)
            )
            
            # Retrieve the created part
            cursor.execute(
                "SELECT * FROM parts WHERE id = ?",
                (part_id,)
            )
            row = cursor.fetchone()
            
            return Part._from_row(row)
    
    @staticmethod
    def get_by_id(part_id: str) -> Optional['Part']:
        """
        Retrieve a part by ID.
        
        Args:
            part_id: Part ID to look up
            
        Returns:
            Part instance if found, None otherwise
        """
        db = get_parts_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM parts WHERE id = ?",
                (part_id,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return Part._from_row(row)
    
    @staticmethod
    def get_all() -> List['Part']:
        """
        Retrieve all parts from the database.
        
        Returns:
            List of Part instances
        """
        db = get_parts_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM parts ORDER BY upload_date DESC")
            rows = cursor.fetchall()
            
            return [Part._from_row(row) for row in rows]
    
    @staticmethod
    def filter_by_type(part_type: str) -> List['Part']:
        """
        Retrieve all parts of a specific type.
        
        Args:
            part_type: Type of part to filter by
            
        Returns:
            List of Part instances matching the type
            
        Raises:
            ValueError: If part_type is not valid
        """
        if part_type not in Part.VALID_PART_TYPES:
            raise ValueError(f"Invalid part type: {part_type}")
        
        db = get_parts_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM parts WHERE part_type = ? ORDER BY upload_date DESC",
                (part_type,)
            )
            rows = cursor.fetchall()
            
            return [Part._from_row(row) for row in rows]
    
    @staticmethod
    def search(query: str) -> List['Part']:
        """
        Search for parts by name or ID.
        
        Args:
            query: Search query string
            
        Returns:
            List of Part instances matching the search criteria
        """
        db = get_parts_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Search in name and id fields using LIKE for partial matching
            search_pattern = f"%{query}%"
            cursor.execute(
                """
                SELECT * FROM parts 
                WHERE name LIKE ? OR id LIKE ?
                ORDER BY upload_date DESC
                """,
                (search_pattern, search_pattern)
            )
            rows = cursor.fetchall()
            
            return [Part._from_row(row) for row in rows]
    
    @staticmethod
    def find_compatible_before(part: 'Part') -> List['Part']:
        """
        Find all parts that can be placed before the given part.
        A part can be placed before if its 3' overhang matches the target's 5' overhang.
        
        Args:
            part: Target part to find compatible parts for
            
        Returns:
            List of Part instances that can be placed before the target
        """
        db = get_parts_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM parts 
                WHERE overhang_3prime = ? AND id != ?
                ORDER BY name
                """,
                (part.overhang_5prime, part.id)
            )
            rows = cursor.fetchall()
            
            return [Part._from_row(row) for row in rows]
    
    @staticmethod
    def find_compatible_after(part: 'Part') -> List['Part']:
        """
        Find all parts that can be placed after the given part.
        A part can be placed after if its 5' overhang matches the target's 3' overhang.
        
        Args:
            part: Target part to find compatible parts for
            
        Returns:
            List of Part instances that can be placed after the target
        """
        db = get_parts_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM parts 
                WHERE overhang_5prime = ? AND id != ?
                ORDER BY name
                """,
                (part.overhang_3prime, part.id)
            )
            rows = cursor.fetchall()
            
            return [Part._from_row(row) for row in rows]
    
    def update(
        self,
        name: Optional[str] = None,
        part_type: Optional[str] = None,
        sequence: Optional[str] = None,
        overhang_5prime: Optional[str] = None,
        overhang_3prime: Optional[str] = None,
        lab_source: Optional[str] = None,
        description: Optional[str] = None,
        # Extended metadata fields
        plasmid_id: Optional[str] = None,
        location_80: Optional[str] = None,
        location_96_plate: Optional[str] = None,
        antibiotic: Optional[str] = None,
        level: Optional[str] = None,
        unit: Optional[str] = None,
        donor_organism: Optional[str] = None,
        reference: Optional[str] = None,
        host_strain: Optional[str] = None,
        sequenced: Optional[str] = None,
        comments: Optional[str] = None,
        ori_ecoli: Optional[str] = None,
        ori_agro: Optional[str] = None,
        primer_for_seq: Optional[str] = None
    ) -> None:
        """
        Update part information.
        
        Args:
            name: New part name (optional)
            part_type: New part type (optional)
            sequence: New DNA sequence (optional)
            overhang_5prime: New 5' overhang (optional)
            overhang_3prime: New 3' overhang (optional)
            lab_source: New lab source (optional)
            description: New description (optional)
            plasmid_id: New plasmid ID (optional)
            location_80: New -80°C location (optional)
            location_96_plate: New 96-well plate location (optional)
            antibiotic: New antibiotic resistance (optional)
            level: New MoClo level (optional)
            unit: New unit type (optional)
            donor_organism: New donor organism (optional)
            reference: New reference (optional)
            host_strain: New host strain (optional)
            sequenced: New sequencing status (optional)
            comments: New comments (optional)
            ori_ecoli: New E. coli origin (optional)
            ori_agro: New Agrobacterium origin (optional)
            primer_for_seq: New sequencing primer (optional)
            
        Raises:
            ValueError: If validation fails
        """
        # Prepare update values
        updates = {}
        if name is not None:
            updates['name'] = name
        if part_type is not None:
            if part_type not in Part.VALID_PART_TYPES:
                raise ValueError(f"Invalid part type: {part_type}")
            updates['part_type'] = part_type
        if sequence is not None:
            if not Part._is_valid_dna_sequence(sequence):
                raise ValueError("Sequence must contain only A, T, C, G characters")
            updates['sequence'] = sequence
        if overhang_5prime is not None:
            if not Part._is_valid_overhang(overhang_5prime):
                raise ValueError("5' overhang must be exactly 4 DNA bases")
            updates['overhang_5prime'] = overhang_5prime
        if overhang_3prime is not None:
            if not Part._is_valid_overhang(overhang_3prime):
                raise ValueError("3' overhang must be exactly 4 DNA bases")
            updates['overhang_3prime'] = overhang_3prime
        if lab_source is not None:
            if not lab_source.strip():
                raise ValueError("Lab source cannot be empty")
            updates['lab_source'] = lab_source
        if description is not None:
            updates['description'] = description
        
        # Extended metadata fields (no validation needed, can be None or empty)
        if plasmid_id is not None:
            updates['plasmid_id'] = plasmid_id
        if location_80 is not None:
            updates['location_80'] = location_80
        if location_96_plate is not None:
            updates['location_96_plate'] = location_96_plate
        if antibiotic is not None:
            updates['antibiotic'] = antibiotic
        if level is not None:
            updates['level'] = level
        if unit is not None:
            updates['unit'] = unit
        if donor_organism is not None:
            updates['donor_organism'] = donor_organism
        if reference is not None:
            updates['reference'] = reference
        if host_strain is not None:
            updates['host_strain'] = host_strain
        if sequenced is not None:
            updates['sequenced'] = sequenced
        if comments is not None:
            updates['comments'] = comments
        if ori_ecoli is not None:
            updates['ori_ecoli'] = ori_ecoli
        if ori_agro is not None:
            updates['ori_agro'] = ori_agro
        if primer_for_seq is not None:
            updates['primer_for_seq'] = primer_for_seq
        
        if not updates:
            return  # Nothing to update
        
        # Build SQL update statement
        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [self.id]
        
        db = get_parts_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE parts SET {set_clause} WHERE id = ?",
                values
            )
        
        # Update instance attributes
        for key, value in updates.items():
            setattr(self, key, value)
    
    def delete(self) -> None:
        """
        Delete this part from the database.
        
        Note: This may fail if there are cassettes referencing this part
        due to foreign key constraints.
        """
        db = get_parts_database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM parts WHERE id = ?",
                (self.id,)
            )
    
    @staticmethod
    def _from_row(row) -> 'Part':
        """
        Create a Part instance from a database row.
        
        Args:
            row: Database row (sqlite3.Row)
            
        Returns:
            Part instance
        """
        # Helper function to safely get column value
        def get_col(name):
            try:
                return row[name]
            except (KeyError, IndexError):
                return None
        
        return Part(
            id=row['id'],
            name=row['name'],
            part_type=row['part_type'],
            sequence=row['sequence'],
            overhang_5prime=row['overhang_5prime'],
            overhang_3prime=row['overhang_3prime'],
            lab_source=row['lab_source'],
            contributor=row['contributor'],
            upload_date=row['upload_date'],
            description=row['description'],
            # Extended metadata (may not exist in older databases)
            plasmid_id=get_col('plasmid_id'),
            location_80=get_col('location_80'),
            location_96_plate=get_col('location_96_plate'),
            antibiotic=get_col('antibiotic'),
            level=get_col('level'),
            unit=get_col('unit'),
            donor_organism=get_col('donor_organism'),
            reference=get_col('reference'),
            size=get_col('size'),
            host_strain=get_col('host_strain'),
            sequenced=get_col('sequenced'),
            comments=get_col('comments'),
            ori_ecoli=get_col('ori_ecoli'),
            ori_agro=get_col('ori_agro'),
            primer_for_seq=get_col('primer_for_seq'),
            features=json.loads(get_col('features')) if get_col('features') else None
        )
    
    @staticmethod
    def _validate_part_data(
        name: str,
        part_type: str,
        sequence: str,
        overhang_5prime: str,
        overhang_3prime: str,
        lab_source: str
    ) -> None:
        """
        Validate part data before creation.
        
        Args:
            name: Part name
            part_type: Type of part
            sequence: DNA sequence
            overhang_5prime: 5' overhang
            overhang_3prime: 3' overhang
            lab_source: Lab source
            
        Raises:
            ValueError: If any validation fails
        """
        # Validate name
        if not name or not name.strip():
            raise ValueError("Part name cannot be empty")
        
        # Validate part type
        if part_type not in Part.VALID_PART_TYPES:
            raise ValueError(
                f"Invalid part type: {part_type}. "
                f"Must be one of: {', '.join(Part.VALID_PART_TYPES)}"
            )
        
        # Validate sequence
        if not Part._is_valid_dna_sequence(sequence):
            raise ValueError("Sequence must contain only A, T, C, G characters")
        
        if len(sequence) < 8:
            raise ValueError("Sequence must be at least 8 bases long")
        
        # Validate overhangs
        if not Part._is_valid_overhang(overhang_5prime):
            raise ValueError("5' overhang must be exactly 4 DNA bases (A, T, C, G)")
        
        if not Part._is_valid_overhang(overhang_3prime):
            raise ValueError("3' overhang must be exactly 4 DNA bases (A, T, C, G)")
        
        # Validate lab source
        if not lab_source or not lab_source.strip():
            raise ValueError("Lab source cannot be empty")
    
    @staticmethod
    def _is_valid_dna_sequence(sequence: str) -> bool:
        """
        Check if a sequence contains only valid DNA bases.
        
        Args:
            sequence: DNA sequence to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not sequence:
            return False
        return all(base in 'ATCG' for base in sequence.upper())
    
    @staticmethod
    def _is_valid_overhang(overhang: str) -> bool:
        """
        Check if an overhang is exactly 4 valid DNA bases.
        
        Args:
            overhang: Overhang sequence to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not overhang or len(overhang) != 4:
            return False
        return all(base in 'ATCG' for base in overhang.upper())
    
    def __repr__(self) -> str:
        """String representation of Part."""
        return (
            f"Part(id='{self.id}', name='{self.name}', "
            f"type='{self.part_type}', length={len(self.sequence)})"
        )
    
    def __eq__(self, other) -> bool:
        """Check equality based on part ID."""
        if not isinstance(other, Part):
            return False
        return self.id == other.id
