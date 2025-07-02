import random
import string
from datetime import datetime, timedelta
from models.animal import Animal, db
from models.user import User
from models.settings import AppSettings
from models.health_record import HealthRecord

def random_string(length):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))

def seed_animals(n=1000):
    species_list = ["Cow", "Goat", "Sheep", "Pig", "Chicken", "Horse", "Donkey"]
    breeds = {
        "Cow": ["Holstein", "Jersey", "Angus", "Hereford"],
        "Goat": ["Boer", "Nubian", "Saanen"],
        "Sheep": ["Merino", "Dorper", "Suffolk"],
        "Pig": ["Yorkshire", "Berkshire", "Duroc"],
        "Chicken": ["Leghorn", "Rhode Island Red", "Plymouth Rock"],
        "Horse": ["Arabian", "Quarter Horse", "Thoroughbred"],
        "Donkey": ["Standard", "Miniature"]
    }
    sexes = ["Male", "Female"]
    statuses = ["Alive", "Sold", "Deceased"]
    animals = []
    used_tags = set(a.tag_number for a in Animal.query.all())
    while len(animals) < n:
        species = random.choice(species_list)
        breed = random.choice(breeds[species])
        tag_number = f"{species[:2].upper()}{random.randint(10000,99999)}"
        if tag_number in used_tags:
            continue
        used_tags.add(tag_number)
        sex = random.choice(sexes)
        dob = random_date(datetime(2015,1,1), datetime(2023,12,31))
        status = random.choices(statuses, weights=[0.8,0.15,0.05])[0]
        animal = Animal(
            tag_number=tag_number,
            species=species,
            breed=breed,
            sex=sex,
            date_of_birth=dob,
            status=status
        )
        animals.append(animal)
    db.session.bulk_save_objects(animals)
    db.session.commit()
    print(f"Seeded {n} animals.")

def seed_users():
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@example.com", role="admin")
        admin.set_password("pass123")
        db.session.add(admin)
    for i in range(10):
        username = f"user{i}"
        email = f"user{i}@example.com"
        if not User.query.filter_by(username=username).first():
            user = User(username=username, email=email, role="staff")
            user.set_password("password123")
            db.session.add(user)
    db.session.commit()
    print("Seeded users.")

def seed_settings():
    if not AppSettings.query.first():
        db.session.add(AppSettings(farm_name="Test Farm"))
        db.session.commit()
        print("Seeded settings.")

def seed_health_records():
    animals = Animal.query.all()
    treatments = ["Vaccination", "Deworming", "Checkup", "Surgery", "Antibiotics"]
    notes = ["Healthy", "Minor injury", "Recovered well", "Needs follow-up", "No issues"]
    records = []
    for animal in animals:
        for _ in range(random.randint(1, 3)):
            date = random_date(datetime(2021,1,1), datetime(2024,6,1))
            record = HealthRecord(
                animal_id=animal.id,
                date=date,
                treatment=random.choice(treatments),
                notes=random.choice(notes)
            )
            records.append(record)
    db.session.bulk_save_objects(records)
    db.session.commit()
    print(f"Seeded health records for {len(animals)} animals.")

if __name__ == "__main__":
    from app import app
    with app.app_context():
        seed_settings()
        seed_users()
        seed_animals(1000)
        seed_health_records()
