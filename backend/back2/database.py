from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define the SQLite database URL. 
# This will create a file named 'user_data.db' in the same directory.
DATABASE_URL = "sqlite:///./user_data.db"

# Create the SQLAlchemy engine
engine = create_engine(
    DATABASE_URL, 
    # required for SQLite
    connect_args={"check_same_thread": False} 
)

# Create a SessionLocal class, which will be our actual database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for our models to inherit from
Base = declarative_base()

def get_db():
    """
    FastAPI dependency to get a database session.
    Yields a session and closes it after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_and_tables():
    """
    Utility function to create all tables in the database.
    Called on app startup.
    """
    Base.metadata.create_all(bind=engine)