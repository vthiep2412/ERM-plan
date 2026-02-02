from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import time

app = Flask(__name__)

# --- Configuration ---
# Load config from Environment Variables (Set these in Vercel)
# FIREBASE_CREDS_JSON: The content of serviceAccountKey.json
# REGISTRY_PASSWORD: The shared Master Password (simple string)

def get_db():
    if not firebase_admin._apps:
        # Initialize Firebase
        creds_json = os.environ.get('FIREBASE_CREDS_JSON')
        if creds_json:
            cred_dict = json.loads(creds_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
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
    """Received from Agent: Updates the tunnel URL"""
    data = request.json
    pwd = data.get('password')
    
    if pwd != os.environ.get('REGISTRY_PASSWORD'):
        return jsonify({"error": "Access Denied: Invalid Master Password"}), 403
        
    # Auth OK, update DB
    db = get_db()
    if not db: return jsonify({"error": "Database Error"}), 500
    
    doc_id = data.get('id')
    db.collection('agents').document(doc_id).set({
        'username': data.get('username'),
        'url': data.get('url'),
        'last_updated': firestore.SERVER_TIMESTAMP
    })
    
    return jsonify({"status": "updated"})

@app.route('/discover', methods=['POST'])
def discover():
    """Received from Viewer: Lists active machines"""
    data = request.json
    pwd = data.get('password')
    
    if pwd != os.environ.get('REGISTRY_PASSWORD'):
        return jsonify({"error": "Access Denied: Invalid Master Password"}), 403
        
    db = get_db()
    if not db: return jsonify({"error": "Database Error"}), 500
    
    agents_ref = db.collection('agents')
    docs = agents_ref.stream()
    
    result = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        result.append(d)
        
    return jsonify(result)

# Vercel entry point
if __name__ == '__main__':
    app.run(debug=True)
