# Database Initialization

This document describes the database initialization process for the MoClo Library Tool.

## Overview

The database is automatically initialized when the application starts. The initialization script:

1. Checks if the database already exists
2. Creates the database schema if needed (users, parts, cassettes tables)
3. Optionally loads seed data from a JSON file

## Automatic Initialization

The application automatically initializes the database on first run. No manual intervention is required.

### On Application Startup

When the Flask application starts (via `app/main.py`), it:
- Checks for an existing database at the configured path
- Creates the schema if the database doesn't exist
- Loads seed data if a seed file is available

### In Docker Container

When running in Docker, the database is stored in the `/data` volume mount, which persists across container restarts.

## Manual Initialization

You can also run the initialization script manually:

```bash
# Initialize with default database path
python app/init_db.py

# Initialize with custom database path
python app/init_db.py /path/to/database.db

# Initialize with seed data
python app/init_db.py /path/to/database.db /path/to/seed_data.json
```

## Seed Data

Seed data allows you to pre-populate the database with users and parts.

### Seed Data Format

Create a JSON file with the following structure:

```json
{
  "users": [
    {
      "username": "demo",
      "password": "demo123"
    }
  ],
  "parts": [
    {
      "name": "Promoter_J23100",
      "part_type": "NonCodingPromoter",
      "sequence": "AAAGTTGACAGCTAGCTCAGTCCTAGGTATAATGCTAGC",
      "overhang_5prime": "AAAG",
      "overhang_3prime": "TAGC",
      "lab_source": "iGEM Registry",
      "contributor": "demo",
      "description": "Strong constitutive promoter"
    }
  ]
}
```

### Valid Part Types

- `Coding` - Protein coding sequences
- `NonCodingPromoter` - Promoter sequences
- `NonCodingTerminator` - Terminator sequences
- `NonCodingIntron` - Intron sequences
- `NonCodingOther` - Other non-coding sequences (RBS, etc.)

### Seed Data Location

The initialization script looks for seed data in the following locations (in order):

1. Path specified in `SEED_DATA_FILE` environment variable
2. Command line argument (when running manually)
3. `/data/seed_data.json` (default location in Docker)

### Using Seed Data with Docker

To use seed data with Docker, place your `seed_data.json` file in the `data` directory:

```bash
# Copy seed data to data directory
cp seed_data.example.json data/seed_data.json

# Start the container
docker-compose up
```

Or specify a custom seed file via environment variable:

```yaml
# docker-compose.yml
services:
  web:
    environment:
      - SEED_DATA_FILE=/data/my_seed_data.json
    volumes:
      - ./data:/data
      - ./my_seed_data.json:/data/my_seed_data.json
```

## Environment Variables

- `DATABASE_PATH` - Path to the SQLite database file (default: `/data/moclo.db`)
- `SEED_DATA_FILE` - Path to seed data JSON file (optional)

## Example Seed Data

An example seed data file is provided at `seed_data.example.json`. This includes:

- A demo user account
- Four compatible parts that can be assembled into a cassette:
  - Promoter (J23100)
  - RBS (B0034)
  - GFP coding sequence
  - Terminator (B0015)

To use the example seed data:

```bash
# Copy to data directory
cp seed_data.example.json data/seed_data.json

# Restart the application
docker-compose restart
```

## Idempotency

The initialization script is idempotent - it can be run multiple times safely:

- Existing tables are not modified
- Existing users are not duplicated
- Existing parts (by name) are not duplicated

This means you can add new seed data and re-run initialization without affecting existing data.

## Logging

The initialization script logs all operations:

- Database creation
- Schema initialization
- User creation
- Part creation
- Errors and warnings

Logs are written to stdout and can be viewed with:

```bash
# Docker logs
docker-compose logs web

# Or follow logs in real-time
docker-compose logs -f web
```

## Troubleshooting

### Database Already Exists

If the database already exists, the script will skip schema creation and only load seed data (if provided).

### Seed Data Errors

If seed data is invalid:
- Invalid JSON: Error logged, initialization continues without seed data
- Missing required fields: Item skipped, other items processed
- Duplicate users/parts: Item skipped, other items processed

### Permission Errors

Ensure the application has write permissions to the database directory:

```bash
# Fix permissions for data directory
chmod 755 data
```

### Database Corruption

If the database becomes corrupted, you can reset it:

```bash
# Stop the container
docker-compose down

# Remove the database
rm data/moclo.db

# Restart (will recreate database)
docker-compose up
```

## Database Schema

The initialization creates three tables:

### users
- `id` (TEXT, PRIMARY KEY) - UUID
- `username` (TEXT, UNIQUE) - Username
- `password_hash` (TEXT) - Bcrypt password hash
- `created_at` (TIMESTAMP) - Creation timestamp

### parts
- `id` (TEXT, PRIMARY KEY) - UUID
- `name` (TEXT) - Part name
- `part_type` (TEXT) - Part type (Coding, NonCodingPromoter, etc.)
- `sequence` (TEXT) - DNA sequence
- `overhang_5prime` (TEXT) - 5' overhang (4 bases)
- `overhang_3prime` (TEXT) - 3' overhang (4 bases)
- `lab_source` (TEXT) - Lab source
- `contributor` (TEXT) - Username of contributor
- `upload_date` (TIMESTAMP) - Upload timestamp
- `description` (TEXT) - Optional description

### cassettes
- `id` (TEXT, PRIMARY KEY) - UUID
- `name` (TEXT) - Cassette name
- `owner_id` (TEXT) - User ID of owner
- `part_ids` (TEXT) - JSON array of part IDs
- `assembled_sequence` (TEXT) - Assembled DNA sequence
- `created_at` (TIMESTAMP) - Creation timestamp

### Indexes

Performance indexes are created on:
- `parts.part_type` - For filtering by type
- `parts.overhang_5prime` - For compatibility checking
- `parts.overhang_3prime` - For compatibility checking
- `cassettes.owner_id` - For user cassette lookup
