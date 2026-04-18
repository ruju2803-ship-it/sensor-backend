from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import csv
import os

app = Flask(__name__)
CORS(app)

CSV_FILE = 'sensor_data.csv'

# Extended parameter list
parameters = [
    {"name": "Temperature", "value": "0.0", "unit": "°C", "last_updated": None},
    {"name": "Humidity", "value": "0.0", "unit": "%", "last_updated": None},
    {"name": "CO2", "value": "000", "unit": "PPM", "last_updated": None},
    {"name": "PM 1", "value": "000", "unit": "µg/m³", "last_updated": None},
    {"name": "PM 2.5", "value": "000", "unit": "µg/m³", "last_updated": None},
    {"name": "PM 10", "value": "000", "unit": "µg/m³", "last_updated": None}
]

# Create CSV file with headers if not exists
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            "Serial No.", "Timestamp",
            "Temperature (°C)", "Humidity (%)",
            "CO2 (PPM)", "PM 1 (µg/m³)", "PM 2.5 (µg/m³)", "PM 10 (µg/m³)"
        ])

@app.route('/')
def show_parameters():
    return render_template('parameters.html', parameters=parameters)

@app.route('/update', methods=['POST'])
def update_parameters():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def update_param(index, key, valid_range=None):
            if key in data:
                try:
                    value = float(data[key])
                    if valid_range is None or (valid_range[0] <= value <= valid_range[1]):
                        parameters[index]['value'] = str(value)
                        parameters[index]['last_updated'] = timestamp
                        print(f"{parameters[index]['name']} updated: {value} at {timestamp}")
                except:
                    pass

        update_param(0, 'temperature', (-40, 80))
        update_param(1, 'humidity', (0, 100))
        update_param(2, 'co2', (0, 5000))
        update_param(3, 'pm1', (0, 1000))
        update_param(4, 'pm2_5', (0, 1000))
        update_param(5, 'pm10', (0, 1000))

        serial_no = 1
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, mode='r') as file:
                serial_no = sum(1 for row in file)

        with open(CSV_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                serial_no,
                timestamp,
                data.get('temperature', ''),
                data.get('humidity', ''),
                data.get('co2', ''),
                data.get('pm1', ''),
                data.get('pm2_5', ''),
                data.get('pm10', '')
            ])

        return jsonify({
            "status": "success",
            "parameters": parameters,
            "timestamp": timestamp
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/parameters', methods=['GET'])
def get_parameters():
    return jsonify({"parameters": parameters})

@app.route('/data', methods=['GET']) # New endpoint for historical data
def get_data(): # New function to handle historical data requests
    try:        # New query parameters: range (day/week/month/year) and date (YYYY-MM-DD)
        range_type = request.args.get('range', 'day')  # Default to 'day' if not provided
        selected_date = request.args.get('date')  # Date is required for all range types to determine the period to filter

        if not selected_date:     # Date is required to filter data, even for 'day' range type, to know which day to filter
            return jsonify({"error": "Date required"}), 400 # Validate range_type

        selected_date = datetime.strptime(selected_date, "%Y-%m-%d")  # Convert string to datetime object for comparison

        filtered_rows = []  # List to hold rows that match the selected date range

        with open(CSV_FILE, mode='r') as file:  # Read the CSV file and filter rows based on the selected date range
            reader = csv.DictReader(file)  # Use DictReader to access columns by name

            for row in reader:       # Try to parse the timestamp and filter rows based on the selected date and range type
                try:                 # If timestamp is missing or in wrong format, skip the row
                    row_time = datetime.strptime(      # Parse the timestamp from the row for comparison
                        row["Timestamp"], "%Y-%m-%d %H:%M:%S"  # Assuming the timestamp is in this format, adjust if different
                    ) 

                    # 🔥 FILTER LOGIC
                    if range_type == "day":   # For 'day' range type, we want to include rows that match the selected date (ignoring time)
                        if row_time.date() == selected_date.date():  # Compare only the date part of the timestamp with the selected date
                            filtered_rows.append(row)# For 'week' range type, we want to include rows that fall within the week of the selected date (Monday to Sunday)

                    elif range_type == "week":# Calculate the start and end of the week based on the selected date (Monday to Sunday)
                        start = selected_date - timedelta(days=selected_date.weekday())# Start of the week (Monday)
                        end = start + timedelta(days=6)# End of the week (Sunday)

                        if start.date() <= row_time.date() <= end.date():# Check if the row's date falls within the start and end of the week
                            filtered_rows.append(row)#

                    elif range_type == "month": # For 'month' range type, we want to include rows that match the month and year of the selected date
                        if ( # Check if the row's year and month match the selected date's year and month
                            row_time.year == selected_date.year and
                            row_time.month == selected_date.month
                        ):# If the row's timestamp falls within the selected month and year, include it in the filtered rows
                            filtered_rows.append(row)

                    elif range_type == "year": # For 'year' range type, we want to include rows that match the year of the selected date
                        if row_time.year == selected_date.year:# Check if the row's year matches the selected date's year
                            filtered_rows.append(row)# If the range_type is not recognized, return an error response

                except: # If there was an error parsing the timestamp, skip this row and
                    continue # If there was an error parsing the timestamp, skip this row and continue with the next one

        # 🔥 IMPORTANT: include time + value
        def extract_with_time(field):
            result = []
            for r in filtered_rows:
                try:
                    result.append({
                        "time": r["Timestamp"],
                        "value": float(r[field])
                    })
                except:
                    continue
            return result

        # 🔥 FINAL RESPONSE
        return jsonify({
            "temperature": extract_with_time("Temperature (°C)"),
            "humidity": extract_with_time("Humidity (%)"),
            "co2": extract_with_time("CO2 (PPM)"),
            "pm1": extract_with_time("PM 1 (µg/m³)"),
            "pm2_5": extract_with_time("PM 2.5 (µg/m³)"),
            "pm10": extract_with_time("PM 10 (µg/m³)")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/log')
def view_log():
    log_data = []
    try:
        with open(CSV_FILE, mode='r') as file:
            reader = csv.reader(file)
            headers = next(reader)
            for row in reader:
                log_data.append(row)
        return render_template('log.html', headers=headers, rows=log_data)
    except Exception as e:
        return f"Error reading log file: {str(e)}"

if __name__ == '__main__':
    print(f"Server starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Waiting for sensor data...")
    app.run(host='0.0.0.0', debug=True, port=5000)