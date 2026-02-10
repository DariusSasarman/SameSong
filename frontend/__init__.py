import uuid
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from security.RateLimiter import not_available
from processing.celeryProcess import process_audio
from data.db_manager import init_db_on_startup

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Initialize database on startup
init_db_on_startup()

upload_dir = Path('/data/tmp')
upload_dir.mkdir(parents=True, exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    client_ip = request.remote_addr

    # 1. Check Rate Limits & Queue Capacity
    if not_available():
        return jsonify({"status": "rejected"}), 429

    # 2. Secure the file
    audio = request.files.get('audio_file')
    if not audio:
        return jsonify({"status": "error", "message": "No file"}), 400

    unique_file_name = f"{uuid.uuid4()}.wav"
    upload_path = upload_dir / unique_file_name
    audio.save(str(upload_path))

    # 3. Start Task & Register Ownership in Redis
    result = process_audio.delay(unique_file_name, client_ip)

    return jsonify({"task_id": result.id})


@app.route('/status/<task_id>')
def status(task_id):
    result = process_audio.AsyncResult(task_id)

    if result.ready() and result.successful():
            data = result.result
            return jsonify({
                "status": "done",
                "vibe_matches": data.get("vibe_matches"),
                "snippet_matches": data.get("snippet_matches")
            })
    return jsonify({"status": "processing"})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)