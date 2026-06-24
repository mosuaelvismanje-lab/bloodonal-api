# create_tables.py
from app.db.database import engine, Base

# Import every model module so Base.metadata includes them

# Now create all tables in the database
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created!")
