# MySQL to PostgreSQL Migration Tool

A comprehensive Python tool for migrating databases from MySQL to PostgreSQL, preserving schema structure, data, relationships, and constraints.

**Author:** Pratush Mishra  
**Date:** December 27, 2025

## Features

- **Complete Schema Migration**: Automatically converts MySQL data types to PostgreSQL equivalents
- **Data Migration**: Batch processing with progress bars for efficient data transfer
- **Relationship Preservation**: Maintains foreign key constraints with proper dependency ordering
- **Index & Constraint Migration**: Preserves indexes and unique constraints
- **Auto-increment Handling**: Correctly migrates and updates PostgreSQL sequences
- **Data Validation**: Validates row counts and foreign key integrity after migration
- **Dependency Management**: Handles table dependencies and circular references
- **Error Handling**: Comprehensive error handling with retry mechanisms
- **Logging**: Detailed logging to `migration.log` for troubleshooting
- **Progress Tracking**: Real-time progress bars using `tqdm`
- **Flexible Configuration**: Supports environment variables or interactive prompts

## Requirements

- Python 3.7+
- MySQL database (source)
- PostgreSQL database (target)
- Network access to both databases

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd migration
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Interactive Mode

Run the script and provide credentials when prompted:

```bash
python MigrationScript.py
```

The script will prompt you for:
- MySQL connection details (host, port, username, password, database)
- PostgreSQL connection details (host, port, username, password, database)

### Environment Variables Mode

Set the following environment variables to automate the migration:

**MySQL Configuration:**
```bash
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=your_mysql_user
export MYSQL_PASSWORD=your_mysql_password
export MYSQL_DATABASE=your_mysql_database
```

**PostgreSQL Configuration:**
```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_USER=your_pg_user
export POSTGRES_PASSWORD=your_pg_password
export POSTGRES_DATABASE=your_pg_database
```

Then run:
```bash
python MigrationScript.py
```

### Windows (PowerShell)

```powershell
$env:MYSQL_HOST="localhost"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="your_mysql_user"
$env:MYSQL_PASSWORD="your_mysql_password"
$env:MYSQL_DATABASE="your_mysql_database"

$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_USER="your_pg_user"
$env:POSTGRES_PASSWORD="your_pg_password"
$env:POSTGRES_DATABASE="your_pg_database"

python MigrationScript.py
```

## Migration Process

The tool performs migration in the following stages:

1. **Schema Creation**: Creates all tables in PostgreSQL with proper data type mappings
2. **Data Migration**: Transfers data in batches (1000 rows at a time) with progress tracking
3. **Sequence Updates**: Updates PostgreSQL sequences to continue from migrated auto-increment values
4. **Index Creation**: Creates indexes and unique constraints
5. **Foreign Key Constraints**: Adds foreign key relationships with proper dependency ordering
6. **Validation**: Validates data integrity and foreign key relationships
7. **Report Generation**: Generates a comprehensive migration report

## Data Type Mappings

| MySQL Type | PostgreSQL Type |
|------------|----------------|
| `int` | `INTEGER` |
| `bigint` | `BIGINT` |
| `tinyint` | `SMALLINT` |
| `varchar(n)` | `VARCHAR(n)` |
| `text` | `TEXT` |
| `datetime` | `TIMESTAMP` |
| `timestamp` | `TIMESTAMP` |
| `decimal` | `NUMERIC` |
| `float` | `REAL` |
| `double` | `DOUBLE PRECISION` |
| `bit` | `BOOLEAN` |
| `enum` | `TEXT` |
| `json` | `JSONB` |
| `blob` | `BYTEA` |
| `auto_increment` | `SERIAL` or `BIGSERIAL` |

## Important Notes

### Case Sensitivity

- **Table and column names are converted to lowercase** in PostgreSQL for case-insensitive behavior
- This is a design decision to handle MySQL's case-insensitive behavior on Windows
- If you need to preserve exact case, you may need to modify the script

### Foreign Keys

- Foreign keys are created as `DEFERRABLE INITIALLY DEFERRED` to handle dependency ordering
- Foreign key actions (CASCADE, RESTRICT, SET NULL, etc.) are preserved from MySQL

### Invalid Dates

- MySQL's invalid dates (like `0000-00-00`) are converted to `NULL` in PostgreSQL
- Date validation ensures only valid dates are migrated

### Transaction Safety

- The entire migration runs in a transaction
- If any error occurs, the transaction is rolled back
- Always backup your PostgreSQL database before running the migration

## Output

The tool generates:

1. **Console Output**: Real-time progress and status messages
2. **Migration Report**: Summary of migrated tables with row counts
3. **Log File**: Detailed log file (`migration.log`) with all operations

### Sample Migration Report

```
============================================================
MIGRATION REPORT
============================================================
Table: users                          MySQL:     1000 PostgreSQL:     1000 ✅ SUCCESS
  Auto-increment columns: id
Table: orders                         MySQL:     5000 PostgreSQL:     5000 ✅ SUCCESS
  Auto-increment columns: order_id
------------------------------------------------------------
TOTAL RECORDS: MySQL:     6000 PostgreSQL:     6000
============================================================
```

## Troubleshooting

### Connection Errors

- Verify database credentials and network connectivity
- Ensure both MySQL and PostgreSQL servers are running
- Check firewall rules for database ports (3306 for MySQL, 5432 for PostgreSQL)

### Foreign Key Errors

- The tool handles circular dependencies automatically
- If foreign key creation fails, check the log file for details
- Orphaned records (violating foreign key constraints) will be logged as warnings

### Sequence Errors

- If sequence updates fail, check the log file
- The tool tries multiple sequence naming conventions automatically
- You may need to manually update sequences if auto-detection fails

### Data Type Issues

- Unsupported MySQL types default to `TEXT` in PostgreSQL
- Review the migration log for any type conversion warnings
- You may need to manually adjust column types after migration

## Limitations

- **Stored Procedures/Triggers**: Not migrated (PostgreSQL uses different syntax)
- **Views**: Not migrated (requires manual conversion)
- **User Permissions**: Not migrated
- **Case Sensitivity**: Table/column names are lowercased
- **MySQL-specific Features**: Some MySQL-specific features may not have direct PostgreSQL equivalents

## Security Considerations

- **Never commit credentials** to version control
- Use environment variables for production deployments
- The script uses parameterized queries to prevent SQL injection
- Passwords are hidden when using interactive mode (`getpass`)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Pratush Mishra**  
Software Developer  
December 27, 2025

## Support

For issues, questions, or contributions, please open an issue on the GitHub repository.

## Changelog

### Version 1.0.0
- Initial release
- Full schema and data migration support
- Foreign key and index migration
- Auto-increment sequence handling
- Data validation and reporting
- Enhanced security with proper SQL identifier escaping
- Improved error handling and logging
- Retry mechanism for database operations

