import json
import psycopg2
from datetime import datetime, timezone
from app.config import settings  # import your Pydantic settings


def get_conn():
    """
    Connect to Neon PostgreSQL using settings from app/config.py
    """
    return psycopg2.connect(
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASS,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        sslmode="require"  # Neon requires SSL (just like Cloud SQL)
    )


def import_blood_donors(json_path: str):
    """Import blood donors from JSON into Neon PostgreSQL."""
    with open(json_path, "r", encoding="utf-8") as f:
        donors = json.load(f)

    conn = get_conn()
    cur = conn.cursor()
    inserted = 0

    for donor in donors:
        id_ = donor.get("id")
        full_name = donor.get("full_name")
        blood_type = donor.get("blood_type")
        phone = donor.get("phone")
        city = donor.get("city")
        is_active = donor.get("is_active", True)
        latitude = donor.get("latitude")
        longitude = donor.get("longitude")
        fcm_token = donor.get("fcm_token") or donor.get("fcmToken")

        try:
            cur.execute("""
                INSERT INTO blood_donors (
                    id, full_name, blood_type, phone, city, is_active, latitude, longitude, fcm_token
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                  full_name = EXCLUDED.full_name,
                  blood_type = EXCLUDED.blood_type,
                  phone = EXCLUDED.phone,
                  city = EXCLUDED.city,
                  is_active = EXCLUDED.is_active,
                  latitude = EXCLUDED.latitude,
                  longitude = EXCLUDED.longitude,
                  fcm_token = EXCLUDED.fcm_token
            """, (id_, full_name, blood_type, phone, city, is_active, latitude, longitude, fcm_token))
            inserted += 1
        except Exception as e:
            print(f"[ERROR] donor {id_}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Imported/updated {inserted} blood_donors records.")


def import_blood_requesters(json_path: str):
    """Import blood requesters from JSON into Neon PostgreSQL."""
    with open(json_path, "r", encoding="utf-8") as f:
        reqs = json.load(f)

    conn = get_conn()
    cur = conn.cursor()
    inserted = 0

    for req in reqs:
        id_ = req.get("id")
        blood_type = req.get("blood_type") or req.get("bloodGroup")
        hospital_name = req.get("hospitalName") or req.get("hospital_name")
        hospital_lat = req.get("hospitalLat")
        hospital_lng = req.get("hospitalLng")
        phone = req.get("phone")

        ts = req.get("timestamp")
        ts_value = None
        if isinstance(ts, dict) and "seconds" in ts:
            ts_value = datetime.fromtimestamp(ts["seconds"], tz=timezone.utc).isoformat()
        elif isinstance(ts, str):
            ts_value = ts

        try:
            if ts_value:
                cur.execute("""
                    INSERT INTO blood_requesters (
                        id, blood_type, hospital_name, hospital_lat, hospital_lng, phone, timestamp
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      blood_type = EXCLUDED.blood_type,
                      hospital_name = EXCLUDED.hospital_name,
                      hospital_lat = EXCLUDED.hospital_lat,
                      hospital_lng = EXCLUDED.hospital_lng,
                      phone = EXCLUDED.phone,
                      timestamp = EXCLUDED.timestamp
                """, (id_, blood_type, hospital_name, hospital_lat, hospital_lng, phone, ts_value))
            else:
                cur.execute("""
                    INSERT INTO blood_requesters (
                        id, blood_type, hospital_name, hospital_lat, hospital_lng, phone
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      blood_type = EXCLUDED.blood_type,
                      hospital_name = EXCLUDED.hospital_name,
                      hospital_lat = EXCLUDED.hospital_lat,
                      hospital_lng = EXCLUDED.hospital_lng,
                      phone = EXCLUDED.phone
                """, (id_, blood_type, hospital_name, hospital_lat, hospital_lng, phone))
            inserted += 1
        except Exception as e:
            print(f"[ERROR] request {id_}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Imported/updated {inserted} blood_requesters records.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import Firestore JSON into Neon PostgreSQL")
    parser.add_argument("--donors-json", help="Path to blood_donors.json")
    parser.add_argument("--requests-json", help="Path to blood_requesters.json")
    args = parser.parse_args()

    if args.donors_json:
        import_blood_donors(args.donors_json)
    if args.requests_json:
        import_blood_requesters(args.requests_json)
