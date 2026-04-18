from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import csv
import os

app = Flask(__name__)
CORS(app)

CSV_FILE = 'sensor_data.csv'

# ---------------- INIT CSV ----------------
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='', encoding='latin-1') as file:
        writer = csv.writer(file)
        writer.writerow([
            "Serial No.", "Timestamp",
            "Temperature (°C)", "Humidity (%)",
            "CO2 (PPM)", "PM 1 (µg/m³)", "PM 2.5 (µg/m³)", "PM 10 (µg/m³)"
        ])

# ---------------- UPDATE DATA ----------------
@app.route('/update', methods=['POST'])
def update_parameters():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        serial_no = 1
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, mode='r', encoding='latin-1') as file:
                serial_no = sum(1 for _ in file)

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

        return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- HELPERS ----------------
POINTS = 260

def get_total_duration(range_type, selected_date):
    if range_type == "day":
        return 1440
    elif range_type == "week":
        return 10080
    elif range_type == "month":
        next_month = selected_date.replace(day=28) + timedelta(days=4)
        days = (next_month - timedelta(days=next_month.day)).day
        return days * 1440
    elif range_type == "year":
        year = selected_date.year
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return (366 if leap else 365) * 1440


def get_time_position(dt, range_type):
    minutes = dt.hour * 60 + dt.minute

    if range_type == "day":
        return minutes
    elif range_type == "week":
        return dt.weekday() * 1440 + minutes
    elif range_type == "month":
        return (dt.day - 1) * 1440 + minutes
    elif range_type == "year":
        return (dt.timetuple().tm_yday - 1) * 1440 + minutes


def map_to_slots(data, range_type, selected_date):
    if not data:
        return [0] * POINTS

    total = get_total_duration(range_type, selected_date)
    slots = [[] for _ in range(POINTS)]

    for item in data:
        try:
            dt = datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S")
            pos = get_time_position(dt, range_type)
            index = int((pos / total) * POINTS)

            if 0 <= index < POINTS:
                slots[index].append(item["value"])
        except:
            continue

    result = []
    last = data[0]["value"]

    for bucket in slots:
        if bucket:
            avg = sum(bucket) / len(bucket)
            last = avg
            result.append(avg)
        else:
            result.append(last)

    return result


# ---------------- GET DATA ----------------
@app.route('/data', methods=['GET'])
def get_data():
    try:
        range_type = request.args.get('range', 'day')
        selected_date = request.args.get('date')

        if not selected_date:
            return jsonify({"error": "Date required"}), 400

        selected_date = datetime.strptime(selected_date, "%Y-%m-%d")

        filtered = []

        with open(CSV_FILE, mode='r', encoding='latin-1') as file:
            reader = csv.DictReader(file)

            for row in reader:
                try:
                    row_time = datetime.strptime(
                        row["Timestamp"], "%Y-%m-%d %H:%M:%S"
                    )

                    if range_type == "day":
                        if row_time.date() == selected_date.date():
                            filtered.append(row)

                    elif range_type == "week":
                        start = selected_date - timedelta(days=selected_date.weekday())
                        end = start + timedelta(days=6)
                        if start.date() <= row_time.date() <= end.date():
                            filtered.append(row)

                    elif range_type == "month":
                        if row_time.year == selected_date.year and row_time.month == selected_date.month:
                            filtered.append(row)

                    elif range_type == "year":
                        if row_time.year == selected_date.year:
                            filtered.append(row)

                except:
                    continue

        def extract(field):
            arr = []
            for r in filtered:
                try:
                    arr.append({
                        "time": r["Timestamp"],
                        "value": float(r[field])
                    })
                except:
                    continue
            return arr

        temp = map_to_slots(extract("Temperature (°C)"), range_type, selected_date)
        hum = map_to_slots(extract("Humidity (%)"), range_type, selected_date)

        return jsonify({
            "temperature": temp,
            "humidity": hum
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# # ---------------- MAIN ----------------
# if __name__ == '__main__':
#     app.run()

if __name__ == '__main__':
    print(f"Server starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Waiting for sensor data...")
    app.run(host='0.0.0.0', debug=True, port=5000)