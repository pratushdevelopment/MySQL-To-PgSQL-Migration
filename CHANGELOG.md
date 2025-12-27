# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-27

### Added
- Initial release of MySQL to PostgreSQL migration tool
- Complete schema migration with data type mapping
- Data migration with batch processing and progress bars
- Foreign key constraint migration with dependency ordering
- Index and unique constraint migration
- Auto-increment sequence handling
- Data integrity validation (row counts, foreign keys)
- Comprehensive logging to `migration.log`
- Environment variable support for automation
- Interactive credential prompts
- Migration report generation
- Circular dependency detection and handling
- Invalid date handling (0000-00-00 → NULL)
- Binary data support
- Transaction safety with rollback on errors

### Security
- Proper SQL identifier escaping using `psycopg2.sql.Identifier`
- Parameterized queries for all user data
- Password masking in interactive mode
- No credentials stored in code or config files

### Technical Details
- Python 3.7+ compatibility
- Uses `mysql-connector-python` for MySQL connections
- Uses `psycopg2` for PostgreSQL connections
- Progress tracking with `tqdm`
- Retry mechanism for database operations
- Case-insensitive table/column name handling (lowercased)

