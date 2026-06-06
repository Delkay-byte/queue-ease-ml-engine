# I am importing our core mathematical and data structuring tools
import os
import pandas as pd
import numpy as np
import math
import pickle
import warnings
from datetime import datetime, timedelta

# I am importing SQLAlchemy assets to manage structured relational operations safely
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

# I am importing the Prophet forecasting algorithm to handle my time-series analysis
from prophet import Prophet

# I am ignoring all non-critical warnings to keep my production console output clean and concise
warnings.filterwarnings('ignore')

# I am dynamically capturing the exact folder path where this specific script lives for safe absolute paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# I am fetching credentials from the environment, defaulting to local values only if needed
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "queueease_db")

# I am establishing the secure connection engine URL for PostgreSQL
CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
db_engine = create_engine(CONNECTION_STRING)


def initialize_database():
    # I am creating the table explicitly with a composite primary key so both facility types can share the same hours without crashing
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS facility_traffic_logs (
        timestamp TIMESTAMP,
        hourly_queue_count INTEGER,
        is_override BOOLEAN,
        facility_type VARCHAR(50),
        was_disrupted_by_rain BOOLEAN
        PRIMARY KEY (timestamp, facility_type)
    );
    """
    with db_engine.connect() as connection:
        connection.execute(text(create_table_sql))
        connection.commit()  # I am ensuring the structural schema change is physically committed to the DB
    print("Database schema verified.")


def generate_nigerian_queue_data(days_to_simulate=60, facility_type="Standard_9to5"):
    # I am setting our baseline date matrix starting 60 days in the past
    start_date = datetime.now() - timedelta(days=days_to_simulate)
    # I am initializing an empty list to collect individual hourly rows before structured compilation
    data_records = []
    
    # I am looping through every single day in my simulation window, one day at a time
    for day_offset in range(days_to_simulate):
        # I am calculating the exact calendar date for the current loop step
        current_date = start_date + timedelta(days=day_offset)
        # I am extracting the day of the week index, where 0 represents Monday, and 6 represents Sunday
        day_of_week = current_date.weekday()
        
        # I am updating the calendar definitions to October 1st (National Day) and June 12th to match Nigeria's official Democracy Day specification
        is_holiday = (current_date.month == 10 and current_date.day == 1) or \
                     (current_date.month == 6 and current_date.day == 12)
        
        # I am looping through all 24 hours of the day to ensure a complete, continuous timeline for time-series tracking
        for hour in range(0, 24):
            # I am checking if the facility is a standard 9-5 office and is currently closed due to weekends, holidays, or off-hours
            is_office_closed = (facility_type == "Standard_9to5") and \
                               (day_of_week >= 5 or is_holiday or hour < 8 or hour >= 16)
                               
            if is_office_closed:
                # I am forcing closed windows to be explicit zeroes so the operational boundary remains clear and crisp
                base_traffic = 0
                is_override = False
                is_heavy_rain_day = False
            else:
                # I am establishing an organic baseline number of people arriving per hour when the facility is open
                base_traffic = np.random.randint(5, 15)
                # I am determining if we fall into the peak rainy season months of May, June, or July
                is_rainy_season_peak = current_date.month in [5, 6, 7]
                # I am calculating a 30% random probability of a heavy tropical downpour occurring during rainy season days
                is_heavy_rain_day = is_rainy_season_peak and (np.random.random() < 0.30)
                
                # I am adding a high-volume Monday morning rush surge pattern for corporate office environments
                if facility_type == "Standard_9to5" and day_of_week == 0 and hour in [8, 9, 10]:
                    base_traffic += np.random.randint(20, 40)
                    
                # I am tapering traffic down on Friday afternoons due to early weekend travel and community prayers
                if day_of_week == 4 and hour >= 13:
                    base_traffic = max(0, base_traffic - np.random.randint(5, 10))
                    
                # I am injecting weekend-evening emergency surge spikes specifically for the 24/7 hospital environment
                if facility_type == "Continuous_24_7" and day_of_week in [4, 5, 6] and hour in [18, 19, 20]:
                    base_traffic += np.random.randint(10, 25)

                # I am modifying crowd arrival behaviors based on severe weather disruptions
                if is_heavy_rain_day:
                    if facility_type == "Standard_9to5":
                        # Rain drops administrative traffic by 60% to 80% as citizens stay indoors or experience transit delays
                        reduction_factor = np.random.uniform(0.60, 0.80)
                        base_traffic = max(1, int(base_traffic * (1 - reduction_factor)))
                    elif facility_type == "Continuous_24_7":
                        # Emergency medical units stay highly active but experience a minor 15% transport lag drop
                        base_traffic = max(2, int(base_traffic * 0.85))
                        
                # I am setting base probabilities for sudden triage overrides (15% for hospitals, 2% for standard offices)
                override_chance = 0.15 if facility_type == "Continuous_24_7" else 0.02
                # I am doubling the hospital override risk to 30% if a heavy rainstorm causes road accidents
                if is_heavy_rain_day and facility_type == "Continuous_24_7":
                    override_chance = 0.30
                    
                # I am executing a random roll to determine if a triage override event triggers during this hour
                is_override = np.random.random() < override_chance

            # I am capturing and constructing the exact timestamp configuration for this specific loop iteration
            timestamp = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            # I am packing our structured observation records into the main collector array
            data_records.append({
                'timestamp': timestamp,
                'hourly_queue_count': base_traffic,
                'is_override': is_override,
                'facility_type': facility_type,
                'was_disrupted_by_rain': is_heavy_rain_day 
            })

    # I am converting our logged records into a standard, structured pandas data frame
    df = pd.DataFrame(data_records)
    
    # I am pushing this dataframe directly into our Postgres database while catching key duplicate constraints gracefully
    try:
        df.to_sql('facility_traffic_logs', db_engine, if_exists='append', index=False)
        print(f"Successfully seeded database with 60 days of {facility_type} traffic data.")
    except IntegrityError:
        # I am absorbing duplicate key conflicts silently so re-running the script doesn't stop the execution pipeline
        print(f"Database notes: Records for {facility_type} already exist. Moving safely to training.")
    except Exception as e:
        print(f"Database write failed. Error: {e}")
        
    return df


def generate_and_save_queue_forecast(facility_type="Standard_9to5"):
    # I am crafting a SQL query to pull only the specific facility data we need directly from Postgres
    sql_query = f"""
        SELECT timestamp, hourly_queue_count, is_override, facility_type, was_disrupted_by_rain 
        FROM facility_traffic_logs
        WHERE facility_type = '{facility_type}';
    """
    
    # I am reading the data stream directly from the database into our pandas dataframe
    try:
        raw_data = pd.read_sql(sql_query, db_engine)
    except Exception as e:
        print(f"Database read failed. Cannot train model without data. Error: {e}")
        return None
        
    # I am sorting and deduplicating timestamps to protect the Prophet model from crashing if records exist in duplicate
    raw_data = raw_data.sort_values('timestamp')
    raw_data = raw_data.drop_duplicates(subset=['timestamp'], keep='last').copy()
    
    # I am separating anomalous operational periods where explicit manual overrides altered the natural baseline flow
    if 'is_override' in raw_data.columns:
        clean_data = raw_data[raw_data['is_override'] == False].copy()
    else:
        clean_data = raw_data.copy()

    # For standard 9-5 facilities, we remove the night/weekend zeros completely from the training set
    if facility_type == "Standard_9to5":
        # I am converting the timestamp text field into active datetimes to extract operational components
        clean_data['timestamp_dt'] = pd.to_datetime(clean_data['timestamp'])
        # I am extracting the exact hour of the day from our transactional timestamps
        clean_data['hour'] = clean_data['timestamp_dt'].dt.hour
        # I am extracting the specific day of the week index to separate weekdays from weekend blocks
        clean_data['dayofweek'] = clean_data['timestamp_dt'].dt.dayofweek
        
        # We only feed the model rows where the office was actually open to prevent zero-anchor drag anomalies
        clean_data = clean_data[(clean_data['dayofweek'] < 5) & (clean_data['hour'] >= 8) & (clean_data['hour'] < 16)]

    # I am building a brand new dataframe structured specifically to meet the entry requirements of the Prophet model
    df_ready = pd.DataFrame()
    df_ready['ds'] = pd.to_datetime(clean_data['timestamp'])
    df_ready['y'] = clean_data['hourly_queue_count']
    
    # I am blanking out rain disruption days so Prophet skips over the extreme noise spikes smoothly
    if 'was_disrupted_by_rain' in clean_data.columns:
        # I am extracting array values explicitly to protect this statement from index positioning shifts
        df_ready.loc[clean_data['was_disrupted_by_rain'].values == True, 'y'] = None
        
    # I am configuring our time-series forecasting model with active daily and weekly cyclical profiles enabled
    my_prophet_model = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)
    
    # I am overlaying local regional statutory holidays for standard business entities using the Nigerian 'NG' identifier
    if facility_type == "Standard_9to5":
        my_prophet_model.add_country_holidays(country_name='NG') 
    
    # I am training our mathematical model parameters against our prepared and filtered data history
    my_prophet_model.fit(df_ready)
    
    # I am creating our dynamic filename string before mapping its absolute output route
    model_filename = f"queueease_model_{facility_type}.pkl"
    
    # I am merging our script directory with the filename to construct an absolute filesystem path
    absolute_save_path = os.path.join(BASE_DIR, model_filename)
    
    # I am saving the active mathematical weights directly to our hard drive using our verified path configuration
    with open(absolute_save_path, 'wb') as file_handle:
        pickle.dump(my_prophet_model, file_handle)
    
    # I am logging a confirmation message to verify successful model compilation and storage
    print(f"Success! Saved trained model architecture to: {model_filename}")
    
    # I am generating a future projection timeline stretching out for the next 24 consecutive hours
    future_time_slots = my_prophet_model.make_future_dataframe(periods=24, freq='H')
    forecast = my_prophet_model.predict(future_time_slots)
    
    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]


def test_saved_models(test_datetime_string):
    # I am parsing our testing timestamp text parameter into an active pandas datetime entity
    parsed_time = pd.to_datetime(test_datetime_string)
    test_time = pd.DataFrame({'ds': [parsed_time]})
    
    # I am extracting calendar attributes for our Business Logic Mask
    day_of_week = parsed_time.weekday()
    hour = parsed_time.hour
    
    # I am synchronizing our programmatic validation rule checks with October 1st and June 12th national calendars
    is_holiday = (parsed_time.month == 10 and parsed_time.day == 1) or \
                 (parsed_time.month == 6 and parsed_time.day == 12)
                 
    # I am defining our strict structural schedule rule boundary for standard facilities
    is_office_physically_closed = (day_of_week >= 5 or is_holiday or hour < 8 or hour >= 16)

    print(f"--- STARTING INFERENCE TEST FOR: {test_datetime_string} ---")
    
    # Testing our Standard 9-5 Corporate Model File
    try:
        if is_office_physically_closed:
            final_weekday_value = 0
        else:
            model_path = os.path.join(BASE_DIR, "queueease_model_Standard_9to5.pkl")
            
            with open(model_path, "rb") as file:
                weekday_model = pickle.load(file)
            weekday_prediction = weekday_model.predict(test_time)
            final_weekday_value = max(0, int(round(weekday_prediction['yhat'].values[0])))
            
        print(f"[9-5 Corporate] Predicted crowd: {final_weekday_value} people in line.")
    except FileNotFoundError:
        print("[9-5 Corporate] Error: File missing.")

    # Testing our Continuous 24/7 Hospital Model File
    try:
        model_path = os.path.join(BASE_DIR, "queueease_model_Continuous_24_7.pkl")
        
        with open(model_path, "rb") as file:
            hospital_model = pickle.load(file)
        hospital_prediction = hospital_model.predict(test_time)
        final_hospital_value = max(0, int(round(hospital_prediction['yhat'].values[0])))
        print(f"[24/7 Hospital] Predicted crowd: {final_hospital_value} people in line.")
    except FileNotFoundError:
        print("[24/7 Hospital] Error: File missing.")
    print("-" * 40 + "\n")


# -----------------------------------------------------------------
# EXECUTION BLOCK (Safeguarded for Production Imports)
# -----------------------------------------------------------------
if __name__ == "__main__":
    print("--- Initializing QueueEase Production Pipeline ---")
    
    # NEW FIX: I am enforcing the database setup function to guarantee that tables exist with PRIMARY KEY attributes
    initialize_database()
    
    # 1. I am generating and pushing the synthetic data directly into PostgreSQL
    office_data = generate_nigerian_queue_data(days_to_simulate=60, facility_type="Standard_9to5")
    hospital_data = generate_nigerian_queue_data(days_to_simulate=60, facility_type="Continuous_24_7")

    # 2. I am executing database extractions, parameter fittings, and saving our weights
    office_results = generate_and_save_queue_forecast(facility_type="Standard_9to5")
    hospital_results = generate_and_save_queue_forecast(facility_type="Continuous_24_7")

    # 3. I am processing our validation checks across our target boundary scenarios
    test_saved_models('2026-06-28 14:00:00')  # FIXED: Expected Sunday Afternoon Test (Checks weekend closures)
    test_saved_models('2026-06-08 09:00:00')  # Expected Monday Morning Test (Checks corporate rush windows)
    test_saved_models('2026-06-12 10:00:00')  # Expected Democracy Day Test (Checks Nigerian holiday masks)