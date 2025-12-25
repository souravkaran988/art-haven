import os
from flask import Flask, send_from_directory, render_template, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- CONFIGURATION ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# CHANGE 1: Point to the 'build' folder (where our script moved the frontend)
app = Flask(__name__, static_folder='build', static_url_path='/', template_folder='build')
CORS(app)

# Database & Uploads
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# CHANGE 2: Keep uploads in a separate folder (not inside build)
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads') 
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- MODELS ---
# (Keep your existing models exactly as they were)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    profile_pic = db.Column(db.String(150), nullable=True)
    images = db.relationship('Image', backref='uploader', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='image', lazy=True)
    comments = db.relationship('Comment', backref='art', lazy=True)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_id = db.Column(db.Integer, db.ForeignKey('image.id'), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_id = db.Column(db.Integer, db.ForeignKey('image.id'), nullable=False)

# --- API ROUTES ---

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    hashed_password = generate_password_hash(data['password'], method='scrypt')
    new_user = User(username=data['username'], email=data['email'], password=hashed_password)
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User created successfully"}), 201
    except:
        return jsonify({"message": "User already exists"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        return jsonify({"message": "Login successful", "user_id": user.id, "username": user.username}), 200
    return jsonify({"message": "Invalid credentials"}), 401

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files: return jsonify({"message": "No file part"}), 400
    file = request.files['image']
    user_id = request.form.get('user_id')
    title = request.form.get('title')
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Save to the new uploads folder
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        new_image = Image(title=title, filename=filename, user_id=user_id)
        db.session.add(new_image)
        db.session.commit()
        return jsonify({"message": "Image uploaded successfully"}), 201
    return jsonify({"message": "Invalid file type"}), 400

@app.route('/images', methods=['GET'])
def get_images():
    images = Image.query.all()
    output = []
    for image in images:
        output.append({
            "id": image.id,
            "title": image.title,
            "filename": image.filename,
            "uploader": image.uploader.username
        })
    return jsonify(output)

@app.route('/profile/<username>')
def get_public_profile(username):
    user = User.query.filter_by(username=username).first()
    if not user: return jsonify({"message": "Not found"}), 404
    images = Image.query.filter_by(user_id=user.id).all()
    image_list = [{"id": i.id, "title": i.title, "filename": i.filename} for i in images]
    return jsonify({"username": user.username, "images": image_list, "profile_pic": user.profile_pic}), 200

# --- SERVING FILES ---

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # Serve images from the 'uploads' folder
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    # Serve static files (like CSS/JS) if they exist in build
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    # Otherwise, serve index.html (React handles the routing)
    return render_template('index.html')

# --- INITIALIZATION ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)