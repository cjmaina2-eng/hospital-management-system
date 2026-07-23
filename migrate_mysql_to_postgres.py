import os
import sys
from datetime import datetime, date
import pymysql
from urllib.parse import urlparse
from sqlalchemy import text
from app import db
from app import create_app

MIGRATION_ORDER = [
    'verification_codes',
    'services',
    'roles',
    'users',
    'user_roles',
    'doctors',
    'patients',
    'appointments',
    'medical_records',
    'lab_tests',
    'bills',
    'bill_items',
]

MYSQL_URL = os.environ.get('MYSQL_DATABASE_URL')
PG_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_DATABASE_URL')

PK_COLS = {
    'user_roles': ('user_id', 'role_id'),
}

BOOL_COLS = {
    ('users', 'is_active'),
    ('services', 'is_active'),
    ('verification_codes', 'used'),
    ('patients', 'is_admitted'),
}

DATE_COLS = {
    ('appointments', 'appointment_date_requested'),
    ('bills', 'due_date'),
}


def get_mysql_connection():
    if not MYSQL_URL:
        print('ERROR: Set MYSQL_DATABASE_URL env var (e.g. mysql+pymysql://user:pass@host:3306/hospital_db)')
        sys.exit(1)
    parsed = urlparse(MYSQL_URL)
    conn = pymysql.connect(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 3306,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path.lstrip('/'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )
    return conn


def fetch_table(conn, table):
    with conn.cursor() as cur:
        cur.execute(f'SELECT * FROM `{table}`')
        return cur.fetchall()


def convert_value(table, col, val):
    if val is None:
        return None
    if (table, col) in DATE_COLS:
        if isinstance(val, datetime) and not isinstance(val, date):
            return val.date()
    if (table, col) in BOOL_COLS:
        if isinstance(val, int):
            return bool(val)
    return val


def migrate_table(app, mysql_conn, table):
    rows = fetch_table(mysql_conn, table)
    if not rows:
        print(f'  {table}: 0 rows')
        return

    with app.app_context():
        cols = list(rows[0].keys())
        col_names = ', '.join([f'"{c}"' for c in cols])
        param_names = ', '.join([f':{c}' for c in cols])
        insert_sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({param_names})'

        pk = PK_COLS.get(table, ('id',))
        if len(pk) == 1:
            conflict_clause = f'ON CONFLICT ("{pk[0]}") DO NOTHING'
        else:
            conflict_clause = 'ON CONFLICT (' + ', '.join([f'"{k}"' for k in pk]) + ') DO NOTHING'
        insert_sql = f'{insert_sql} {conflict_clause}'

        batch = []
        for row in rows:
            batch.append({c: convert_value(table, c, row[c]) for c in cols})

        db.session.execute(text(insert_sql), batch)
        db.session.commit()

    print(f'  {table}: {len(rows)} rows migrated')


def update_sequences(app, table, pk_col='id'):
    if table not in PK_COLS:
        with app.app_context():
            db.session.execute(
                text(f'SELECT setval(pg_get_serial_sequence(:t, :pk), coalesce(max("{pk_col}"), 1), true) FROM "{table}"'),
                {'t': table, 'pk': pk_col},
            )
            db.session.commit()


def main():
    if not MYSQL_URL:
        print('ERROR: Set MYSQL_DATABASE_URL env var (e.g. mysql+pymysql://user:pass@host:3306/hospital_db)')
        sys.exit(1)
    if not PG_URL:
        print('ERROR: Set DATABASE_URL or POSTGRES_DATABASE_URL env var')
        sys.exit(1)

    app = create_app()
    app.config['SQLALCHEMY_DATABASE_URI'] = PG_URL

    print('Connecting to MySQL...')
    mysql_conn = get_mysql_connection()

    with app.app_context():
        db.create_all()

    print('Starting migration...')
    for table in MIGRATION_ORDER:
        migrate_table(app, mysql_conn, table)

    print('Updating sequences...')
    with app.app_context():
        for table in MIGRATION_ORDER:
            update_sequences(app, table)

    mysql_conn.close()
    print('Migration complete.')


if __name__ == '__main__':
    main()
