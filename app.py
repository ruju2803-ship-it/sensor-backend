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
    with open(CSV_FILE, mode='w', newline='', encoding='latin-1') as file:
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
            with open(CSV_FILE, mode='r', encoding='latin-1') as file:
                serial_no = sum(1 for row in file)

        with open(CSV_FILE, mode='a', newline='', encoding='latin-1') as file:
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


POINTS = 260

def get_step(range_type):
    if range_type == "day":
        return 5
    elif range_type == "week":
        return 38
    elif range_type == "month":
        return 166
    elif range_type == "year":
        return 2021


def map_to_slots(data, range_type, selected_date):
    if not data:
        return [0] * POINTS

    #  sort by time
    data.sort(key=lambda x: x["time"])

    step = get_step(range_type)

    result = []

    # 🔹 pick every Nth value
    for i in range(0, len(data), step):
        try:
            result.append(data[i]["value"])
        except:
            continue

    # 🔹 ensure exactly 260 points
    if len(result) >= POINTS:
        return result[:POINTS]
    else:
        # fill remaining with last value
        last_value = result[-1] if result else 0
        while len(result) < POINTS:
            result.append(last_value)

    return result

@app.route('/data', methods=['GET']) # New endpoint for historical data
def get_data():
    try:
        range_type = request.args.get('range', 'day')
        selected_date = request.args.get('date')

        if not selected_date:
            return jsonify({"error": "Date required"}), 400

        selected_date = datetime.strptime(selected_date, "%Y-%m-%d")

        filtered_rows = []

        with open(CSV_FILE, mode='r', encoding='latin-1') as file:
            reader = csv.DictReader(file)

            for row in reader:
                try:
                    row_time = datetime.strptime(
                        row["Timestamp"], "%Y-%m-%d %H:%M:%S"
                    )

                    if range_type == "day":
                        if row_time.date() == selected_date.date():
                            filtered_rows.append(row)

                    elif range_type == "week":
                        start = selected_date - timedelta(days=selected_date.weekday())
                        end = start + timedelta(days=6)

                        if start.date() <= row_time.date() <= end.date():
                            filtered_rows.append(row)

                    elif range_type == "month":
                        if (
                            row_time.year == selected_date.year and
                            row_time.month == selected_date.month
                        ):
                            filtered_rows.append(row)

                    elif range_type == "year":
                        if row_time.year == selected_date.year:
                            filtered_rows.append(row)

                except:
                    continue

        # 🔥 extract function (same)
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

        # ✅ NOW PROPERLY INSIDE FUNCTION
        temp_raw = extract_with_time("Temperature (°C)")
        hum_raw = extract_with_time("Humidity (%)")
        co2_raw = extract_with_time("CO2 (PPM)")
        pm1_raw = extract_with_time("PM 1 (µg/m³)")
        pm2_5_raw = extract_with_time("PM 2.5 (µg/m³)")
        pm10_raw = extract_with_time("PM 10 (µg/m³)")

        return jsonify({
            "temperature": map_to_slots(temp_raw, range_type, selected_date),
            "humidity": map_to_slots(hum_raw, range_type, selected_date),
            "co2": map_to_slots(co2_raw, range_type, selected_date),
            "pm1": map_to_slots(pm1_raw, range_type, selected_date),
            "pm2_5": map_to_slots(pm2_5_raw, range_type, selected_date),
            "pm10": map_to_slots(pm10_raw, range_type, selected_date)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/log')
def view_log():
    log_data = []
    try:
        with open(CSV_FILE, mode='r', encoding='latin-1') as file:
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