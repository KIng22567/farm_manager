from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Animal(db.Model):
    __tablename__ = 'animal'
    id = db.Column(db.Integer, primary_key=True)
    tag_number = db.Column(db.String(50), unique=True, nullable=False)
    species = db.Column(db.String(50))
    breed = db.Column(db.String(50))
    sex = db.Column(db.String(10))
    date_of_birth = db.Column(db.Date)
    status = db.Column(db.String(20))