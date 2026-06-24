# MoClo Library Tool

A Docker-containerized web application for managing and working with MoClo (Modular Cloning) golden gate cloning libraries.

> **macOS Users:** See [MACOS_SETUP.md](MACOS_SETUP.md) for detailed macOS-specific setup instructions.

## Features

### Core Functionality
- Browse genetic parts in the MoClo library
- Visualize parts by type with graphical representations
- Check compatibility for assembly based on overhang sequences
- Create cassettes from compatible parts
- Export cassettes as images and sequence files (FASTA, GenBank)
- User authentication with private cassette workspaces
- Part upload with metadata tracking

### MoClo Backbone Integration (NEW)
- **Upload MoClo Backbones**: Import GenBank files with automatic restriction site detection
- **Compatibility Checking**: See which cassettes fit which backbones (and vice versa)
- **Plasmid Assembly**: Combine cassettes into backbones using Golden Gate assembly simulation
- **Multi-Slot Support**: Assemble multiple cassettes into backbones with multiple insertion sites
- **Circular Maps**: Visualize assembled plasmids with color-coded features
- **Export Options**: Download plasmids as GenBank, FASTA, or PNG images
- **Automated Analysis**: Automatic detection of BsaI, BpiI, and BsmBI restriction sites

## Technology Stack

- **Backend**: Python 3.11+, Flask
- **Database**: SQLite
- **Authentication**: bcrypt
- **Testing**: pytest, Hypothesis (property-based testing)
- **Visualization**: Pillow, cairosvg
- **Sequence Analysis**: BioPython 1.81
- **Containerization**: Docker, Docker Compose

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # Flask application entry point
│   ├── models/              # Data models (User, Part, Cassette)
│   ├── api/                 # REST API endpoints
│   ├── services/            # Business logic services
│   ├── static/              # Static files (CSS, JS, images)
│   └── templates/           # HTML templates
├── data/                    # Persistent storage (mounted volume)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### Running with Docker

1. Build and start the container:
   ```bash
   docker-compose up --build
   ```

2. Access the application at `http://localhost:5000`

3. Stop the container:
   ```bash
   docker-compose down
   ```

### Development Setup (without Docker)

**Note**: For image export functionality, you need to install Cairo system libraries:

- **Ubuntu/Debian**: `sudo apt-get install libcairo2 libcairo2-dev libgdk-pixbuf2.0-0 libffi-dev`
- **macOS**: `brew install cairo`
- **Windows**: Download GTK+ runtime from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   export FLASK_APP=app.main
   export DATABASE_PATH=./data/moclo.db
   flask run
   ```

4. Run tests:
   ```bash
   pytest
   ```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and create session
- `POST /api/auth/logout` - Logout and destroy session
- `GET /api/auth/session` - Check current session

### Parts
- `GET /api/parts` - List all parts (with optional filters)
- `GET /api/parts/:id` - Get part details
- `POST /api/parts` - Upload new part
- `GET /api/parts/:id/compatible` - Get compatible parts

### Cassettes
- `GET /api/cassettes` - List user's cassettes
- `GET /api/cassettes/:id` - Get cassette details
- `POST /api/cassettes` - Create new cassette
- `DELETE /api/cassettes/:id` - Delete cassette
- `GET /api/cassettes/:id/export/fasta` - Export as FASTA
- `GET /api/cassettes/:id/export/genbank` - Export as GenBank
- `GET /api/cassettes/:id/export/image` - Export as image
- `GET /api/cassettes/:id/compatible-backbones` - Get compatible backbones (NEW)

### Backbones (NEW)
- `POST /api/backbones` - Upload GenBank backbone file
- `GET /api/backbones` - List user's backbones
- `GET /api/backbones/:id` - Get backbone details
- `DELETE /api/backbones/:id` - Delete backbone
- `GET /api/backbones/:id/sites` - Get restriction sites
- `GET /api/backbones/:id/compatible-cassettes` - Get compatible cassettes

### Plasmids (NEW)
- `POST /api/plasmids` - Assemble cassettes into backbone
- `POST /api/plasmids/simulate` - Simulate assembly (validation)
- `GET /api/plasmids` - List user's assembled plasmids
- `GET /api/plasmids/:id` - Get plasmid details
- `DELETE /api/plasmids/:id` - Delete plasmid
- `GET /api/plasmids/:id/export/genbank` - Export as GenBank
- `GET /api/plasmids/:id/export/fasta` - Export as FASTA
- `GET /api/plasmids/:id/export/image` - Export circular map as PNG

### Visualization
- `GET /api/visualize/part/:id` - Get part visualization (SVG)
- `GET /api/visualize/cassette/:id` - Get cassette visualization (SVG)

## MoClo System Overview

MoClo (Modular Cloning) uses Type IIS restriction enzymes to create standardized DNA parts with 4-base overhangs. Parts can be assembled when the 3' overhang of one part matches the 5' overhang of the next part.

### Part Types

- **Coding**: Protein-coding sequences (blue)
- **NonCodingPromoter**: Promoter sequences (green)
- **NonCodingTerminator**: Terminator sequences (red)
- **NonCodingIntron**: Intron sequences (yellow)
- **NonCodingOther**: Other non-coding sequences (gray)

### Assembly Workflow

1. **Parts → Cassettes**: Assemble compatible parts into cassettes
2. **Cassettes → Plasmids**: Insert cassettes into MoClo backbone vectors
3. **Export**: Download final plasmids for use in lab

### Supported Restriction Enzymes

- **BsaI**: GGTCTC (most common in MoClo)
- **BpiI/BbsI**: GAAGAC
- **BsmBI**: CGTCTC

## Documentation

- **User Guide**: [docs/BACKBONE_USER_GUIDE.md](docs/BACKBONE_USER_GUIDE.md) - Complete guide for using the backbone feature
- **Testing Guide**: [TESTING_GUIDE.md](TESTING_GUIDE.md) - Comprehensive testing procedures
- **API Documentation**: See API Endpoints section above
- **Requirements**: `.kiro/specs/moclo-library-tool/requirements.md`
- **Design**: `.kiro/specs/moclo-library-tool/design.md`
