"""
MySQL to PostgreSQL Migration Tool
Version: 1.0.0

A comprehensive tool for migrating databases from MySQL to PostgreSQL,
preserving schema structure, data, relationships, and constraints.

Author: Pratush Mishra
Date: December 27, 2025
"""

import mysql.connector
import psycopg2
import psycopg2.extras
import psycopg2.sql
import logging
import re
from datetime import datetime
import getpass
import sys
import os
import time
from tqdm import tqdm  # For progress bars

# Version information
__version__ = "1.0.0"
__author__ = "Pratush Mishra"
__date__ = "2025-12-27"

# Configure logging
logging.basicConfig(
    filename='migration.log', 
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'  # Append mode to preserve previous logs
)

# Type Mapping from MySQL to PostgreSQL
# This dictionary maps MySQL data types to their PostgreSQL equivalents
TYPE_MAPPING = {
    'int': 'INTEGER',
    'bigint': 'BIGINT',
    'smallint': 'SMALLINT',
    'tinyint': 'SMALLINT',
    'mediumint': 'INTEGER',
    'varchar': 'VARCHAR',
    'char': 'CHAR',
    'text': 'TEXT',
    'longtext': 'TEXT',
    'mediumtext': 'TEXT',
    'tinytext': 'TEXT',
    'datetime': 'TIMESTAMP',
    'timestamp': 'TIMESTAMP',
    'date': 'DATE',
    'time': 'TIME',
    'decimal': 'NUMERIC',
    'float': 'REAL',
    'double': 'DOUBLE PRECISION',
    'bit': 'BOOLEAN',
    'enum': 'TEXT',
    'set': 'TEXT',
    'json': 'JSONB',
    'blob': 'BYTEA',
    'longblob': 'BYTEA',
    'mediumblob': 'BYTEA',
    'tinyblob': 'BYTEA',
    'binary': 'BYTEA',
    'varbinary': 'BYTEA',
    'year': 'INTEGER'
}

def retry_operation(max_retries=3, delay=1):
    """
    Retry decorator for database operations
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (mysql.connector.Error, psycopg2.Error) as e:
                    if attempt == max_retries - 1:
                        raise e
                    logging.warning(f"⚠ Attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

def get_credentials():
    """
    Get MySQL and PostgreSQL connection credentials
    Supports environment variables for automation, falls back to interactive prompts
    """
    # Check for environment variables first
    mysql_host = os.getenv('MYSQL_HOST', '')
    mysql_port = os.getenv('MYSQL_PORT', '')
    mysql_user = os.getenv('MYSQL_USER', '')
    mysql_password = os.getenv('MYSQL_PASSWORD', '')
    mysql_db = os.getenv('MYSQL_DATABASE', '')
    
    pg_host = os.getenv('POSTGRES_HOST', '')
    pg_port = os.getenv('POSTGRES_PORT', '')
    pg_user = os.getenv('POSTGRES_USER', '')
    pg_password = os.getenv('POSTGRES_PASSWORD', '')
    pg_db = os.getenv('POSTGRES_DATABASE', '')
    
    # If environment variables are not set, use interactive prompts
    if not all([mysql_user, mysql_password, mysql_db, pg_user, pg_password, pg_db]):
        print("=== MySQL Credentials ===")
        mysql_host = mysql_host or input("MySQL Host (default: localhost): ") or "localhost"
        mysql_port = mysql_port or input("MySQL Port (default: 3306): ") or "3306"
        mysql_user = mysql_user or input("MySQL Username: ")
        mysql_password = mysql_password or getpass.getpass("MySQL Password: ")
        mysql_db = mysql_db or input("MySQL Database: ")
        
        print("\n=== PostgreSQL Credentials ===")
        pg_host = pg_host or input("PostgreSQL Host (default: localhost): ") or "localhost"
        pg_port = pg_port or input("PostgreSQL Port (default: 5432): ") or "5432"
        pg_user = pg_user or input("PostgreSQL Username: ")
        pg_password = pg_password or getpass.getpass("PostgreSQL Password: ")
        pg_db = pg_db or input("PostgreSQL Database: ")
    
    # Convert ports to integers
    mysql_port = int(mysql_port) if mysql_port else 3306
    pg_port = int(pg_port) if pg_port else 5432
    
    # Validate required fields
    if not mysql_user or not mysql_password or not mysql_db:
        raise ValueError("MySQL username, password, and database are required")
    if not pg_user or not pg_password or not pg_db:
        raise ValueError("PostgreSQL username, password, and database are required")
    
    # Validate port numbers
    if not (1 <= mysql_port <= 65535):
        raise ValueError("MySQL port must be between 1 and 65535")
    if not (1 <= pg_port <= 65535):
        raise ValueError("PostgreSQL port must be between 1 and 65535")
    
    return {
        "mysql": {
            "host": mysql_host,
            "port": mysql_port,
            "user": mysql_user,
            "password": mysql_password,
            "database": mysql_db
        },
        "postgres": {
            "host": pg_host,
            "port": pg_port,
            "user": pg_user,
            "password": pg_password,
            "database": pg_db
        }
    }

def sanitize_row(row):
    """
    Clean and prepare row data for PostgreSQL
    Handles NULL values, date formats, and binary data
    """
    sanitized = {}
    for key, value in row.items():
        # Handle None values
        if value is None:
            sanitized[key] = None
        # Handle date/datetime strings
        elif isinstance(value, str) and re.match(r'^\d{4}-\d{2}-\d{2}', value):
            try:
                # Handle invalid dates like 0000-00-00
                if value.startswith("0000-00-00"):
                    sanitized[key] = None
                else:
                    # Validate the date format
                    datetime.strptime(value[:10], "%Y-%m-%d")
                    sanitized[key] = value
            except ValueError:
                sanitized[key] = None
        # Handle binary data
        elif isinstance(value, bytes):
            sanitized[key] = value
        # Default case
        else:
            sanitized[key] = value
    return sanitized

def get_mysql_tables(mysql_cursor, db_name):
    """
    Get a list of all tables in the MySQL database
    """
    mysql_cursor.execute("SHOW TABLES")
    tables = mysql_cursor.fetchall()
    
    # The column name depends on the database name
    column_name = f'Tables_in_{db_name}'
    
    # Handle case where column name might be different
    if len(tables) > 0 and column_name not in tables[0]:
        column_name = list(tables[0].keys())[0]
        
    return [row[column_name] for row in tables]

def get_table_schema(mysql_cursor, table_name):
    """
    Get the schema definition for a MySQL table
    Returns column definitions and primary keys with preserved case
    """
    mysql_cursor.execute(f"DESCRIBE `{table_name}`")
    columns = mysql_cursor.fetchall()
    
    column_defs = []
    primary_keys = []
    column_mapping = {}  # To track original column names to preserve case
    
    for column in columns:
        col_name = column['Field']
        col_type = column['Type']
        col_null = column['Null']
        col_key = column['Key']
        col_default = column['Default']
        col_extra = column['Extra']
        
        # Store original column name for case preservation
        column_mapping[col_name.lower()] = col_name
        
        # Extract base type (e.g., varchar from varchar(255))
        base_type = re.match(r'(\w+)', col_type.lower()).group(1)
        
        # Map MySQL type to PostgreSQL type
        pg_type = TYPE_MAPPING.get(base_type, 'TEXT')
        
        # Handle size for types like varchar, char, etc.
        if '(' in col_type and base_type in ['varchar', 'char', 'decimal', 'numeric']:
            size = re.search(r'\((.*?)\)', col_type).group(1)
            pg_type += f"({size})"
        
        # Handle auto_increment
        if 'auto_increment' in col_extra:
            pg_type = "SERIAL" if pg_type == "INTEGER" else "BIGSERIAL" if pg_type == "BIGINT" else pg_type
        
        # Build column definition - use lowercase for case-insensitive behavior
        column_def = f'{col_name.lower()} {pg_type}'
        
        # Add NOT NULL constraint if needed
        if col_null == 'NO':
            column_def += " NOT NULL"
        
        # Add default value if present and not auto_increment
        if col_default is not None and 'auto_increment' not in col_extra:
            if col_default == 'CURRENT_TIMESTAMP':
                column_def += " DEFAULT CURRENT_TIMESTAMP"
            elif base_type in ['char', 'varchar', 'text', 'enum']:
                # Escape single quotes in default values to prevent SQL injection
                escaped_default = col_default.replace("'", "''")
                column_def += f" DEFAULT '{escaped_default}'"
            else:
                # For numeric defaults, validate they're safe
                try:
                    float(col_default)  # Test if it's a valid number
                    column_def += f" DEFAULT {col_default}"
                except ValueError:
                    # If not a valid number, treat as string
                    escaped_default = col_default.replace("'", "''")
                    column_def += f" DEFAULT '{escaped_default}'"
        
        column_defs.append(column_def)
        
        # Track primary keys - use lowercase for case-insensitive behavior
        if col_key == "PRI":
            primary_keys.append(col_name.lower())
    
    return column_defs, primary_keys, column_mapping

def get_foreign_keys(mysql_cursor, table_name, db_name):
    """
    Get foreign key relationships for a MySQL table
    Returns a list of foreign key definitions with preserved case and actions
    """
    query = """
    SELECT
        kcu.COLUMN_NAME,
        kcu.REFERENCED_TABLE_NAME,
        kcu.REFERENCED_COLUMN_NAME,
        kcu.CONSTRAINT_NAME,
        rc.UPDATE_RULE,
        rc.DELETE_RULE
    FROM
        INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
    LEFT JOIN
        INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
        ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
        AND kcu.TABLE_SCHEMA = rc.CONSTRAINT_SCHEMA
    WHERE
        kcu.TABLE_SCHEMA = %s AND
        kcu.TABLE_NAME = %s AND
        kcu.REFERENCED_TABLE_NAME IS NOT NULL
    """
    mysql_cursor.execute(query, (db_name, table_name))
    return mysql_cursor.fetchall()

def get_table_dependencies(mysql_cursor, db_name):
    """
    Get table dependency order to ensure proper migration sequence
    Returns tables ordered by dependency (parent tables first)
    Handles circular dependencies by breaking them
    """
    query = """
    SELECT DISTINCT
        t1.TABLE_NAME as child_table,
        t2.TABLE_NAME as parent_table
    FROM
        INFORMATION_SCHEMA.KEY_COLUMN_USAGE t1
    JOIN
        INFORMATION_SCHEMA.KEY_COLUMN_USAGE t2
        ON t1.REFERENCED_TABLE_NAME = t2.TABLE_NAME
        AND t1.REFERENCED_COLUMN_NAME = t2.COLUMN_NAME
    WHERE
        t1.TABLE_SCHEMA = %s AND
        t2.TABLE_SCHEMA = %s AND
        t1.REFERENCED_TABLE_NAME IS NOT NULL
    """
    mysql_cursor.execute(query, (db_name, db_name))
    dependencies = mysql_cursor.fetchall()
    
    # Build dependency graph
    graph = {}
    in_degree = {}
    
    # Get all tables first
    all_tables = get_mysql_tables(mysql_cursor, db_name)
    for table in all_tables:
        graph[table] = []
        in_degree[table] = 0
    
    # Add dependencies
    for dep in dependencies:
        child = dep['child_table']
        parent = dep['parent_table']
        if parent in graph and child != parent:  # Avoid self-references
            graph[parent].append(child)
            in_degree[child] += 1
    
    # Topological sort with cycle detection
    queue = [table for table in all_tables if in_degree[table] == 0]
    ordered_tables = []
    processed_count = 0
    
    while queue:
        current = queue.pop(0)
        ordered_tables.append(current)
        processed_count += 1
        
        for child in graph[current]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
    
    # Handle circular dependencies
    if processed_count < len(all_tables):
        remaining_tables = [table for table in all_tables if table not in ordered_tables]
        logging.warning(f"⚠ Circular dependencies detected. Adding remaining tables: {remaining_tables}")
        ordered_tables.extend(remaining_tables)
    
    return ordered_tables

def create_pg_table(pg_cursor, table_name, schema, pkeys):
    """
    Create a PostgreSQL table with the given schema
    Uses lowercase table names for case-insensitive behavior
    Uses proper SQL identifier escaping for security
    """
    # Use lowercase table name for case-insensitive behavior
    # Use proper SQL identifier escaping
    drop_query = psycopg2.sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
        psycopg2.sql.Identifier(table_name.lower())
    )
    pg_cursor.execute(drop_query)
    
    # Build CREATE TABLE query with proper escaping
    schema_sql = psycopg2.sql.SQL(", ").join([
        psycopg2.sql.SQL(col_def) for col_def in schema
    ])
    
    if pkeys:
        pkeys_sql = psycopg2.sql.SQL(", ").join([
            psycopg2.sql.Identifier(pk) for pk in pkeys
        ])
        create_query = psycopg2.sql.SQL("CREATE TABLE {} ({}, PRIMARY KEY ({}))").format(
            psycopg2.sql.Identifier(table_name.lower()),
            schema_sql,
            pkeys_sql
        )
    else:
        create_query = psycopg2.sql.SQL("CREATE TABLE {} ({})").format(
            psycopg2.sql.Identifier(table_name.lower()),
            schema_sql
        )
    
    pg_cursor.execute(create_query)
    logging.info(f"✅ Created PostgreSQL table: {table_name.lower()}")

def add_foreign_keys(pg_cursor, table_name, foreign_keys):
    """
    Add foreign key constraints to a PostgreSQL table
    Uses lowercase identifiers for case-insensitive behavior
    Uses proper SQL identifier escaping for security
    """
    for fk in foreign_keys:
        column_name = fk['COLUMN_NAME'].lower()
        ref_table = fk['REFERENCED_TABLE_NAME'].lower()
        ref_column = fk['REFERENCED_COLUMN_NAME'].lower()
        update_rule = fk.get('UPDATE_RULE', 'RESTRICT')
        delete_rule = fk.get('DELETE_RULE', 'RESTRICT')
        
        constraint_name = f"fk_{table_name.lower()}_{column_name}"
        
        # Map MySQL actions to PostgreSQL actions
        action_mapping = {
            'RESTRICT': 'RESTRICT',
            'CASCADE': 'CASCADE',
            'SET NULL': 'SET NULL',
            'NO ACTION': 'NO ACTION',
            'SET DEFAULT': 'SET DEFAULT'
        }
        
        pg_update_action = action_mapping.get(update_rule, 'RESTRICT')
        pg_delete_action = action_mapping.get(delete_rule, 'RESTRICT')
        
        # Use proper SQL identifier escaping
        try:
            query = psycopg2.sql.SQL("""
                ALTER TABLE {} 
                ADD CONSTRAINT {} 
                FOREIGN KEY ({}) 
                REFERENCES {} ({})
                ON UPDATE {} 
                ON DELETE {}
                DEFERRABLE INITIALLY DEFERRED
            """).format(
                psycopg2.sql.Identifier(table_name.lower()),
                psycopg2.sql.Identifier(constraint_name),
                psycopg2.sql.Identifier(column_name),
                psycopg2.sql.Identifier(ref_table),
                psycopg2.sql.Identifier(ref_column),
                psycopg2.sql.SQL(pg_update_action),
                psycopg2.sql.SQL(pg_delete_action)
            )
            pg_cursor.execute(query)
            logging.info(f"✅ Added foreign key: {constraint_name} (UPDATE: {pg_update_action}, DELETE: {pg_delete_action})")
        except Exception as e:
            logging.warning(f"⚠ Could not add foreign key {constraint_name}: {e}")

def get_indexes_and_constraints(mysql_cursor, table_name, db_name):
    """
    Get indexes and unique constraints from MySQL table
    """
    # Get indexes
    index_query = """
    SELECT DISTINCT
        INDEX_NAME,
        COLUMN_NAME,
        NON_UNIQUE,
        INDEX_TYPE
    FROM
        INFORMATION_SCHEMA.STATISTICS
    WHERE
        TABLE_SCHEMA = %s AND
        TABLE_NAME = %s AND
        INDEX_NAME != 'PRIMARY'
    ORDER BY INDEX_NAME, SEQ_IN_INDEX
    """
    mysql_cursor.execute(index_query, (db_name, table_name))
    indexes = mysql_cursor.fetchall()
    
    # Group by index name
    index_groups = {}
    for idx in indexes:
        idx_name = idx['INDEX_NAME']
        if idx_name not in index_groups:
            index_groups[idx_name] = {
                'columns': [],
                'unique': idx['NON_UNIQUE'] == 0,
                'type': idx['INDEX_TYPE']
            }
        index_groups[idx_name]['columns'].append(idx['COLUMN_NAME'])
    
    return index_groups

def create_indexes_and_constraints(pg_cursor, table_name, indexes):
    """
    Create indexes and unique constraints in PostgreSQL
    Uses lowercase identifiers for case-insensitive behavior
    Uses proper SQL identifier escaping for security
    """
    for idx_name, idx_info in indexes.items():
        columns = [col.lower() for col in idx_info['columns']]
        
        if idx_info['unique']:
            # Create unique constraint
            constraint_name = f"uk_{table_name.lower()}_{idx_name.lower()}"
            try:
                column_identifiers = [psycopg2.sql.Identifier(col) for col in columns]
                query = psycopg2.sql.SQL("ALTER TABLE {} ADD CONSTRAINT {} UNIQUE ({})").format(
                    psycopg2.sql.Identifier(table_name.lower()),
                    psycopg2.sql.Identifier(constraint_name),
                    psycopg2.sql.SQL(", ").join(column_identifiers)
                )
                pg_cursor.execute(query)
                logging.info(f"✅ Added unique constraint: {constraint_name}")
            except Exception as e:
                logging.warning(f"⚠ Could not add unique constraint {constraint_name}: {e}")
        else:
            # Create regular index
            index_name = f"idx_{table_name.lower()}_{idx_name.lower()}"
            try:
                column_identifiers = [psycopg2.sql.Identifier(col) for col in columns]
                query = psycopg2.sql.SQL("CREATE INDEX {} ON {} ({})").format(
                    psycopg2.sql.Identifier(index_name),
                    psycopg2.sql.Identifier(table_name.lower()),
                    psycopg2.sql.SQL(", ").join(column_identifiers)
                )
                pg_cursor.execute(query)
                logging.info(f"✅ Created index: {index_name}")
            except Exception as e:
                logging.warning(f"⚠ Could not create index {index_name}: {e}")

def update_sequences(pg_cursor, table_name, mysql_cursor):
    """
    Update PostgreSQL sequences to continue from the highest migrated value
    This fixes the auto-increment reset issue
    Uses proper SQL identifier escaping for security
    """
    # Get all auto-increment columns from MySQL
    mysql_cursor.execute(f"DESCRIBE `{table_name}`")
    columns = mysql_cursor.fetchall()
    
    for column in columns:
        if 'auto_increment' in column['Extra']:
            col_name = column['Field']
            
            # Get the maximum value from the migrated data
            # Use proper SQL identifier escaping
            max_query = psycopg2.sql.SQL("SELECT MAX({}) FROM {}").format(
                psycopg2.sql.Identifier(col_name.lower()),
                psycopg2.sql.Identifier(table_name.lower())
            )
            pg_cursor.execute(max_query)
            max_val = pg_cursor.fetchone()[0]
            
            if max_val is not None:
                # PostgreSQL sequence naming convention: tablename_columnname_seq
                # Try multiple sequence naming conventions
                sequence_names = [
                    f"{table_name.lower()}_{col_name.lower()}_seq",
                    f"{table_name}_{col_name}_seq",
                    f"{table_name.lower()}_{col_name}_seq",
                    f"{table_name}_{col_name.lower()}_seq"
                ]
                
                sequence_updated = False
                for seq_name in sequence_names:
                    try:
                        # Use proper SQL identifier escaping
                        setval_query = psycopg2.sql.SQL("SELECT setval({}, %s, true)").format(
                            psycopg2.sql.Literal(seq_name)
                        )
                        pg_cursor.execute(setval_query, (max_val,))
                        logging.info(f"✅ Updated sequence {seq_name} to start from {max_val + 1}")
                        sequence_updated = True
                        break
                    except Exception as e:
                        continue
                
                if not sequence_updated:
                    logging.warning(f"⚠ Could not update sequence for {table_name}.{col_name}. Tried: {', '.join(sequence_names)}")
                    # Try to find the actual sequence name from PostgreSQL
                    try:
                        find_seq_query = psycopg2.sql.SQL("""
                            SELECT sequence_name 
                            FROM information_schema.sequences 
                            WHERE sequence_schema = 'public' 
                            AND sequence_name LIKE {}
                        """).format(psycopg2.sql.Literal(f"%{table_name.lower()}%{col_name.lower()}%"))
                        pg_cursor.execute(find_seq_query)
                        result = pg_cursor.fetchone()
                        if result:
                            actual_seq_name = result[0]
                            setval_query = psycopg2.sql.SQL("SELECT setval({}, %s, true)").format(
                                psycopg2.sql.Literal(actual_seq_name)
                            )
                            pg_cursor.execute(setval_query, (max_val,))
                            logging.info(f"✅ Updated sequence {actual_seq_name} to start from {max_val + 1}")
                    except Exception as e2:
                        logging.error(f"❌ Failed to update sequence for {table_name}.{col_name}: {e2}")

def validate_foreign_keys(mysql_cursor, pg_cursor, table_name, db_name):
    """
    Validate that foreign key relationships are properly maintained
    Uses proper SQL identifier escaping for security
    """
    foreign_keys = get_foreign_keys(mysql_cursor, table_name, db_name)
    
    for fk in foreign_keys:
        column_name = fk['COLUMN_NAME']
        ref_table = fk['REFERENCED_TABLE_NAME']
        ref_column = fk['REFERENCED_COLUMN_NAME']
        
        # Check for orphaned records using proper SQL escaping
        query = psycopg2.sql.SQL("""
            SELECT COUNT(*) FROM {} t1
            WHERE t1.{} IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM {} t2
                WHERE t2.{} = t1.{}
            )
        """).format(
            psycopg2.sql.Identifier(table_name.lower()),
            psycopg2.sql.Identifier(column_name.lower()),
            psycopg2.sql.Identifier(ref_table.lower()),
            psycopg2.sql.Identifier(ref_column.lower()),
            psycopg2.sql.Identifier(column_name.lower())
        )
        
        pg_cursor.execute(query)
        orphaned_count = pg_cursor.fetchone()[0]
        
        if orphaned_count > 0:
            logging.warning(f"⚠ Found {orphaned_count} orphaned records in {table_name}.{column_name}")
            return False
        else:
            logging.info(f"✅ Foreign key validation passed for {table_name}.{column_name}")
    
    return True

def validate_data_integrity(mysql_cursor, pg_cursor, table_name):
    """
    Validate that data migration was successful by comparing row counts
    Uses proper SQL identifier escaping for security
    """
    # Get MySQL row count
    mysql_cursor.execute(f"SELECT COUNT(*) as count FROM `{table_name}`")
    mysql_count = mysql_cursor.fetchone()['count']
    
    # Get PostgreSQL row count using proper SQL escaping
    query = psycopg2.sql.SQL("SELECT COUNT(*) FROM {}").format(
        psycopg2.sql.Identifier(table_name.lower())
    )
    pg_cursor.execute(query)
    pg_count = pg_cursor.fetchone()[0]
    
    if mysql_count != pg_count:
        logging.error(f"❌ Row count mismatch in {table_name}: MySQL={mysql_count}, PostgreSQL={pg_count}")
        return False
    else:
        logging.info(f"✅ Row count validated for {table_name}: {pg_count} rows")
        return True

def migrate_table_data(mysql_cursor, pg_cursor, pg_conn, table_name, column_mapping=None):
    """
    Migrate data from MySQL table to PostgreSQL table
    Preserves case by quoting all identifiers
    Uses column_mapping to ensure case consistency
    """
    # Get row count for progress bar
    mysql_cursor.execute(f"SELECT COUNT(*) as count FROM `{table_name}`")
    row_count = mysql_cursor.fetchone()['count']
    
    if row_count == 0:
        logging.info(f"⚠ No data in table: {table_name}")
        return
    
    # Get data in batches
    batch_size = 1000
    total_inserted = 0
    
    # Create progress bar
    progress = tqdm(total=row_count, desc=f"Migrating {table_name}")
    
    for offset in range(0, row_count, batch_size):
        mysql_cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {batch_size} OFFSET {offset}")
        rows = mysql_cursor.fetchall()
        
        if not rows:
            break
            
        # Get column names from the first row
        original_col_names = list(rows[0].keys())
        
        # Use lowercase column names for case-insensitive behavior
        lowercase_cols = [col.lower() for col in original_col_names]
        
        # Use proper SQL identifier escaping for table and column names
        # Table and column names come from database schema, so we use Identifier for safety
        table_identifier = psycopg2.sql.Identifier(table_name.lower())
        column_identifiers = [psycopg2.sql.Identifier(col) for col in lowercase_cols]
        
        # Build INSERT query with proper escaping for identifiers
        # Use %s placeholders for values (execute_batch requires string format with %s)
        placeholders_str = ', '.join(['%s'] * len(original_col_names))
        insert_query = psycopg2.sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            table_identifier,
            psycopg2.sql.SQL(", ").join(column_identifiers),
            psycopg2.sql.SQL(placeholders_str)
        )
        # Convert to string for execute_batch
        insert_query_str = insert_query.as_string(pg_cursor)
        
        sanitized_batch = []
        for row in rows:
            try:
                sanitized = sanitize_row(row)
                sanitized_batch.append(tuple(sanitized[col] for col in original_col_names))
            except Exception as e:
                logging.warning(f"Skipping row in {table_name} due to sanitization error: {e}")
        
        try:
            psycopg2.extras.execute_batch(pg_cursor, insert_query_str, sanitized_batch)
            pg_conn.commit()
            total_inserted += len(sanitized_batch)
            progress.update(len(sanitized_batch))
        except Exception as batch_err:
            logging.error(f"❌ Batch insert error in {table_name}: {batch_err}")
            pg_conn.rollback()
            
            # Try inserting row by row
            for val in sanitized_batch:
                try:
                    pg_cursor.execute(insert_query_str, val)
                    pg_conn.commit()
                    total_inserted += 1
                    progress.update(1)
                except Exception as row_err:
                    pg_conn.rollback()
                    logging.warning(f"⚠ Failed row insert in {table_name}: {row_err}")
    
    progress.close()
    logging.info(f"✅ Migrated {total_inserted} of {row_count} records from {table_name}")

def generate_migration_report(mysql_cursor, pg_cursor, tables, db_name):
    """
    Generate a comprehensive migration report
    """
    report = []
    report.append("=" * 60)
    report.append("MIGRATION REPORT")
    report.append("=" * 60)
    
    total_mysql_rows = 0
    total_pg_rows = 0
    
    for table in tables:
        # Get row counts
        mysql_cursor.execute(f"SELECT COUNT(*) as count FROM `{table}`")
        mysql_count = mysql_cursor.fetchone()['count']
        
        # Use proper SQL identifier escaping
        count_query = psycopg2.sql.SQL("SELECT COUNT(*) FROM {}").format(
            psycopg2.sql.Identifier(table.lower())
        )
        pg_cursor.execute(count_query)
        pg_count = pg_cursor.fetchone()[0]
        
        total_mysql_rows += mysql_count
        total_pg_rows += pg_count
        
        status = "✅ SUCCESS" if mysql_count == pg_count else "❌ MISMATCH"
        report.append(f"Table: {table:<30} MySQL: {mysql_count:>8} PostgreSQL: {pg_count:>8} {status}")
        
        # Check for auto-increment columns
        mysql_cursor.execute(f"DESCRIBE `{table}`")
        columns = mysql_cursor.fetchall()
        auto_increment_cols = [col['Field'] for col in columns if 'auto_increment' in col['Extra']]
        
        if auto_increment_cols:
            report.append(f"  Auto-increment columns: {', '.join(auto_increment_cols)}")
    
    report.append("-" * 60)
    report.append(f"TOTAL RECORDS: MySQL: {total_mysql_rows:>8} PostgreSQL: {total_pg_rows:>8}")
    report.append("=" * 60)
    
    return "\n".join(report)

def migrate_all(credentials):
    """
    Main migration function that orchestrates the entire process
    Handles case sensitivity throughout the migration
    Fixes foreign key dependency issues and auto-increment sequences
    """
    mysql_conn = None
    mysql_cursor = None
    pg_conn = None
    pg_cursor = None
    
    try:
        # Connect to MySQL
        logging.info("🔌 Connecting to MySQL...")
        mysql_conn = mysql.connector.connect(**credentials["mysql"])
        mysql_cursor = mysql_conn.cursor(dictionary=True)
        logging.info("✅ MySQL connection established")
        
        # Connect to PostgreSQL
        logging.info("🔌 Connecting to PostgreSQL...")
        pg_conn = psycopg2.connect(**credentials["postgres"])
        pg_cursor = pg_conn.cursor()
        logging.info("✅ PostgreSQL connection established")
        
        # Start transaction
        pg_conn.autocommit = False
        
        # Get all tables ordered by dependency (parent tables first)
        tables = get_table_dependencies(mysql_cursor, credentials["mysql"]["database"])
        
        if not tables:
            logging.warning("No tables found in MySQL.")
            return
        
        logging.info(f"📋 Migration order: {', '.join(tables)}")
        
        # Store column mappings for each table to preserve case
        column_mappings = {}
        
        # First pass: Create all tables without foreign keys
        logging.info("🏗️ Creating table structures...")
        for table in tables:
            logging.info(f"--- Creating Table: {table} ---")
            schema, pkeys, col_mapping = get_table_schema(mysql_cursor, table)
            create_pg_table(pg_cursor, table, schema, pkeys)
            column_mappings[table] = col_mapping
        
        # Second pass: Migrate data in dependency order
        logging.info("📦 Migrating data...")
        for table in tables:
            logging.info(f"--- Migrating Data for Table: {table} ---")
            migrate_table_data(mysql_cursor, pg_cursor, pg_conn, table, column_mappings[table])
            
            # Validate data integrity after each table
            if not validate_data_integrity(mysql_cursor, pg_cursor, table):
                logging.error(f"❌ Data validation failed for table: {table}")
                raise Exception(f"Data validation failed for table: {table}")
        
        # Third pass: Update auto-increment sequences
        logging.info("🔄 Updating auto-increment sequences...")
        for table in tables:
            logging.info(f"--- Updating Sequences for Table: {table} ---")
            update_sequences(pg_cursor, table, mysql_cursor)
        
        # Fourth pass: Add indexes and unique constraints
        logging.info("📇 Creating indexes and unique constraints...")
        for table in tables:
            logging.info(f"--- Creating Indexes for Table: {table} ---")
            indexes = get_indexes_and_constraints(mysql_cursor, table, credentials["mysql"]["database"])
            if indexes:
                create_indexes_and_constraints(pg_cursor, table, indexes)
        
        # Fifth pass: Add foreign keys in reverse dependency order
        logging.info("🔗 Adding foreign key constraints...")
        for table in reversed(tables):  # Reverse order to add child constraints last
            logging.info(f"--- Adding Foreign Keys for Table: {table} ---")
            foreign_keys = get_foreign_keys(mysql_cursor, table, credentials["mysql"]["database"])
            if foreign_keys:
                add_foreign_keys(pg_cursor, table, foreign_keys)
        
        # Sixth pass: Validate foreign key relationships
        logging.info("🔍 Validating foreign key relationships...")
        for table in tables:
            logging.info(f"--- Validating Foreign Keys for Table: {table} ---")
            if not validate_foreign_keys(mysql_cursor, pg_cursor, table, credentials["mysql"]["database"]):
                logging.warning(f"⚠ Foreign key validation issues found in table: {table}")
        
        # Generate migration report
        logging.info("📊 Generating migration report...")
        report = generate_migration_report(mysql_cursor, pg_cursor, tables, credentials["mysql"]["database"])
        logging.info(f"\n{report}")
        
        # Commit transaction
        pg_conn.commit()
        logging.info("🎯 All tables migrated successfully!")
        print("Migration completed successfully! Check migration.log for details.")
        print(f"\n{report}")
        
    except mysql.connector.Error as mysql_err:
        logging.error(f"❌ MySQL connection error: {mysql_err}")
        print(f"Error connecting to MySQL: {mysql_err}")
        if pg_conn:
            pg_conn.rollback()
        return
    except psycopg2.Error as pg_err:
        logging.error(f"❌ PostgreSQL connection error: {pg_err}")
        print(f"Error connecting to PostgreSQL: {pg_err}")
        if pg_conn:
            pg_conn.rollback()
        return
    except Exception as e:
        logging.error(f"❌ Migration failed: {e}")
        print(f"Migration failed: {e}")
        if pg_conn:
            pg_conn.rollback()
        return

    finally:
        # Close connections
        try:
            if mysql_cursor:
                mysql_cursor.close()
            if mysql_conn:
                mysql_conn.close()
            if pg_cursor:
                pg_cursor.close()
            if pg_conn:
                pg_conn.close()
        except Exception as e:
            logging.warning(f"⚠ Error closing connections: {e}")

if __name__ == "__main__":
    print("MySQL to PostgreSQL Migration Tool")
    print("=" * 40)
    print(f"Version: {__version__}")
    print("=" * 40)
    print()
    
    try:
        creds = get_credentials()
        print("\nStarting migration process...")
        print("=" * 40)
        migrate_all(creds)
    except ValueError as ve:
        print(f"\n❌ Input validation error: {ve}")
        logging.error(f"Input validation error: {ve}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n❌ Migration aborted by user.")
        logging.warning("Migration aborted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logging.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)