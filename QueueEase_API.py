from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import pickle
import os
from datetime import datetime

# Capturing the root directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)

# --- HEALTH CHECK ROUTE ---
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "QueueEase API is online and healthy"}), 200

print("--- Loading QueueEase Models into Server Memory ---")

office_model = None
hospital_model = None

# UPDATED: Looking in the 'models/' subfolder
try:
    office_model_path = os.path.join(BASE_DIR, "models", "queueease_model_Standard_9to5.pkl")
    with open(office_model_path, "rb") as file:
        office_model = pickle.load(file)
    print("Standard 9-to-5 model loaded successfully.")
except FileNotFoundError:
    print("Warning: Standard 9-to-5 model file is missing in /models/")

try:
    hospital_model_path = os.path.join(BASE_DIR, "models", "queueease_model_Continuous_24_7.pkl")
    with open(hospital_model_path, "rb") as file:
        hospital_model = pickle.load(file)
    print("Continuous 24/7 model loaded successfully.")
except FileNotFoundError:
    print("Warning: Continuous 24/7 model file is missing in /models/")


@app.route('/predict_queue', methods=['POST'])
def predict_queue():
    data = request.get_json()

    if not data or 'timestamp' not in data or 'facility_model' not in data:
        return jsonify({
            "status": "error", 
            "message": "Missing required fields."
        }), 400

    target_time_str = data['timestamp']
    facility_model = data['facility_model']

    try:
        parsed_time = pd.to_datetime(target_time_str)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Invalid timestamp: {e}"}), 400

    hour = parsed_time.hour
    day_of_week = parsed_time.weekday()
    
    is_holiday = (parsed_time.month == 10 and parsed_time.day == 1) or \
                 (parsed_time.month == 6 and parsed_time.day == 12)

    test_time_df = pd.DataFrame({'ds': [parsed_time]})
    predicted_crowd = 0

    if facility_model == "Standard_9to5":
        is_office_physically_closed = (day_of_week >= 5 or is_holiday or hour < 8 or hour >= 16)
        if is_office_physically_closed:
            predicted_crowd = 0
        else:
            if office_model is None:
                return jsonify({"status": "error", "message": "Office model is not available"}), 500
            prediction = office_model.predict(test_time_df)
            predicted_crowd = max(0, int(round(prediction['yhat'].values[0])))

    elif facility_model == "Continuous_24_7":
        if hospital_model is None:
            return jsonify({"status": "error", "message": "Continuous 24/7 model is not available"}), 500
        prediction = hospital_model.predict(test_time_df)
        predicted_crowd = max(0, int(round(prediction['yhat'].values[0])))
        
    else:
        return jsonify({"status": "error", "message": f"Unknown model: {facility_model}"}), 400

    estimated_wait_minutes = predicted_crowd * 4

    return jsonify({
        "status": "success",
        "predicted_people_in_line": predicted_crowd,
        "estimated_wait_raw_minutes": estimated_wait_minutes
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)