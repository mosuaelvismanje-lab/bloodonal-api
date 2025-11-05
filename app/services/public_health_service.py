# app/services/public_health_service.py
from collections import Counter
from datetime import datetime
from app.schemas.public_summary import OutbreakSummary, SymptomStat
from app.firebase_client import db  # Firestore client

def get_symptom_stats():
    reports = db.collection("symptom_reports").stream()
    symptoms = []
    for doc in reports:
        data = doc.to_dict() or {}
        symptoms.extend(data.get("symptoms", []))
    counter = Counter(symptoms)
    return [SymptomStat(symptom=k, count=v) for k, v in counter.items()]

def get_outbreak_summaries():
    outbreaks = db.collection("outbreaks").stream()
    summaries = []
    for doc in outbreaks:
        data = doc.to_dict() or {}
        summaries.append(OutbreakSummary(
            disease_name=data.get("disease_name", "Unknown"),
            affected_count=data.get("case_count", 0),
            region=data.get("region", "N/A"),
            start_date=data.get("start_date", datetime.utcnow()),
            last_updated=data.get("last_updated", datetime.utcnow()),
            safety_measures=data.get("safety_measures", [])
        ))
    return summaries

