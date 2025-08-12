import os
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'legal_documents')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload-document', methods=['POST'])
def upload_document():
    print("Received upload request")  # <-- add this
    if 'document' not in request.files:
        print("No file part in request")  # <-- add this
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['document']
    print(f"File received: {file.filename}")  # <-- add this

    if file.filename == '':
        print("Empty filename")  # <-- add this
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    print(f"Saving file to: {save_path}")  # <-- add this

    try:
        file.save(save_path)
        print(f"File saved successfully at: {save_path}")
        return jsonify({"message": "File uploaded successfully", "filename": filename}), 200
    except Exception as e:
        print(f"Error saving file: {e}")
        return jsonify({"error": "Failed to save file", "details": str(e)}), 500



@app.route('/documents/list')
def list_documents():
    try:
        files = os.listdir(app.config['UPLOAD_FOLDER'])
    except Exception as e:
        print(f"Error listing files: {e}")
        return jsonify([])

    documents = []
    for f in files:
        documents.append({
            "filename": f,
            "title": os.path.splitext(f)[0].replace('_', ' ').title(),
            "url": f"/static/legal_documents/{f}"
        })
    return jsonify(documents)
