# =========================================================
# RESET DATABASE (ENTERPRISE SAFE VERSION)
# =========================================================

import logging
import sys
import os
import traceback
import pkgutil
import importlib

sys.path.append(os.getcwd())

from app.db.database import sync_engine, Base
import app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reset_db")


# =========================================================
# AUTO MODEL REGISTRATION
# =========================================================
def auto_register_models():
    """
    Dynamically imports all SQLAlchemy model modules.
    Ensures Base.metadata is fully populated before create_all().
    """

    print("\n🔍 Auto-discovering models...")

    imported = []

    for _, module_name, _ in pkgutil.walk_packages(
        app.__path__,
        app.__name__ + ".",
    ):
        try:
            # =================================================
            # IMPORT FILTER STRATEGY
            # =================================================
            if (
                module_name.endswith(".models")
                or ".models." in module_name
                or module_name.endswith(".model")
                or module_name.endswith("user_profile")
                or module_name.endswith("service_listing")
                or module_name.endswith("usage_counter")
            ):
                importlib.import_module(module_name)
                imported.append(module_name)

        except Exception as exc:
            print(f"⚠️ Failed to import: {module_name}")
            print(f"   {exc}")

    print(f"\n✅ Imported {len(imported)} model modules")

    for name in sorted(imported):
        print(f"   • {name}")


# =========================================================
# ENUM SAFETY HOOK (CRITICAL FIX FOR YOUR ERROR)
# =========================================================
def ensure_enums_exist():
    """
    Pre-creates PostgreSQL enum types BEFORE table creation.

    This prevents:
    - device_status_enum does not exist
    - enum type missing errors
    """

    print("\n🔧 Ensuring PostgreSQL enum types exist...")

    from sqlalchemy.dialects import postgresql
    from app.core.constants.statuses import DeviceStatus

    # DEVICE STATUS ENUM
    postgresql.ENUM(
        *[e.value for e in DeviceStatus],
        name="device_status_enum",
        create_type=True,
    ).create(sync_engine, checkfirst=True)

    print("   ✔ device_status_enum ready")


# =========================================================
# TABLE DEBUG OUTPUT
# =========================================================
def show_registered_tables():
    print("\n📋 Registered Tables")
    print("=" * 60)

    if not Base.metadata.tables:
        print("❌ No tables registered")
        return

    for table_name in sorted(Base.metadata.tables.keys()):
        print(f"✅ {table_name}")

    print("=" * 60)
    print(f"Total Tables: {len(Base.metadata.tables)}")


# =========================================================
# MAIN RESET LOGIC
# =========================================================
def reset_database():
    try:
        # STEP 1: IMPORT ALL MODELS
        auto_register_models()

        # STEP 2: SHOW TABLES BEFORE DROP
        show_registered_tables()

        # STEP 3: DROP TABLES
        print("\n🧨 Dropping all tables...")
        Base.metadata.drop_all(bind=sync_engine)
        Base.metadata.clear()
        print("✅ Drop complete")

        # STEP 4: ENSURE ENUMS EXIST (CRITICAL FIX)
        ensure_enums_exist()

        # STEP 5: CREATE TABLES
        print("\n🏗️ Creating all tables...")
        Base.metadata.create_all(bind=sync_engine)
        print("✅ Create complete")

        print("\n✨ Database reset complete")

    except Exception as exc:
        print("\n❌ DATABASE RESET FAILED")
        print(f"\nError: {exc}")
        traceback.print_exc()


# =========================================================
# ENTRY POINT
# =========================================================
if __name__ == "__main__":
    print(f"\nDB: {sync_engine.url}")

    confirm = input("\n⚠️ This will DELETE ALL DATA. Continue? (y/n): ")

    if confirm.lower() == "y":
        reset_database()
    else:
        print("Aborted")