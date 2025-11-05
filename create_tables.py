# create_tables.py
from app.database import engine, Base

# Import every model module so Base.metadata includes them
import app.models.blood_request
import app.models.blood_donor
import app.models.healthcare_provider
import app.models.healthcare_request
import app.models.outbreak
import app.models.symptom_report
import app.models.transport_offer
import app.models.transport_request
import app.models.vaccination

# Now create all tables in the database
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created!")
