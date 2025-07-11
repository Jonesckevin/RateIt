from flask import Flask, render_template_string, request, jsonify, send_from_directory, send_file
import json
import csv
import os
import shutil
import datetime
from collections import defaultdict
from werkzeug.utils import secure_filename

app = Flask(__name__)

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), 'resource')
CONFIG_FILE = os.path.join(RESOURCE_DIR, 'config.json')
JSON_FILE = 'ratings.json'
CSV_FILE = 'ratings.csv'
ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), 'archive')
TEMPLATE_FILE = os.path.join(RESOURCE_DIR, 'template.html')
BACKGROUND_DIR = os.path.join(RESOURCE_DIR, 'backgrounds')
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

def load_config():
    if not os.path.exists(RESOURCE_DIR):
        os.makedirs(RESOURCE_DIR)
    if not os.path.exists(CONFIG_FILE):
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
        changed = False
        if "num_buttons" not in config:
            config["num_buttons"] = 5
            changed = True
        if "port" not in config:
            config["port"] = 7331
            changed = True
        theme_keys = ['font', 'textColor', 'glowColor', 'headingColor', 'menuBg', 'bgImg']
        if "theme" not in config:
            config["theme"] = {}
        for key in theme_keys:
            if key in config:
                config["theme"][key] = config[key]
                del config[key]
                changed = True
        defaults = {
            "font": "Consolas",
            "textColor": "#f3f3f3",
            "glowColor": "#1bd602",
            "headingColor": "#cfd6da",
            "menuBg": "#181b20",
            "bgImg": None
        }
        for k, v in defaults.items():
            if k not in config["theme"]:
                config["theme"][k] = v
                changed = True
        if "rainbow_glow" not in config:
            config["rainbow_glow"] = True
            changed = True
        if changed:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
    return config

config = load_config()

if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, 'w') as f:
        json.dump([], f)
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'rating'])  # Date first

if not os.path.exists(ARCHIVE_DIR):
    os.makedirs(ARCHIVE_DIR)

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
    return render_template_string(
        html_template,
        hotkeys=config['hotkeys'],
        num_buttons=config.get('num_buttons', 5),
        config=config,
        theme=config.get('theme', {})
    )

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

    default_keys = [str(i) for i in range(1, 10)] + (['0'] if max_rating >= 10 else [])
    if key in default_keys:
        return jsonify({"success": False, "message": f"Default keys 1-{'0' if max_rating >= 10 else max_rating} are always mapped."})

    numpad_keys = [f'Numpad{i}' for i in range(0, 10)]
    if key in numpad_keys:
        return jsonify({"success": False, "message": "Numpad keys 0-9 are reserved for default mappings."})

    for k, v in list(config['hotkeys'].items()):
        if k == key:
            del config['hotkeys'][k]
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

@app.route('/set_max_columns', methods=['POST'])
def set_max_columns():
    data = request.get_json()
    max_cols = data.get('max_columns')
    try:
        max_cols = int(max_cols)
        if not (1 <= max_cols <= 10):
            raise ValueError
    except Exception:
        return jsonify({"success": False, "message": "Invalid number."}), 400
    config['max_columns'] = max_cols
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    return jsonify({"success": True})

@app.route('/set_title', methods=['POST'])
def set_title():
    data = request.get_json()
    title = data.get('title', '').strip()
    if not title:
        return jsonify({"success": False, "message": "Title cannot be empty."}), 400
    config['title'] = title
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    return jsonify({"success": True})

@app.route('/set_theme', methods=['POST'])
def set_theme():
    data = request.get_json()
    theme_keys = ['font', 'textColor', 'glowColor', 'headingColor', 'menuBg', 'bgImg']
    if "theme" not in config:
        config["theme"] = {}
    for key in theme_keys:
        if key in data:
            config["theme"][key] = data[key]
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    return jsonify({"success": True})

@app.route('/set_rainbow_glow', methods=['POST'])
def set_rainbow_glow():
    data = request.get_json()
    val = data.get('rainbow_glow')
    config['rainbow_glow'] = bool(val)
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

    date_ratings = []
    for date_str, ratings in data.items():
        try:
            if not date_str or date_str in ("", None):
                continue
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            date_ratings.append((dt, ratings))
        except Exception:
            continue

    date_ratings.sort(key=lambda x: x[0])

    if range_param != "all":
        try:
            days = int(range_param)
            if date_ratings:
                last_date = date_ratings[-1][0]
                min_date = last_date - datetime.timedelta(days=days-1)
                date_ratings = [(dt, r) for dt, r in date_ratings if dt >= min_date]
        except Exception:
            pass

    grouped = defaultdict(list)
    if group_by == "day":
        for dt, ratings in date_ratings:
            grouped[dt.strftime("%Y-%m-%d")].extend(ratings)
    elif group_by == "week":
        for dt, ratings in date_ratings:
            year, week, _ = dt.isocalendar()
            key = f"{year}-W{week:02d}"
            grouped[key].extend(ratings)
    elif group_by == "month":
        for dt, ratings in date_ratings:
            key = dt.strftime("%Y-%m")
            grouped[key].extend(ratings)
    else:
        for dt, ratings in date_ratings:
            grouped[dt.strftime("%Y-%m-%d")].extend(ratings)

    timeline = []
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

@app.route('/upload_data', methods=['POST'])
def upload_data():
    file = request.files.get('file')
    dtype = request.form.get('type')
    if not file or dtype not in ('csv', 'json'):
        return jsonify({'success': False, 'message': 'Invalid upload.'}), 400
    filename = secure_filename(file.filename)
    if dtype == 'csv':
        if not filename.lower().endswith('.csv'):
            return jsonify({'success': False, 'message': 'Must upload a CSV file.'}), 400
        archive_file(CSV_FILE)
        file.save(CSV_FILE)
        return jsonify({'success': True, 'message': 'CSV uploaded.'})
    elif dtype == 'json':
        if not filename.lower().endswith('.json'):
            return jsonify({'success': False, 'message': 'Must upload a JSON file.'}), 400
        archive_file(JSON_FILE)
        file.save(JSON_FILE)
        return jsonify({'success': True, 'message': 'JSON uploaded.'})
    return jsonify({'success': False, 'message': 'Unknown error.'}), 400

@app.route('/download_data/<dtype>')
def download_data(dtype):
    if dtype == 'csv':
        return send_file(CSV_FILE, as_attachment=True, download_name='ratings.csv')
    elif dtype == 'json':
        return send_file(JSON_FILE, as_attachment=True, download_name='ratings.json')
    else:
        return "Invalid type", 400

@app.route('/reset_data', methods=['POST'])
def reset_data():
    archive_file(CSV_FILE)
    archive_file(JSON_FILE)
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'rating'])
    with open(JSON_FILE, 'w') as f:
        json.dump([], f)
    return jsonify({'success': True, 'message': 'Databases reset and backed up.'})

if __name__ == '__main__':
    try:
        port = int(config.get('port', 7331))
    except Exception:
        port = 7331
    app.run(debug=True, port=port)