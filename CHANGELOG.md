# Changelog

All notable changes to the MoClo Library Tool project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.0] - 2026-09-02

### Added
- Real Addgene Plant MoClo demo data (kit #1000000044) and a pre-assembled
  multigene Level 2 example built from three chained transcription units.
- `restriction_sites.compute_slot_overhangs` / `build_moclo_acceptor`: faithful
  Type IIS digest of an acceptor into per-slot excision window and fusion overhangs.
- Bulk upload: per-file category selector (Backbone / Level 0 / Level 1 / Level 2),
  pre-filled from an `L0` / `L1` / `L2` token in the filename.
- Backbone is now an upload category on the upload page; a bulk file with no level
  token is registered as an acceptor vector.
- `scripts/update.sh`: backup, health gate and automatic rollback on failed update.
- `tests/test_plasmid_assembly.py`.

### Changed
- Golden Gate at the cassette-to-backbone step is now biologically faithful: each
  4 bp scar is kept once and no Type IIS recognition site is left in the product.
- Part and cassette GenBank exports are wrapped in their Type IIS sites so an
  exported `.gb` re-imports as a genuine MoClo unit; the parser also falls back to
  `/overhang_*` and `/moclo_level` qualifiers when no sites are present.
- Bulk upload sends a per-file MoClo level, and renames each part file with the
  matching `_L0` / `_L1` / `_L2` token before parsing.
- Internal restriction-site check on upload is level-aware (skipped for Level 1+).

### Security
- `docker-compose.prod.yml` requires `SECRET_KEY`; the app refuses to start in
  production with the default key.

## [0.1.0] - 2024-01-XX

### Added
- Initial project structure and dependencies
- Docker configuration (Dockerfile, docker-compose.yml)
- Python project structure with Flask web framework
- Virtual environment setup scripts (setup.sh, setup.bat)
- Directory structure:
  - `/app` - Main application code
  - `/app/models` - Data models
  - `/app/api` - REST API endpoints
  - `/app/services` - Business logic services
  - `/app/static` - Static files (CSS, JS, images)
  - `/app/templates` - HTML templates
  - `/tests` - Test suite
- Dependencies:
  - Flask 3.0.0 - Web framework
  - Flask-CORS 4.0.0 - CORS support
  - bcrypt 4.1.2 - Password hashing
  - pytest 7.4.3 - Testing framework
  - pytest-cov 4.1.0 - Test coverage
  - hypothesis 6.92.2 - Property-based testing
  - Pillow 10.4.0 - Image processing
  - cairosvg 2.7.1 - SVG rendering
  - python-dotenv 1.0.0 - Environment variables
- Basic Flask application with health check endpoint
- Test configuration with pytest
- Basic unit tests for application setup
- Documentation:
  - README.md - Project overview
  - QUICKSTART.md - Quick start guide
  - CHANGELOG.md - This file
  - .env.example - Environment variables template
- Git configuration (.gitignore)

### Requirements Addressed
- 7.1: Docker containerization
- 7.2: HTTP port exposure for web access
- 7.6: All necessary dependencies included

## [Unreleased]

### Planned
- Database schema and models (Task 2)
- Core business logic services (Task 3)
- Authentication and authorization (Task 5)
- Visualization service (Task 6)
- Export service (Task 7)
- REST API endpoints (Task 9)
- Web interface (Task 10)
- Integration testing (Task 12)
