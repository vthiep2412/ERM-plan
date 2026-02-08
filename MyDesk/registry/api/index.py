from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import datetime
from dotenv import load_dotenv

load_dotenv() # Load .env for local development

app = Flask(__name__)
CORS(app) # Enable CORS for all routes (for now)

# Debug: Print loaded config
REGISTRY_PWD = os.environ.get('REGISTRY_PASSWORD')
if REGISTRY_PWD:
    print(f"[*] Loaded PASSWORD: {REGISTRY_PWD[:2]}...{REGISTRY_PWD[-2:]} (Length: {len(REGISTRY_PWD)})")
else:
    print("[-] WARNING: REGISTRY_PASSWORD not found in env!")

# --- Configuration ---
# Load config from Environment Variables (Set these in Vercel)
# FIREBASE_CREDS_JSON: The content of serviceAccountKey.json
# REGISTRY_PASSWORD: The shared Master Password (simple string)

def get_db():
    if not firebase_admin._apps:
        # Initialize Firebase
        creds_json = os.environ.get('FIREBASE_CREDS_JSON')
        if creds_json:
            try:
                # Debug: Check what we are trying to parse
                print(f"[*] DEBUG JSON: {creds_json[:50]}...") 
                cred_dict = json.loads(creds_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            except Exception as e:
                print(f"[-] Firebase Init Error: {e}")
                return None
        else:
            print("[-] No Firebase Credentials found in Env")
            return None
    return firestore.client()

# --- Endpoints ---

@app.route('/')
def home():
    return "MyDesk Registry Active (Secure)"

@app.route('/update', methods=['POST'])
def update_machine():
    """Received from Agent: Updates the tunnel URL (Heartbeat)"""
    data = request.json
    pwd = data.get('password')
    
    if pwd != os.environ.get('REGISTRY_PASSWORD'):
        return jsonify({"error": "Access Denied: Invalid Master Password"}), 403
        
    # Auth OK, update DB
    db = get_db()
    if not db: return jsonify({"error": "Database Error"}), 500
    
    doc_id = data.get('id')
    if not doc_id:
        return jsonify({"error": "Missing ID"}), 400

    db.collection('agents').document(doc_id).set({
        'username': data.get('username'),
        'url': data.get('url'),
        'last_updated': firestore.SERVER_TIMESTAMP
    }, merge=True)
    
    return jsonify({"status": "updated"})

@app.route('/discover', methods=['POST'])
def discover():
    """Received from Viewer: Lists active machines"""
    data = request.json
    pwd = data.get('password')
    
    # Allow empty password in dev if env var not set (optional, strictly enforcing for now)
    if pwd != os.environ.get('REGISTRY_PASSWORD'):
         return jsonify({"error": "Access Denied: Invalid Master Password"}), 403
        
    db = get_db()
    if not db: return jsonify({"error": "Database Error"}), 500
    
    agents_ref = db.collection('agents')
    docs = agents_ref.stream()
    
    result = []
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        
        # Calculate Active Status
        is_active = False
        last_updated = d.get('last_updated')
        
        if last_updated:
            # Firestore timestamp to datetime
            if hasattr(last_updated, 'year'): # It's a proper datetime object (or Firestore Timestamp wrapper)
                # Ensure UTC for comparison
                # Note: firebase-admin Python often returns localized datetime with timezone
                diff = now - last_updated
                if diff.total_seconds() < 300: # 5 minutes
                    is_active = True
        
        d['active'] = is_active
        # Serialize timestamp for JSON
        if last_updated:
            d['last_updated'] = last_updated.isoformat()
            
        result.append(d)
    
    # Sort: Active first, then by time (newest first)
    # result.sort(key=lambda x: (x.get('active', False), x.get('last_updated', '')), reverse=True)
    
    return jsonify(result)

@app.route('/delete', methods=['DELETE', 'POST'])
def delete_machine():
    """Delete an agent from registry"""
    data = request.json
    pwd = data.get('password')
    
    if pwd != os.environ.get('REGISTRY_PASSWORD'):
        return jsonify({"error": "Access Denied"}), 403
        
    db = get_db()
    doc_id = data.get('id')
    if not doc_id:
        return jsonify({"error": "Missing ID"}), 400
        
    db.collection('agents').document(doc_id).delete()
    return jsonify({"status": "deleted"})

# Vercel entry point
if __name__ == '__main__':
    app.run(debug=True)

