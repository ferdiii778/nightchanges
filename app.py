from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_mail import Mail, Message
from pymongo import MongoClient
from bson.objectid import ObjectId
import random
import string
import jwt
from datetime import datetime, timedelta
import cv2
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask import send_from_directory
from routes.face_routes import face_bp

app = Flask(__name__)
app.register_blueprint(face_bp, url_prefix="/api")
app.config['SECRET_KEY'] = 'gajah_terbang'
CORS(app)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# === MongoDB Configuration ===
client = MongoClient(os.environ.get("MONGODB_URI"))
db = client['guardian']
users = db['user']
otp_collection = db['otp']
cameras = db['cameras']

# === Flask-Mail Configuration ===
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'guardiansmarthome99@gmail.com'
app.config['MAIL_PASSWORD'] = 'ocbr pfus awcs jsst'
mail = Mail(app)

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(email, otp):
    try:
        msg = Message('Kode OTP Verifikasi Anda', sender='guardiansmarthome99@gmail.com', recipients=[email])
        msg.body = f"Kode OTP Anda adalah: {otp}"
        mail.send(msg)
        return True
    except Exception as e:
        print("Gagal kirim email:", e)
        return False

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('.', filename)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data['name']
    email = data['email']
    phone = data['phone']
    password = generate_password_hash(data['password'])

    existing_user = users.find_one({"$or": [{"email": email}, {"phone": phone}]})
    if existing_user:
        if not existing_user.get("is_verified", False):
            otp = generate_otp()
            otp_collection.insert_one({"user_id": str(existing_user['_id']), "otp_code": otp, "created_at": datetime.utcnow()})
            send_otp_email(email, otp)
            return jsonify({'status': True, 'message': 'Akun sudah ada tapi belum diverifikasi, OTP baru telah dikirim.', 'need_verification': True})
        return jsonify({'status': False, 'message': 'Email atau nomor sudah terdaftar'})

    result = users.insert_one({"name": name, "email": email, "phone": phone, "password": password, "is_verified": False})
    user_id = str(result.inserted_id)
    otp = generate_otp()
    otp_collection.insert_one({"user_id": user_id, "otp_code": otp, "created_at": datetime.utcnow()})
    send_otp_email(email, otp)
    return jsonify({'status': True, 'message': 'Berhasil daftar, cek email untuk OTP', 'need_verification': True})

@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    data = request.get_json()
    email = data['email']
    mode = data.get('mode', 'register')  # Tambahkan ini

    user = users.find_one({"email": email})
    if not user:
        return jsonify({'status': False, 'message': 'Email tidak ditemukan'})

    otp = generate_otp()
    otp_collection.insert_one({
        "user_id": str(user['_id']),
        "otp_code": otp,
        "created_at": datetime.utcnow(),
        "mode": mode  # Simpan mode sesuai keperluan
    })
    send_otp_email(email, otp)
    return jsonify({'status': True, 'message': 'OTP baru telah dikirim ke email'})

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')

    user = users.find_one({"email": email})
    if not user:
        return jsonify({'status': False, 'message': 'Email tidak ditemukan'})

    otp = generate_otp()
    otp_collection.insert_one({
        "user_id": str(user['_id']),
        "otp_code": otp,
        "created_at": datetime.utcnow(),
        "mode": "forgot_password"
    })
    send_otp_email(email, otp)

    return jsonify({'status': True, 'message': 'OTP lupa password berhasil dikirim'})

@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    new_password = data.get('new_password')

    if not email or not new_password:
        return jsonify({'status': False, 'message': 'Data tidak lengkap'}), 400

    hashed = generate_password_hash(new_password)
    result = users.update_one({"email": email}, {"$set": {"password": hashed}})
    
    if result.modified_count == 1:
        return jsonify({'status': True, 'message': 'Password berhasil diubah'})
    return jsonify({'status': False, 'message': 'Gagal mengubah password'})


@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp_input = data.get('otp')
    mode = data.get('mode', 'register')  # Default 'register' jika tidak dikirim

    user = users.find_one({"email": email})
    if not user:
        return jsonify({'status': False, 'message': 'Email tidak ditemukan'})

    latest_otp = otp_collection.find({"user_id": str(user['_id']), "mode": mode}).sort("created_at", -1).limit(1)
    for otp_doc in latest_otp:
        if otp_doc['otp_code'] == otp_input:
            if mode == 'register':
                users.update_one({"_id": user['_id']}, {"$set": {"is_verified": True}})
                return jsonify({'status': True, 'message': 'Verifikasi berhasil (register)'})
            elif mode == 'forgot_password':
                return jsonify({'status': True, 'message': 'Verifikasi berhasil, lanjut reset password'})
    
    return jsonify({'status': False, 'message': 'Kode OTP salah'})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data['email']
    password = data['password']
    
    user = users.find_one({"email": email})
    if not user:
        return jsonify({'status': False, 'message': 'Email tidak ditemukan'})
    if not check_password_hash(user['password'], password):
        return jsonify({'status': False, 'message': 'Password salah'})
    if not user.get('is_verified', False):
        return jsonify({'status': False, 'message': 'Akun belum diverifikasi'})
    
    token = jwt.encode(
        {'user_id': str(user['_id']), 'exp': datetime.utcnow() + timedelta(hours=2)},
        app.config['SECRET_KEY'],
        algorithm="HS256"
    )

    if 'api_key' not in user:
        api_key = str(uuid.uuid4())
        users.update_one({'_id': user['_id']}, {'$set': {'api_key': api_key}})
    else:
        api_key = user['api_key']

    # ✅ Tambahkan data user di response
    return jsonify({
        'status': True,
        'message': 'Login berhasil',
        'token': token,
        'api_key': api_key,
        'user_id': str(user['_id']),
        'name': user.get('name', ''),
        'email': user.get('email', ''),
        'phone': user.get('phone', '')
    })

@app.route('/dashboard/<user_id>', methods=['GET'])
def dashboard(user_id):
    user = users.find_one({"_id": ObjectId(user_id)})
    if user:
        return jsonify({'status': True, 'name': user['name'], 'email': user['email']})
    return jsonify({'status': False, 'message': 'User tidak ditemukan'})

@app.route('/user_profile/<user_id>', methods=['GET'])
def user_profile(user_id):
    user = users.find_one(
        {"_id": ObjectId(user_id)},
        {"name": 1, "email": 1, "foto_profil": 1}
    )

    if not user:
        return jsonify({"status": False, "message": "User tidak ditemukan"}), 404

    # Cek apakah user sudah punya foto profil
    foto_profil = user.get('foto_profil')
    if foto_profil:
        foto_url = f"/profile_pics/{foto_profil}"
    else:
        # Gunakan URL gambar default
        foto_url = "/profile_pics/default.png"  # Pastikan file ini tersedia di static/uploads

    return jsonify({
        "status": True,
        "name": user['name'],
        "email": user['email'],
        "foto_profil": foto_url
    })

@app.route('/profile_pics/<filename>')
def serve_profile_picture(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/upload_profile', methods=['POST'])
def upload_profile():
    file = request.files.get('file')
    email = request.form.get('email')

    if not file or not email:
        return jsonify({'status': 'failed', 'message': 'File atau email tidak ditemukan'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Simpan hanya nama file ke MongoDB
    users.update_one(
        {'email': email},
        {'$set': {'foto_profil': filename}}
    )

    return jsonify({
        'status': 'success',
        'message': 'Foto profil berhasil diunggah',
        'file_url': f'/profile_pics/{filename}'
    }), 200

@app.route('/update_profile/<user_id>', methods=['PUT'])
def update_profile(user_id):
    data = request.get_json()
    update_data = {
        "name": data.get("name"),
        "email": data.get("email"),
        "phone": data.get("phone")
    }

    result = users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    if result.modified_count == 1:
        return jsonify({"status": True, "message": "Profil berhasil diperbarui"})
    else:
        return jsonify({"status": False, "message": "Tidak ada perubahan data"})

@app.route("/cctv", methods=["POST"])
def add_camera():
    data = request.get_json()

    required_fields = ["user_id", "nama_kamera", "ip_address", "path"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"status": False, "message": f"{field} wajib diisi"}), 400

    camera = {
        "user_id": data["user_id"],
        "nama_kamera": data["nama_kamera"],
        "ip_address": data["ip_address"],
        "port": data.get("port", 554),  # default port RTSP
        "username": data.get("username", ""),
        "password": data.get("password", ""),
        "path": data["path"],
        "lokasi": data.get("lokasi", ""),
        "created_at": datetime.utcnow()
    }

    result = cameras.insert_one(camera)
    return jsonify({"status": True, "message": "Perangkat CCTV berhasil ditambahkan", "camera_id": str(result.inserted_id)}), 201


@app.route("/cctv/<user_id>", methods=["GET"])
def get_cameras(user_id):
    cameras_list = list(cameras.find({"user_id": user_id}))
    for cam in cameras_list:
        cam["_id"] = str(cam["_id"])
    return jsonify(cameras_list), 200

@app.route('/snapshot/<camera_id>', methods=['GET'])
def snapshot(camera_id):
    camera = cameras.find_one({'_id': ObjectId(camera_id)})
    if not camera:
        return "Camera not found", 404

    ip = camera['ip_address']
    port = camera.get('port', 554)
    path = camera['path']
    username = camera.get('username', '')
    password = camera.get('password', '')

    auth = f"{username}:{password}@" if username and password else ""
    rtsp_url = f"rtsp://{auth}{ip}:{port}/{path}"

    cap = cv2.VideoCapture(rtsp_url)
    success, frame = cap.read()
    cap.release()

    if not success:
        return "Failed to capture frame", 500

    _, jpeg = cv2.imencode('.jpg', frame)
    return Response(jpeg.tobytes(), mimetype='image/jpeg')

@app.route('/cctv/<id>', methods=['PUT'])
def update_cctv(id):
    from bson.objectid import ObjectId
    from bson.errors import InvalidId
    data = request.json

    try:
        object_id = ObjectId(id)
    except InvalidId:
        return jsonify({"status": False, "message": "ID tidak valid"}), 400

    print("Cek apakah ID ada:", object_id)
    cek = cameras.find_one({"_id": object_id})
    print("Data ditemukan:", cek)

    result = cameras.update_one(
        {"_id": object_id},
        {"$set": {
            "nama_kamera": data["nama_kamera"],
            "ip_address": data["ip_address"],
            "port": data["port"],
            "username": data["username"],
            "password": data["password"],
            "path": data["path"],
            "lokasi": data["lokasi"],
        }}
    )

    print("Matched:", result.matched_count)

    if result.matched_count > 0:
        return jsonify({"status": True, "message": "Data CCTV berhasil diupdate"}), 200
    else:
        return jsonify({"status": False, "message": "CCTV tidak ditemukan"}), 404

@app.route('/cctv/<id>', methods=['DELETE'])
def delete_cctv(id):
    from bson.objectid import ObjectId
    from bson.errors import InvalidId

    try:
        object_id = ObjectId(id)
    except InvalidId:
        return jsonify({"status": False, "message": "ID tidak valid"}), 400

    result = cameras.delete_one({"_id": object_id})

    if result.deleted_count > 0:
        return jsonify({"status": True, "message": "CCTV berhasil dihapus"}), 200
    else:
        return jsonify({"status": False, "message": "CCTV tidak ditemukan"}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
