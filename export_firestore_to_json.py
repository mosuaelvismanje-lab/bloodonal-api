import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from datetime import datetime, date

def serialize_value(val):
    # Duck-type Firestore Timestamp: has to_datetime()
    if hasattr(val, "to_datetime") and callable(val.to_datetime):
        return val.to_datetime().isoformat()
    # If nested dict or list, recurse
    if isinstance(val, dict):
        return {k: serialize_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [serialize_value(v) for v in val]
    # datetime/date: convert to ISO
    if isinstance(val, datetime) or isinstance(val, date):
        return val.isoformat()
    # Other types (int, float, str, bool, None)
    return val

def export_collections(service_account_path, output_dir="exported_data"):
    # Initialize Firebase app
    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    os.makedirs(output_dir, exist_ok=True)

    for coll in db.collections():
        col_name = coll.id
        docs = coll.stream()
        data = []
        for doc in docs:
            raw = doc.to_dict()
            serialized = {}
            for k, v in raw.items():
                serialized[k] = serialize_value(v)
            serialized['id'] = doc.id
            data.append(serialized)

        file_path = os.path.join(output_dir, f"{col_name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Exported {len(data)} documents from collection '{col_name}' to {file_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export Firestore collections to JSON files")
    parser.add_argument(
        "--service-account", "-s",
        required=True,
        help="Path to Firebase serviceAccountKey.json"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="exported_data",
        help="Directory to save exported JSON files"
    )
    args = parser.parse_args()
    export_collections(args.service_account, args.output_dir)
