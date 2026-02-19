from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__, template_folder="live-server/templates", static_folder="live-server/static")

ENTRIES_FILE = "entries.json"
PRESETS_FILE = "presets.json"

def load_entries():
    if os.path.exists(ENTRIES_FILE):
        with open(ENTRIES_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def save_entries(entries):
    with open(ENTRIES_FILE, "w", encoding="utf-8") as file:
        json.dump(entries, file, ensure_ascii=False, indent=4)

def load_presets():
    if os.path.exists(PRESETS_FILE):
        with open(PRESETS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def save_presets(presets):
    with open(PRESETS_FILE, "w", encoding="utf-8") as file:
        json.dump(presets, file, ensure_ascii=False, indent=4)

entries = load_entries()
presets = load_presets()

@app.route("/")
def index():
    return "Сервер работает. Перейдите на /admin"

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/broadcast")
def broadcast():
    return render_template("broadcast.html")

@app.route("/competition")
def competition():
    return render_template("competition.html")

@app.route("/entries")
def get_entries():
    return jsonify(entries)

@app.route("/add_entry", methods=["POST"])
def add_entry():
    data = request.json
    new_id = max([entry["id"] for entry in entries], default=0) + 1
    data["id"] = new_id
    entries.append(data)
    save_entries(entries)
    return jsonify({"message": "Запись добавлена"}), 200

@app.route("/update_entry/<int:id>", methods=["PUT"])
def update_entry(id):
    data = request.json
    for entry in entries:
        if entry["id"] == id:
            entry.update(data)
            save_entries(entries)
            return jsonify({"message": "Запись обновлена"}), 200
    return jsonify({"error": "Запись не найдена"}), 404

@app.route("/delete_entry/<int:id>", methods=["DELETE"])
def delete_entry(id):
    global entries
    entries = [entry for entry in entries if entry["id"] != id]
    save_entries(entries)
    return jsonify({"message": "Запись удалена"}), 200

@app.route("/save_all_entries", methods=["POST"])
def save_all_entries():
    data = request.json
    entries.clear()
    entries.extend(data)
    save_entries(entries)
    return jsonify({"message": "Все записи сохранены"}), 200

@app.route("/reorder_entries", methods=["POST"])
def reorder_entries():
    data = request.json
    entries.clear()
    entries.extend(data)
    save_entries(entries)
    return jsonify({"message": "Порядок обновлён"}), 200

@app.route("/presets")
def get_presets():
    return jsonify(presets)

@app.route("/save_preset", methods=["POST"])
def save_preset():
    data = request.json
    presets.append(data)
    save_presets(presets)
    return jsonify({"message": "Пресет сохранён"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082, debug=True)
