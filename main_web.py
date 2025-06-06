from flask import Flask, render_template_string, request, jsonify, send_from_directory
import json
import csv
import os
import shutil
import datetime
from collections import defaultdict

app = Flask(__name__)

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), 'resource')
CONFIG_FILE = os.path.join(RESOURCE_DIR, 'config.json')
JSON_FILE = 'ratings.json'
CSV_FILE = 'ratings.csv'
ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), 'archive')
TEMPLATE_FILE = os.path.join(RESOURCE_DIR, 'template.html')
BACKGROUND_DIR = os.path.join(RESOURCE_DIR, 'backgrounds')
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

# Load or create config file for hotkeys
def load_config():
    if not os.path.exists(RESOURCE_DIR):
        os.makedirs(RESOURCE_DIR)
    if not os.path.exists(CONFIG_FILE):
        # Default hotkeys: 1-5, default num_buttons: 5, default port: 7331
        config = {
            "hotkeys": {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10},
            "num_buttons": 5,
            "port": 7331
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    else:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        # Backward compatibility: add num_buttons or port if missing
        changed = False
        if "num_buttons" not in config:
            config["num_buttons"] = 5
            changed = True
        if "port" not in config:
            config["port"] = 7331
            changed = True
        if changed:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
    return config

config = load_config()

# Ensure ratings files exist
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, 'w') as f:
        json.dump([], f)
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'rating'])  # Date first

# Ensure archive directory exists
if not os.path.exists(ARCHIVE_DIR):
    os.makedirs(ARCHIVE_DIR)

# Ensure backgrounds directory exists
if not os.path.exists(BACKGROUND_DIR):
    os.makedirs(BACKGROUND_DIR)

def archive_file(filepath):
    if os.path.exists(filepath):
        basename = os.path.basename(filepath)
        date_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_name = f"{basename}.{date_str}.bak"
        shutil.move(filepath, os.path.join(ARCHIVE_DIR, archive_name))

def ensure_json_file():
    if not os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'w') as f:
            json.dump([], f)
    else:
        try:
            with open(JSON_FILE, 'r') as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError
        except Exception:
            archive_file(JSON_FILE)
            with open(JSON_FILE, 'w') as f:
                json.dump([], f)

def ensure_csv_file():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'rating'])
    else:
        try:
            with open(CSV_FILE, 'r', newline='') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header != ['date', 'rating']:
                    raise ValueError
        except Exception:
            archive_file(CSV_FILE)
            with open(CSV_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'rating'])

ensure_json_file()
ensure_csv_file()

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

@app.route('/resource/<path:filename>')
def resource(filename):
    return send_from_directory(RESOURCE_DIR, filename)

@app.route('/backgrounds/<filename>')
def get_background(filename):
    return send_from_directory(BACKGROUND_DIR, filename)

@app.route('/list_backgrounds')
def list_backgrounds():
    files = []
    for fname in os.listdir(BACKGROUND_DIR):
        if allowed_image(fname):
            files.append(fname)
    return jsonify(files)

@app.route('/upload_background', methods=['POST'])
def upload_background():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400
    if file and allowed_image(file.filename):
        filename = file.filename
        # Avoid overwriting: add timestamp if exists
        base, ext = os.path.splitext(filename)
        i = 1
        while os.path.exists(os.path.join(BACKGROUND_DIR, filename)):
            filename = f"{base}_{i}{ext}"
            i += 1
        file.save(os.path.join(BACKGROUND_DIR, filename))
        return jsonify({'success': True, 'filename': filename})
    return jsonify({'success': False, 'message': 'Invalid file type'}), 400

@app.route('/delete_background', methods=['POST'])
def delete_background():
    data = request.get_json()
    filename = data.get('filename')
    if not filename or not allowed_image(filename):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400
    filepath = os.path.join(BACKGROUND_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'File not found'}), 404

@app.route('/')
def index():
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html_template = f.read()
    return render_template_string(html_template, hotkeys=config['hotkeys'], num_buttons=config.get('num_buttons', 5))

@app.route('/rate', methods=['POST'])
def rate():
    data = request.get_json()
    rating = data.get('rating')
    try:
        rating = int(rating)
    except Exception:
        return jsonify({"message": "Invalid rating."}), 400
    max_rating = config.get('num_buttons', 10)  # default to 10
    if rating not in range(1, max_rating + 1):
        return jsonify({"message": "Invalid rating."}), 400

    now_str = datetime.datetime.now().isoformat(timespec='seconds')

    # Append to JSON (store as list of objects with rating and date)
    with open(JSON_FILE, 'r+') as f:
        try:
            ratings = json.load(f)
        except Exception:
            ratings = []
        if ratings and isinstance(ratings[0], int):
            ratings = [{"rating": r, "date": ""} for r in ratings]
        ratings.append({"date": now_str, "rating": rating})
        f.seek(0)
        json.dump(ratings, f)
        f.truncate()

    # Append to CSV (date first)
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([now_str, rating])

    return jsonify({"message": f"Rating {rating} saved!"})

@app.route('/map_hotkey', methods=['POST'])
def map_hotkey():
    data = request.get_json()
    key = data.get('key')
    rating = data.get('rating')
    try:
        rating = int(rating)
    except Exception:
        return jsonify({"success": False, "message": "Invalid rating."})
    max_rating = config.get('num_buttons', 10)  # default to 10

    # Allow default keys '1'-'9' and '0' for ratings 1-10
    default_keys = [str(i) for i in range(1, 10)] + (['0'] if max_rating >= 10 else [])
    if key in default_keys:
        return jsonify({"success": False, "message": f"Default keys 1-{'0' if max_rating >= 10 else max_rating} are always mapped."})

    # Also block Numpad keys for default mappings
    numpad_keys = [f'Numpad{i}' for i in range(0, 10)]
    if key in numpad_keys:
        return jsonify({"success": False, "message": "Numpad keys 0-9 are reserved for default mappings."})

    # Remove key from any previous mapping
    for k, v in list(config['hotkeys'].items()):
        if k == key:
            del config['hotkeys'][k]
    # Remove previous mapping for this rating (except for default keys)
    for k, v in list(config['hotkeys'].items()):
        if v == rating and k not in default_keys and k not in numpad_keys:
            del config['hotkeys'][k]
    config['hotkeys'][key] = rating
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    return jsonify({"success": True, "message": f"Mapped '{key}' to rating {rating}."})

@app.route('/set_num_buttons', methods=['POST'])
def set_num_buttons():
    data = request.get_json()
    num = data.get('num_buttons')
    try:
        num = int(num)
        if not (1 <= num <= 10):
            raise ValueError
    except Exception:
        return jsonify({"success": False, "message": "Invalid number."}), 400
    config['num_buttons'] = num
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    return jsonify({"success": True})

@app.route('/timeline_data')
def timeline_data():
    """
    Returns average ratings per group (day/week/month) as a list of {date, avg_rating, count}.
    Query params:
      - 'source': 'csv' or 'json'
      - 'range': number of days (int) or 'all'
      - 'group': 'day', 'week', 'month'
    """
    source = request.args.get('source', 'csv')
    range_param = request.args.get('range', '30')
    group_by = request.args.get('group', 'day')
    data = defaultdict(list)
    if source == 'json':
        try:
            with open(JSON_FILE, 'r') as f:
                ratings = json.load(f)
            for entry in ratings:
                date = entry.get('date', '')
                rating = entry.get('rating', None)
                if not date or rating is None:
                    continue
                date_part = date.split('T')[0] if 'T' in date else date.split()[0]
                data[date_part].append(int(rating))
        except Exception:
            return jsonify({"success": False, "message": "Failed to read JSON."}), 500
    else:
        try:
            with open(CSV_FILE, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date = row.get('date', '')
                    rating = row.get('rating', None)
                    if not date or rating is None:
                        continue
                    date_part = date.split('T')[0] if 'T' in date else date.split()[0]
                    data[date_part].append(int(rating))
        except Exception:
            return jsonify({"success": False, "message": "Failed to read CSV."}), 500

    # Convert date keys to datetime.date
    date_ratings = []
    for date_str, ratings in data.items():
        try:
            if not date_str or date_str in ("", None):
                continue
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            date_ratings.append((dt, ratings))
        except Exception:
            # skip invalid date formats
            continue

    # Sort by date
    date_ratings.sort(key=lambda x: x[0])

    # Filter by range
    if range_param != "all":
        try:
            days = int(range_param)
            if date_ratings:
                last_date = date_ratings[-1][0]
                min_date = last_date - datetime.timedelta(days=days-1)
                date_ratings = [(dt, r) for dt, r in date_ratings if dt >= min_date]
        except Exception:
            pass

    # Grouping
    grouped = defaultdict(list)
    if group_by == "day":
        for dt, ratings in date_ratings:
            grouped[dt.strftime("%Y-%m-%d")].extend(ratings)
    elif group_by == "week":
        for dt, ratings in date_ratings:
            # ISO week: (year, week)
            year, week, _ = dt.isocalendar()
            key = f"{year}-W{week:02d}"
            grouped[key].extend(ratings)
    elif group_by == "month":
        for dt, ratings in date_ratings:
            key = dt.strftime("%Y-%m")
            grouped[key].extend(ratings)
    else:
        # fallback to day
        for dt, ratings in date_ratings:
            grouped[dt.strftime("%Y-%m-%d")].extend(ratings)

    # Prepare timeline
    timeline = []
    # Sort keys chronologically
    def sort_key(k):
        if group_by == "day":
            return k
        elif group_by == "week":
            y, w = k.split('-W')
            return f"{y}-{int(w):02d}"
        elif group_by == "month":
            return k
        return k

    for key in sorted(grouped.keys(), key=sort_key):
        ratings = grouped[key]
        avg = sum(ratings) / len(ratings) if ratings else 0
        timeline.append({
            "date": key,
            "avg_rating": round(avg, 2),
            "count": len(ratings)
        })
    return jsonify({"success": True, "timeline": timeline})

# If this program is being run by flash or python, start the server
# Run using `flask run` or `python main_web.py`
# For Gunicorn, use `gunicorn -w 4 -b 0.0.0.0:7331 main_web:app`
if __name__ == '__main__':
    try:
        port = int(config.get('port', 7331))
    except Exception:
        port = 7331
    app.run(debug=True, port=port)