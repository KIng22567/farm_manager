from flask_sqlalchemy import SQLAlchemy
from models.user import db

class AppSettings(db.Model):
    __tablename__ = "app_settings"
    id = db.Column(db.Integer, primary_key=True)
    farm_name = db.Column(db.String(128), default="My Farm")
