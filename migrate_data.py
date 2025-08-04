import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from dotenv import load_dotenv
from models import Estoque, BarraEndereco, InventariosRealizados, UserCredential
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def create_sqlite_session():
    """Create a session for the SQLite database."""
    sqlite_uri = 'sqlite:///instance/database.db'
    engine = create_engine(sqlite_uri)
    return scoped_session(sessionmaker(bind=engine))

def create_postgres_session():
    """Create a session for the PostgreSQL database."""
    postgres_user = os.getenv('POSTGRES_USER')
    postgres_password = os.getenv('POSTGRES_PASSWORD')
    postgres_db = os.getenv('POSTGRES_DB')
    postgres_host = os.getenv('POSTGRES_HOST')
    postgres_port = os.getenv('POSTGRES_PORT')
    postgres_uri = f'postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}'
    engine = create_engine(postgres_uri)
    return scoped_session(sessionmaker(bind=engine))

def migrate_table(sqlite_session, postgres_session, model, table_name):
    """Migrate data from SQLite to PostgreSQL for a given model."""
    logger.info(f"Migrating table: {table_name}")
    try:
        # Fetch all records from SQLite
        records = sqlite_session.query(model).all()
        logger.info(f"Found {len(records)} records in {table_name}")

        # Insert records into PostgreSQL
        for record in records:
            # Create a new instance of the model with the same data
            data = {c.name: getattr(record, c.name) for c in record.__table__.columns}
            postgres_session.merge(model(**data))  # Use merge to handle existing records

        postgres_session.commit()
        logger.info(f"Successfully migrated {table_name}")
    except Exception as e:
        logger.error(f"Error migrating {table_name}: {e}")
        postgres_session.rollback()
        raise

def main():
    # Create sessions for both databases
    sqlite_session = create_sqlite_session()
    postgres_session = create_postgres_session()

    try:
        # Migrate each table
        migrate_table(sqlite_session, postgres_session, Estoque, 'estoque')
        migrate_table(sqlite_session, postgres_session, BarraEndereco, 'barra_endereco')
        migrate_table(sqlite_session, postgres_session, InventariosRealizados, 'inventarios_realizados')
        migrate_table(sqlite_session, postgres_session, UserCredential, 'user_credential')

        logger.info("Data migration completed successfully!")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
    finally:
        # Close sessions
        sqlite_session.remove()
        postgres_session.remove()

if __name__ == '__main__':
    main()