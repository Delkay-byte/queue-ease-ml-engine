# I am importing Flask to build the web server, and 'request' and 'jsonify' to handle incoming and outgoing data
from flask import Flask, request, jsonify
# I am importing CORS to allow the frontend website to talk to this backend server securely
from flask_cors import CORS
# I am importing pandas to structure timestamps into the dataframe format and handle date arithmetic
import pandas as pd
# I am importing pickle to unpack and load my frozen mathematical models into active memory
import pickle
# I am importing os to dynamically locate my model files regardless of where the server is hosted
import os
# I am importing datetime to parse and understand the exact time the user scanned the QR code
from datetime import datetime

# I am importing my notification engine right at the top so it is fully loaded before any user makes a request
from notification_engine import QueueNotificationEngine

# I am dynamically capturing the exact folder path where this API script lives to safely locate my models
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# I am initializing the Flask application instance to serve as my backend API listener
app = Flask(__name__)

# I am registering CORS with the app so that any frontend application can request data from this server
CORS(app)

print("--- Loading QueueEase Models into Server Memory ---")

# I am setting up empty variables to hold my models globally so they only have to load once when the server starts
office_model = None
hospital_model = None

# I am importing SQLAlchemy tools to allow my API to write live data into my PostgreSQL warehouse
from sqlalchemy import create_engine, text
import urllib.parse

# I am fetching my local database credentials from the environment
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "143@DelKay") 
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "queueease_db")

# I am safely encoding the password so special characters do not confuse the connection parser
SAFE_PASSWORD = urllib.parse.quote_plus(DB_PASSWORD)

# I am establishing the secure connection engine URL for PostgreSQL
CONNECTION_STRING = f"postgresql://{DB_USER}:{SAFE_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
db_engine = create_engine(CONNECTION_STRING)

def initialize_live_tracking_table():
    # I am updating the live tracking table to match the Master Blueprint: capturing BOTH the ML model and the Analyst's specific facility name
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS live_queue_bookings (
        booking_id SERIAL PRIMARY KEY,
        scan_timestamp TIMESTAMP,
        facility_model VARCHAR(50),
        facility_name VARCHAR(100),
        predicted_wait_time INTEGER,
        booking_source VARCHAR(50)
    );
    """
    with db_engine.connect() as connection:
        connection.execute(text(create_table_sql))
        connection.commit()
    print("Live queue bookings database table verified and synced with Master Blueprint.")

# I am calling this function right before the server starts
initialize_live_tracking_table()

# I am safely loading the Standard 9-to-5 model into server memory
try:
    office_model_path = os.path.join(BASE_DIR, "queueease_model_Standard_9to5.pkl")
    with open(office_model_path, "rb") as file:
        office_model = pickle.load(file)
    print("Standard 9-to-5 model loaded successfully.")
except FileNotFoundError:
    print("Warning: Standard 9-to-5 model file is missing.")

# I am safely loading the Continuous 24/7 hospital model into server memory
try:
    hospital_model_path = os.path.join(BASE_DIR, "queueease_model_Continuous_24_7.pkl")
    with open(hospital_model_path, "rb") as file:
        hospital_model = pickle.load(file)
    print("Continuous 24/7 model loaded successfully.")
except FileNotFoundError:
    print("Warning: Continuous 24/7 model file is missing.")


@app.route('/predict_queue', methods=['POST'])
def predict_queue():
    # I am extracting the raw JSON package sent by the frontend
    data = request.get_json()

    # I am acting as the bouncer: checking for the new Master Blueprint keys
    if not data or 'timestamp' not in data or 'facility_model' not in data:
        return jsonify({
            "status": "error", 
            "message": "Missing required fields. Please ensure 'timestamp' and 'facility_model' are provided."
        }), 400

    # I am safely extracting the parameters
    target_time_str = data['timestamp']
    facility_model = data['facility_model']
    # I am fetching the specific business name for the analysts, defaulting to generic if missing
    facility_name = data.get('facility_name', 'General Facility')
    booking_source = data.get("booking_source", "Unknown")
    citizen_phone = data.get("phone_number", "+233501234567")

    # I am using a try block to parse the user's time string into a valid pandas datetime object
    try:
        parsed_time = pd.to_datetime(target_time_str)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Invalid timestamp format: {e}"}), 400

    # I am extracting the specific hour and day of the week to run my business logic masks
    hour = parsed_time.hour
    day_of_week = parsed_time.weekday()
    
    # I am enforcing the statutory holiday mask directly on the incoming request (Nigeria context)
    is_holiday = (parsed_time.month == 10 and parsed_time.day == 1) or \
                 (parsed_time.month == 6 and parsed_time.day == 12)

    # I am creating a Prophet-friendly dataframe containing the exact time the user is asking about
    test_time_df = pd.DataFrame({'ds': [parsed_time]})
    predicted_crowd = 0

    # I am branching the logic to handle standard corporate environments
    if facility_model == "Standard_9to5":
        is_office_physically_closed = (day_of_week >= 5 or is_holiday or hour < 8 or hour >= 16)
        
        if is_office_physically_closed:
            predicted_crowd = 0
        else:
            if office_model is None:
                return jsonify({"status": "error", "message": "Office model is not available"}), 500
            
            prediction = office_model.predict(test_time_df)
            predicted_crowd = max(0, int(round(prediction['yhat'].values[0])))

    # I am branching the logic to handle continuous environments
    elif facility_model == "Continuous_24_7":
        if hospital_model is None:
            return jsonify({"status": "error", "message": "Continuous 24/7 model is not available"}), 500
        
        prediction = hospital_model.predict(test_time_df)
        predicted_crowd = max(0, int(round(prediction['yhat'].values[0])))
        
    else:
        return jsonify({"status": "error", "message": f"Unknown facility model: {facility_model}"}), 400

    # I am mathematically estimating the wait time by assuming each person takes an average of 4 minutes to process
    estimated_wait_minutes = predicted_crowd * 4

    # I am isolating the whole hours and minutes for a premium user experience
    calculated_hours = estimated_wait_minutes // 60
    calculated_minutes = estimated_wait_minutes % 60

    # I am building the human-readable string structure
    if calculated_hours == 0:
        readable_wait = f"{calculated_minutes} minutes"
    elif calculated_minutes == 0:
        readable_wait = f"{calculated_hours} hour{'s' if calculated_hours > 1 else ''}"
    else:
        readable_wait = f"{calculated_hours} hour{'s' if calculated_hours > 1 else ''} and {calculated_minutes} minutes"

    # I am computing the exact clock arrival target
    expected_service_time = parsed_time + pd.Timedelta(minutes=estimated_wait_minutes)
    formatted_service_time = expected_service_time.strftime("%I:%M %p")

    # I am initializing a placeholder variable to safely capture my ticket primary key
    ticket_num = None

    # --- DATABASE LOGIC ---
    try:
        # I am securely opening a connection to the PostgreSQL database
        with db_engine.connect() as connection:
            # I am updating the SQL to capture both the ML model type and the specific facility name
            log_query = text("""
                INSERT INTO live_queue_bookings (scan_timestamp, facility_model, facility_name, predicted_wait_time, booking_source)
                VALUES (:ts, :fmod, :fname, :pwt, :src)
                RETURNING booking_id
            """)
            
            result = connection.execute(log_query, {
                "ts": target_time_str, 
                "fmod": facility_model,
                "fname": facility_name,
                "pwt": estimated_wait_minutes, 
                "src": booking_source
            })
            
            # I am reading the newly generated primary key value from the database return cursor
            ticket_num = result.fetchone()[0]
            # I am saving my transaction permanently
            connection.commit()
            
    except Exception as e:
        # I am logging the raw technical error to my own terminal
        print(f"CRITICAL DATABASE ERROR: {e}")
        return jsonify({
            "status": "error", 
            "message": "Internal server error while saving the booking. Please try again later."
        }), 500
        
    # --- AUTOMATED WHATSAPP NOTIFICATION PIPELINE ---
    if ticket_num is not None:
        try:
            print(f"--- Dispatching Live WhatsApp Alert to Ticket #{ticket_num} ---")
            # I am firing the notification engine BEFORE the return statement so it actually executes!
            notifier = QueueNotificationEngine(provider="twilio")
            notifier.send_whatsapp_alert(
                recipient_phone=citizen_phone, 
                ticket_number=ticket_num, 
                wait_time=estimated_wait_minutes
            )
        except Exception as msg_error:
            # I am logging communication drops softly so the UI still loads for the user
            print(f"WARNING: Database saved successfully, but notification dispatch failed: {msg_error}")

    # I am generating the premium formatted response ticket to send back to the user's interface
    # This return statement is the absolute final line of the function.
    return jsonify({
        "status": "success",
        "ticket_number": ticket_num,
        "requested_time": target_time_str,
        "facility_model": facility_model,
        "facility_name": facility_name,
        "booking_source": booking_source,
        "predicted_people_in_line": predicted_crowd,
        "estimated_wait_raw_minutes": estimated_wait_minutes,
        "readable_wait_time": readable_wait,
        "expected_service_time": formatted_service_time
    }), 200

@app.route('/live_queue', methods=['GET'])
def get_live_queue():
    try:
        # I am securely opening a connection to the PostgreSQL database
        with db_engine.connect() as connection:
            # I am updating the select query to pull the specific facility_name for the Officer Dashboard
            query = text("""
                SELECT booking_id, scan_timestamp, facility_name, predicted_wait_time, booking_source 
                FROM live_queue_bookings 
                ORDER BY scan_timestamp DESC 
                LIMIT 50
            """)
            result = connection.execute(query)
            
            # I am formatting the raw SQL rows into a clean list of dictionaries
            queue_data = []
            for row in result:
                queue_data.append({
                    "ticket_number": row.booking_id,
                    "joined_at": row.scan_timestamp.strftime("%I:%M %p"),
                    "facility": row.facility_name,
                    "wait_time_mins": row.predicted_wait_time,
                    "source": row.booking_source
                })
            
            # I am sending the compiled payload back to the frontend
            return jsonify({
                "status": "success",
                "total_waiting": len(queue_data),
                "queue": queue_data
            }), 200

    except Exception as e:
        # I am catching and logging database read errors
        print(f"CRITICAL DATABASE ERROR ON GET ROUTE: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve live queue data."
        }), 500
        
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)