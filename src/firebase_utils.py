import os
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase only once
if not firebase_admin._apps:
    cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- USER UTILITIES ---
def get_user(user_id):
    doc = db.collection("users").document(user_id).get()
    return doc.to_dict() if doc.exists else None

def create_or_update_user(user_id, data):
    db.collection("users").document(user_id).set(data, merge=True)

def ensure_user_exists(user_id, name):
    if not get_user(user_id):
        create_or_update_user(user_id, {
            "id": user_id,
            "name": name,
            "role": None,
            "interests": [],
            "channels": [],
            "followed_users": [],
            "muted": False,
            "digest_config": {
                "frequency": "daily",
                "types": ["commits", "prs", "tasks", "blockers", "kudos"]
            },
            "last_digest_sent": None
        })

def mute_user(user_id):
    db.collection("users").document(user_id).update({"muted": True})

def unmute_user(user_id):
    db.collection("users").document(user_id).update({"muted": False})

def update_user_digest_config(user_id, config):
    db.collection("users").document(user_id).update({"digest_config": config})

# --- DIGEST UTILITIES ---
def add_team_digest(summary, highlights, blockers, kudos, trends, frequency="daily"):
    db.collection("digests").add({
        "type": "team",
        "date": firestore.SERVER_TIMESTAMP,
        "frequency": frequency,
        "summary": summary,
        "highlights": highlights,
        "blockers": blockers,
        "kudos": kudos,
        "trends": trends
    })

def get_latest_team_digest():
    docs = db.collection("digests").where("type", "==", "team").order_by("date", direction=firestore.Query.DESCENDING).limit(1).stream()
    for doc in docs:
        return doc.to_dict()
    return None

# --- BLOCKERS UTILITIES ---
def add_blocker(title, description, reported_by, tags):
    db.collection("blockers").add({
        "title": title,
        "description": description,
        "reported_by": reported_by,
        "created_at": firestore.SERVER_TIMESTAMP,
        "status": "open",
        "tags": tags,
        "resolved_at": None,
        "resolved_by": None
    })

def get_open_blockers():
    return [doc.to_dict() for doc in db.collection("blockers").where("status", "==", "open").stream()]

def resolve_blocker(blocker_id, resolved_by):
    db.collection("blockers").document(blocker_id).update({
        "status": "resolved",
        "resolved_at": firestore.SERVER_TIMESTAMP,
        "resolved_by": resolved_by
    })

# --- KUDOS UTILITIES ---
def add_kudos(from_user, to_user, message, gpt_generated=False):
    db.collection("kudos").add({
        "from": from_user,
        "to": to_user,
        "message": message,
        "created_at": firestore.SERVER_TIMESTAMP,
        "gpt_generated": gpt_generated
    })

def get_recent_kudos(limit=10):
    return [doc.to_dict() for doc in db.collection("kudos").order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit).stream()]

# --- TRENDS UTILITIES ---
def add_trend(date, active_threads, top_prs, issue_swarms, summary):
    db.collection("trends").add({
        "date": date,
        "active_threads": active_threads,
        "top_prs": top_prs,
        "issue_swarms": issue_swarms,
        "summary": summary
    })

def get_latest_trends():
    docs = db.collection("trends").order_by("date", direction=firestore.Query.DESCENDING).limit(1).stream()
    for doc in docs:
        return doc.to_dict()
    return None

# --- CONFIG UTILITIES (OPTIONAL) ---
def set_global_config(config):
    db.collection("config").document("global").set(config, merge=True)

def get_global_config():
    doc = db.collection("config").document("global").get()
    return doc.to_dict() if doc.exists else None

# --- MESSAGES UTILITIES (OPTIONAL) ---
def store_message(message_data):
    db.collection("messages").add(message_data)

def get_user_messages(user_id, limit=20):
    return [doc.to_dict() for doc in db.collection("messages").where("user_id", "==", user_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()] 