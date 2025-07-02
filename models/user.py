from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import os
from datetime import datetime, timedelta

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='staff')  # 'admin', 'staff', etc.

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_token'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')

    @staticmethod
    def generate_token(user, expires_in_minutes=30):
        raw_token = os.urandom(32).hex()
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        db.session.add(reset_token)
        db.session.commit()
        # Return the token in a URL-safe way (hex string is already safe)
        return raw_token

    @staticmethod
    def verify_token(raw_token):
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token = PasswordResetToken.query.filter_by(token_hash=token_hash, used=False).first()
        if token and token.expires_at > datetime.utcnow():
            return token
        return None

    def mark_used(self):
        self.used = True
        db.session.commit()