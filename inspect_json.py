import json
import os

EXPORT_DIR = "firestore_exports"

def inspect_collection(file_name):
    path = os.path.join(EXPORT_DIR, file_name)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Collection {file_name}: {len(data)} documents")
    # Collect all keys across docs
    keys = set()
    for doc in data:
        keys.update(doc.keys())
    print("Fields:", keys)
    # Optionally show sample doc
    if data:
        print("Sample document:", data[0])
    print()

if __name__ == "__main__":
    for fname in os.listdir(EXPORT_DIR):
        if fname.endswith(".json"):
            inspect_collection(fname)
