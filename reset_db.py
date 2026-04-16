import logging
import sys
import os

# Add the current directory to sys.path so we can import 'app'
sys.path.append(os.getcwd())

from app.database import sync_engine, Base

# Set up basic logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reset_db")


def reset_database():
    """
    Drops all existing tables and recreates them fresh.
    """
    # ⚠️ CRITICAL: We MUST import all models here.
    # Base.metadata is a registry. If a model file is never
    # imported, the registry is empty and drop_all() does nothing.
    try:
        print("🔍 Registering models...")
        # Add every model file you have here
        from app.models.user import User
        from app.models.payment import Payment
        from app.models.wallet import Wallet
        from app.models.usage_counter import UsageCounter
        from app.models.service_listing import ServiceListing
        from app.models.blood_request import BloodRequest
        from app.models.blood_donor import BloodDonor
        from app.models.healthcare_provider import HealthcareProvider
        from app.models.transport_request import TransportRequest

        # Add any missing specific models found in your git status
        from app.models.BikeRequest import BikeRequest
        from app.models.servicemodel import ServiceRequest

    except ImportError as e:
        logger.warning(f"Note: Some models could not be imported: {e}")

    print("🧨 Dropping all tables...")
    try:
        # Use the sync_engine specifically for this administrative task
        Base.metadata.drop_all(bind=sync_engine)
        print("✅ All tables dropped successfully.")

        print("🏗️ Recreating tables...")
        Base.metadata.create_all(bind=sync_engine)
        print("✨ Database reset complete. Tables are empty and ready.")

    except Exception as e:
        print(f"❌ Error during database reset: {e}")


if __name__ == "__main__":
    confirm = input("This will DELETE ALL DATA in the database. Are you sure? (y/n): ")
    if confirm.lower() == 'y':
        reset_database()
    else:
        print("Reset aborted.")