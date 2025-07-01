from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from models.animal import Animal,db    
# db = SQLAlchemy()

class HealthRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animal.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    treatment = db.Column(db.String(100))
    notes = db.Column(db.Text)

    animal = db.relationship(Animal, backref='health_records')
