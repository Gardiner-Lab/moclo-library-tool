# Changelog

All notable changes to the MoClo Library Tool project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.10.0] - 2026-09-30

### Added
- CRISPR Guide Designer page (`/guide-designer`). Enter one or more 20 bp guide
  sequences and auto-generate a full Golden Gate cloning strategy for the
  polycistronic tRNA-sgRNA system of the Hahn et al. (2020) plant genome-editing
  MoClo toolkit:
  - Level -1 oligos to order, each guide flanked by the toolkit fusion overhangs
    (TGCA / AAAC) and a BpiI site with an independent, hairpin-optimised 3 bp
    binding pad per end (hairpin free energy via `seqfold`).
  - Position-specific Level 0 acceptor modules, Pol III promoter, endlinker, and
    the Level 1 (into pICH47742 by default) and Level 2 assembly steps.
- "Generate Level 0 cassette part(s)" action that assembles the full Level 0
  module (the real toolkit acceptor vector with the guide spliced into the lacZ
  site) and saves each as a Part (level 0, unit gRNA). The part stores the
  complete assembled module sequence plus the MoClo cloning strategy and oligo
  annealing protocol (heat block to 100 C, then cool to room temperature).
- Bundled the toolkit Level 0 vector GenBank sequences (`app/data/toolkit_gb/`)
  so module assembly works offline. These files are from Hahn et al. 2020
  (Figshare, CC BY 4.0); attribution retained in `ATTRIBUTION.md`.
- `seqfold` dependency for nucleic-acid secondary-structure (hairpin) analysis.

### Changed
- Admin dashboard: the automatic-updates panel now states that Watchtower checks
  weekly (previously said hourly), matching the actual `--interval 604800`
  configuration.

## [1.9.0] - 2026-09-30

### Added
- Orientation-aware assembly. Level 1 transcription units cloned into a
  reverse-orientation position acceptor (for example pICH47802, "Position 1
  reverse") are now recognised as compatible and are reverse-complemented into
  the assembled construct. Compatibility is checked in both orientations, the
  first part is treated as a free anchor (either orientation), and each part's
  chosen orientation is recorded in the cassette's part metadata
  (`orientation`, plus the presented and stored overhangs).
- `overhang_source` field in the part upload response, indicating whether the
  4bp overhangs came from the GenBank `/overhang_*` qualifiers or were computed
  from restriction sites.

### Changed
- Part GenBank upload now prefers the `/overhang_5prime` and `/overhang_3prime`
  qualifiers as the authoritative overhangs, even when Type IIS sites are
  present. The previous site-based computation used only the first forward and
  first reverse site, so a construct with an internal recognition site (common
  in Level 1 cassettes) could get the wrong 4bp overhangs that never matched a
  neighbouring part. When several features carry overhang qualifiers, the
  whole-part feature (largest span) is used.
- `Part.find_compatible_before` / `find_compatible_after` now also match
  reverse-complement overhangs so reverse-orientation partners are found.

### Fixed
- Level 1 cassettes with an internal BpiI site (e.g. a gRNA construct) no longer
  get mis-read overhangs on upload, so they chain correctly into a Level 2
  assembly.

## [1.8.0] - 2026-09-02

### Added
- `ExpressionCassette` part type for Level 1 files. Bulk upload offers only
  "Expression cassette" or "Non-coding other" for a Level 1 or Level 2 row.
- Per-file part-type selector in bulk upload, pre-filled from the filename, with
  "All types" batch buttons.
- Coding-sequence check and translation for `Coding` and `ExpressionCassette`
  parts: `GET /api/parts/<id>/translation`, a Translation section in the part
  detail view, and a `coding_warning` in upload and edit responses.
- Level 1 and Level 2 constructs track which parts are coding: `coding_parts`
  per cassette, `has_coding` / `coding_parts` per transcription unit, and a
  `coding_units` summary. Cassette and plasmid detail views report them.
- Easy in-place updates: `docker-compose.watchtower.yml` for automatic updates,
  and an Admin dashboard panel with copy-paste commands for a one-shot host
  update or enabling Watchtower. `make update-auto`.

### Changed
- Introns are now recognised from a part's stored GenBank features, not only the
  `INTRON_ANNOTATIONS` comment, so a CDS with annotated introns splices and
  translates (verified on a 13-intron dCas9 part).
- Changing a part's type recomputes its translation and refreshes every cassette
  that uses it.

### Fixed
- `GET /api/cassettes/<id>/translation` returned 500 from a doubled auth decorator.
- Bulk backbone uploads use the existing `/api/backbones` endpoint and surface its
  `message` field in the results log.

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
