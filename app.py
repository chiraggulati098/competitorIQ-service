from flask import Flask, request, jsonify
from flask_cors import CORS
from utils.clerk_auth import authenticate_and_get_user_details
from routes.competitor import competitor_bp
from pymongo import MongoClient
import os
import dotenv

dotenv.load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "competitorIQ"
USER_PREFS_COLLECTION = "user_preferences"

def get_mongo_client():
    return MongoClient(MONGO_URI)

app = Flask(__name__)
CORS(app, origins=["http://localhost:8080"], supports_credentials=True)

# Register competitor routes
app.register_blueprint(competitor_bp)

@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.status_code = 204
        return response
    try:
        user_details = authenticate_and_get_user_details(request)
        return jsonify({"success": True, "user": user_details}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 401

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/api/user/preferences', methods=['GET', 'POST'])
def user_preferences():
    client = get_mongo_client()
    db = client[DB_NAME]
    collection = db[USER_PREFS_COLLECTION]
    if request.method == 'GET':
        user_id = request.args.get('userId')
        if not user_id:
            client.close()
            return jsonify({'error': 'Missing userId parameter'}), 400
        doc = collection.find_one({'userId': user_id})
        client.close()
        if doc:
            prefs = doc.get('preferences', {})
        else:
            prefs = {'updateFreq': 'daily', 'receiveEmail': True}
        return jsonify({'preferences': prefs}), 200
    elif request.method == 'POST':
        data = request.get_json()
        user_id = data.get('userId')
        preferences = data.get('preferences')
        if not user_id or preferences is None:
            client.close()
            return jsonify({'error': 'Missing userId or preferences'}), 400
        collection.update_one(
            {'userId': user_id},
            {'$set': {'preferences': preferences}},
            upsert=True
        )
        client.close()
        return jsonify({'success': True}), 200

if __name__ == "__main__":
    app.run(port=8000)