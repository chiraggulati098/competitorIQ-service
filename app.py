from flask import Flask, request, jsonify
from flask_cors import CORS
from utils.clerk_auth import authenticate_and_get_user_details
from routes.competitor import competitor_bp

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

if __name__ == "__main__":
    app.run(debug=True, port=8000)