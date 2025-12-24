# Add 'render_template' to the list
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import random
from datetime import datetime # NEW: To timestamp comments

app = Flask(__name__, static_folder='build/static', template_folder='build')
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    profile_pic = db.Column(db.String(150), nullable=True)
    images = db.relationship('Image', backref='uploader', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True) # NEW

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='image', lazy=True)
    comments = db.relationship('Comment', backref='art', lazy=True) # NEW

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_id = db.Column(db.Integer, db.ForeignKey('image.id'), nullable=False)

# NEW: Comment Table
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_id = db.Column(db.Integer, db.ForeignKey('image.id'), nullable=False)

# --- Routes ---


# SERVE REACT FRONTEND
@app.route('/')
def serve():
    return render_template('index.html')

@app.route('/<path:path>')
def catch_all(path):
    return render_template('index.html')


@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    if User.query.filter_by(email=data['email']).first() or User.query.filter_by(username=data['username']).first():
        return jsonify({"message": "User already exists"}), 400
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    new_user = User(username=data['username'], email=data['email'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created!"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        return jsonify({"message": "Success", "user_id": user.id, "username": user.username, "profile_pic": user.profile_pic}), 200
    return jsonify({"message": "Invalid credentials"}), 401

@app.route('/user_details/<int:user_id>')
def get_user_details(user_id):
    user = User.query.get(user_id)
    if not user: return jsonify({"message": "User not found"}), 404
    return jsonify({"username": user.username, "email": user.email, "id": user.id, "profile_pic": user.profile_pic}), 200

# NEW: Add Comment Route
@app.route('/comment/<int:image_id>', methods=['POST'])
def add_comment(image_id):
    data = request.json
    new_comment = Comment(text=data['text'], user_id=data['user_id'], image_id=image_id)
    db.session.add(new_comment)
    db.session.commit()
    
    # Return the new comment so Frontend can show it immediately
    return jsonify({
        "id": new_comment.id,
        "text": new_comment.text,
        "username": new_comment.author.username,
        "profile_pic": new_comment.author.profile_pic
    }), 201

@app.route('/like/<int:image_id>', methods=['POST'])
def toggle_like(image_id):
    data = request.json
    user_id = data.get('user_id')
    existing_like = Like.query.filter_by(user_id=user_id, image_id=image_id).first()
    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify({"message": "Unliked", "status": "unliked"}), 200
    else:
        new_like = Like(user_id=user_id, image_id=image_id)
        db.session.add(new_like)
        db.session.commit()
        return jsonify({"message": "Liked", "status": "liked"}), 200

# UPDATED: Explore now includes comments
@app.route('/explore')
def explore_images():
    query = request.args.get('q')
    current_user_id = request.args.get('user_id')

    if query:
        images = Image.query.filter(Image.title.ilike(f'%{query}%')).all()
    else:
        images = Image.query.all()
        random.shuffle(images)

    image_list = []
    for img in images:
        is_liked = False
        if current_user_id:
            is_liked = Like.query.filter_by(user_id=current_user_id, image_id=img.id).first() is not None
        
        # Pack comments
        comments = []
        for c in img.comments:
            comments.append({
                "id": c.id, 
                "text": c.text, 
                "username": c.author.username,
                "profile_pic": c.author.profile_pic
            })

        image_list.append({
            "id": img.id, 
            "title": img.title, 
            "filename": img.filename,
            "username": img.uploader.username,
            "likes_count": len(img.likes),
            "is_liked": is_liked,
            "comments": comments # Send comments to frontend
        })
    return jsonify(image_list), 200

@app.route('/upload_profile_pic', methods=['POST'])
def upload_profile_pic():
    if 'image' not in request.files: return jsonify({"message": "No image"}), 400
    file = request.files['image']
    user_id = request.form.get('user_id')
    user = User.query.get(user_id)
    if user and file and allowed_file(file.filename):
        filename = secure_filename(f"profile_{user_id}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        user.profile_pic = filename
        db.session.commit()
        return jsonify({"message": "Updated", "profile_pic": filename}), 200
    return jsonify({"message": "Failed"}), 400

@app.route('/upload', methods=['POST'])
def upload_image():
    file = request.files['image']
    title = request.form.get('title')
    user_id = request.form.get('user_id')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        new_image = Image(title=title, filename=filename, user_id=user_id)
        db.session.add(new_image)
        db.session.commit()
        return jsonify({"message": "Uploaded"}), 201
    return jsonify({"message": "Error"}), 400

@app.route('/my_images/<int:user_id>')
def get_user_images(user_id):
    images = Image.query.filter_by(user_id=user_id).all()
    image_list = [{"id": img.id, "title": img.title, "filename": img.filename} for img in images]
    return jsonify(image_list), 200

@app.route('/update_image/<int:image_id>', methods=['PUT'])
def update_image(image_id):
    data = request.json
    image = Image.query.get(image_id)
    if not image or str(image.user_id) != str(data.get('user_id')): return jsonify({"message": "Unauthorized"}), 403
    image.title = data.get('title')
    db.session.commit()
    return jsonify({"message": "Updated"}), 200

@app.route('/delete/<int:image_id>', methods=['DELETE'])
def delete_image(image_id):
    image = Image.query.get(image_id)
    if image:
        try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image.filename))
        except: pass
        db.session.delete(image)
        db.session.commit()
        return jsonify({"message": "Deleted"}), 200
    return jsonify({"message": "Error"}), 404

@app.route('/profile/<username>')
def get_public_profile(username):
    user = User.query.filter_by(username=username).first()
    if not user: return jsonify({"message": "Not found"}), 404
    images = Image.query.filter_by(user_id=user.id).all()
    image_list = [{"id": i.id, "title": i.title, "filename": i.filename} for i in images]
    return jsonify({"username": user.username, "images": image_list, "profile_pic": user.profile_pic}), 200

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)