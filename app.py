from datetime import datetime
from flask import Flask, render_template, request, redirect
from models.animal import db, Animal
import os

from models.health_record import HealthRecord

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///farm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

@app.before_request
def create_tables():
    db.create_all()

@app.route("/add-animal", methods=["GET", "POST"])
def add_animal():
    if request.method == "POST":
        new_animal = Animal(
            tag_number=request.form["tag_number"],
            species=request.form["species"],
            breed=request.form["breed"],
            sex=request.form["sex"],
            status=request.form["status"]
        )
        db.session.add(new_animal)
        db.session.commit()
        return redirect("/add-animal")
    return render_template("animal_form.html")

@app.route("/animals")
def view_animals():
    animals = Animal.query.all()
    return render_template("animal_list.html",animals=animals)

@app.route("/animals/<int:animal_id>/edit",methods=["GET","POST"])
def edit_animal(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if request.method == "POST":
        animal.tag_number = request.form["tag_number"]
        animal.species = request.form["species"]
        animal.breed = request.form["breed"]
        animal.sex = request.form["sex"]
        animal.status = request.form["status"]
        db.session.commit()
        return redirect("/animals")
    return render_template("edit_animal.html",animal=animal)

@app.route("/animals/<int:animal_id>/delete")
def delete_animal(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    db.session.delete(animal)
    db.session.commit()
    return redirect("/animals")


@app.route("/dashboard")
def dashboard():
    animals = Animal.query.all()
    total = len(animals)
    alive = len([a for a in animals if a.status == "Alive"])
    sold = len([a for a in animals if a.status == "Sold"])
    deceased = len([a for a in animals if a.status =="Deceased"])

    labels = ["Alive","Sold","Deceased"]
    values = [alive,sold,deceased]
    return render_template("dashboard.html",total=total,alive=alive,sold=sold,deceased=deceased,
                           labels=labels,values=values)

@app.route("/animals/<int:animal_id>/health", methods=["GET", "POST"])
def animal_health(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if request.method == "POST":
        date_str = request.form["date"]
        date_obj = datetime.strptime(date_str,"%Y-%m-%d").date()
        record = HealthRecord(
            animal_id=animal.id,
            date=date_obj,
            treatment=request.form["treatment"],
            notes=request.form["notes"]
        )
        db.session.add(record)
        db.session.commit()
        return redirect(f"/animals/{animal.id}/health")
    return render_template("animal_health.html", animal=animal)


@app.route("/")
@app.route("/login")
def login():
    return render_template("login_form.html")

if __name__ == "__main__":
    print(Animal.__tablename__)
    app.run(host='0.0.0.0', port=5000,debug=True)