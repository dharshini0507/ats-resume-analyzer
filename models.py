from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AnalysisHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resume_text = db.Column(db.Text, nullable=False)
    jd_text = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer)
    hiring_probability = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        try:
            db.create_all()
            print("Database initialized successfully.")
        except Exception as e:
            print(f"Database initialization failed: {e}")
            print("Check your DATABASE_URL in .env")
