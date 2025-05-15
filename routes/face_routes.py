# app/routes/face_routes.py
from flask import Blueprint, request, jsonify
import os

from services.video_proses import extract_and_crop_faces
from services.embedding_trainer import generate_embeddings
from services.face_recognize import start_monitoring

face_bp = Blueprint('face_routes', __name__)

@face_bp.route("/upload_video", methods=["POST"])
def upload_video():
    if 'video' not in request.files or 'label' not in request.form:
        return jsonify({"error": "Harap kirim file video dan label."}), 400

    video = request.files['video']
    label = request.form['label']

    os.makedirs("videos", exist_ok=True)
    filename = f"{label}.mp4"
    save_path = os.path.join("videos", filename)
    video.save(save_path)

    try:
        total_faces = extract_and_crop_faces(save_path, label)
        return jsonify({
            "message": "Video berhasil diunggah dan diproses.",
            "file": filename,
            "wajah_terekstrak": total_faces
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@face_bp.route("/train_ai", methods=["POST"])
def train_ai():
    if 'label' not in request.json:
        return jsonify({"error": "Label pengguna wajib disertakan."}), 400

    label = request.json['label']
    try:
        total_images = generate_embeddings(label)
        return jsonify({
            "message": f"Pelatihan selesai untuk '{label}'.",
            "jumlah_wajah_dilatih": total_images
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@face_bp.route("/monitoring/start", methods=["GET"])
def start_monitoring_api():
    try:
        message = start_monitoring()
        return jsonify({"message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500    
    

@face_bp.route("/wajah", methods=["GET"])
def get_all_faces():
    import os
    import glob
    from flask import request

    dataset_dir = "dataset"
    data = []

    if not os.path.exists(dataset_dir):
        return jsonify([])

    base_url = request.host_url.rstrip('/')  # contoh: http://192.168.1.x:5000

    for label in os.listdir(dataset_dir):
        cropped_dir = os.path.join(dataset_dir, label, "cropped")
        images = glob.glob(os.path.join(cropped_dir, "*.jpg"))
        image = images[0] if images else None

        # 🔥 FIX bagian ini:
        safe_image_path = image.replace("\\", "/") if image else None
        image_url = f"{base_url}/images/{safe_image_path}" if image else None

        data.append({
            "name": label.capitalize(),
            "id": f"wajah_{label}",
            "lastDetected": "-",
            "image": image_url,
        })

    return jsonify(data)


@face_bp.route("/wajah/<label>", methods=["DELETE"])
def delete_face_data(label):
    import shutil
    import os
    import numpy as np

    dataset_dir = f"dataset/{label}"
    video_path = f"videos/{label}.mp4"
    embeddings_path = "embeddings/embeddings.npy"
    labels_path = "embeddings/labels.npy"

    # Hapus folder dataset
    if os.path.exists(dataset_dir):
        shutil.rmtree(dataset_dir)

    # Hapus video asli yang diupload
    if os.path.exists(video_path):
        os.remove(video_path)

    # Hapus dari .npy
    if os.path.exists(embeddings_path) and os.path.exists(labels_path):
        embeddings = np.load(embeddings_path)
        labels = np.load(labels_path)

        labels_str = labels.astype(str)
        indices = np.where(labels_str != label)[0]

        new_embeddings = embeddings[indices]
        new_labels = labels_str[indices]

        np.save(embeddings_path, new_embeddings)
        np.save(labels_path, new_labels)

    return jsonify({"message": f"Wajah '{label}' berhasil dihapus"}), 200

