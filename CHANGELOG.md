# Changelog

All notable changes to the MoClo Library Tool project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
