from datetime import datetime
from flask import Flask, g, render_template, request, redirect, session, url_for, flash, get_flashed_messages
from models.animal import db, Animal
from models.user import User, PasswordResetToken
from models.settings import AppSettings
import os
import smtplib
from email.mime.text import MIMEText

from models.health_record import HealthRecord
from config import Config
from datetime import datetime, timedelta
import hashlib
import re
from flask_migrate import Migrate
from animal_tree_view import *

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)

@app.before_request
def create_tables():
    # Ensure settings row and admin user exist
    try:
        # Settings row
        if not AppSettings.query.first():
            default_settings = AppSettings(farm_name="My Farm")
            db.session.add(default_settings)
            db.session.commit()
        # Admin user
        admin_user = User.query.filter_by(username="admin").first()
        if not admin_user:
            admin = User(username="admin", email="admin@example.com", role="admin")
            admin.set_password("pass123")
            db.session.add(admin)
            db.session.commit()
            print("[DEBUG] Admin user created with username 'admin' and password 'pass123'. Hash:", admin.password_hash)
        else:
            print(f"[DEBUG] Admin user already exists. Username: {admin_user.username}, Hash: {admin_user.password_hash}")
    except Exception as e:
        print(f"[DEBUG] Exception in create_tables: {e}")
        # If table doesn't exist yet (e.g., during migration), ignore error
        pass

@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.current_user = db.session.get(User,user_id) if user_id else None


def get_settings():
    try:
        return AppSettings.query.first()
    except Exception:
        # Table does not exist yet
        return None


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
    return render_template("animal_form.html", settings=get_settings())

@app.route("/animals")
def view_animals():
    animals = Animal.query.all()
    return render_template("animal_list.html", animals=animals, settings=get_settings())

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
    return render_template("edit_animal.html", animal=animal, settings=get_settings())

@app.route("/animals/<int:animal_id>/delete")
def delete_animal(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    db.session.delete(animal)
    db.session.commit()
    return redirect("/animals")

@app.route("/")
@app.route("/dashboard")
def dashboard():
    if not g.current_user:
        return redirect(url_for("login"))
    animals = Animal.query.all()
    total = len(animals)
    alive = len([a for a in animals if a.status == "Alive"])
    sold = len([a for a in animals if a.status == "Sold"])
    deceased = len([a for a in animals if a.status =="Deceased"])

    labels = ["Alive","Sold","Deceased"]
    values = [alive,sold,deceased]
    return render_template("dashboard.html", total=total, alive=alive, sold=sold, deceased=deceased,
                           labels=labels, values=values, settings=get_settings())

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
    return render_template("animal_health.html", animal=animal, settings=get_settings())

# Simple in-memory rate limit (per IP/email)
reset_request_times = {}

def strong_password(password):
    # At least 8 chars, 1 upper, 1 lower, 1 digit, 1 special char
    return (
        len(password) >= 8 and
        re.search(r'[A-Z]', password) and
        re.search(r'[a-z]', password) and
        re.search(r'\d', password) and
        re.search(r'[^A-Za-z0-9]', password)
    )

def log_event(event, user=None, extra=None):
    # Simple audit log to file
    with open("password_reset_audit.log", "a") as f:
        f.write(f"{datetime.utcnow().isoformat()} | {event} | user={getattr(user, 'id', None)} | {extra}\n")

def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = "no-reply@farmmanager.local"
    msg["To"] = to_email
    SMTP_SERVER = app.config["SMTP_SERVER"]
    SMTP_PORT = app.config["SMTP_PORT"]
    SMTP_USERNAME = app.config["SMTP_USERNAME"]
    SMTP_PASSWORD = app.config["SMTP_PASSWORD"]
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(msg["From"], [msg["To"]], msg.as_string())

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        identifier = request.form["identifier"]
        # Rate limit: 1 request per 5 min per identifier (email or IP)
        key = identifier.lower()
        now = datetime.utcnow()
        last_time = reset_request_times.get(key)
        if last_time and (now - last_time).total_seconds() < 300:
            flash("If an account with that email exists, you'll receive a reset link soon.", "info")
            return redirect(url_for("login"))
        reset_request_times[key] = now

        user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
        if user and user.email:
            # Generate token and send email
            raw_token = PasswordResetToken.generate_token(user)
            reset_url = url_for("reset_password", token=raw_token, _external=True, _scheme="http")
            subject = "Farm Manager Password Reset"
            body = f"To reset your password, click the link below:\n\n{reset_url}\n\nThis link will expire in 30 minutes."
            try:
                send_email(user.email, subject, body)
                log_event("reset_requested", user)
            except Exception as e:
                log_event("reset_email_failed", user, str(e))
        # Always show generic message
        flash("If an account with that email exists, you'll receive a reset link soon.", "info")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    reset_token = PasswordResetToken.verify_token(token)
    if not reset_token:
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for("login"))
    user = reset_token.user
    if request.method == "POST":
        password = request.form["password"]
        if not strong_password(password):
            flash("Password must be at least 8 characters and include upper, lower, digit, and special character.", "danger")
            return render_template("reset_password.html")
        user.set_password(password)
        db.session.commit()
        reset_token.mark_used()
        # Invalidate all sessions (simple: clear session)
        session.clear()
        # Notify user
        try:
            send_email(user.email, "Your Farm Manager password was changed", "If you did not do this, contact support immediately.")
        except Exception as e:
            log_event("notify_email_failed", user, str(e))
        log_event("reset_completed", user)
        flash("Password reset successful. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if not g.current_user or g.current_user.role != "admin":
        flash("Only admin can add new users.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"].strip()
        role = request.form["role"].strip()
        try:
            if User.query.filter_by(username=username).first():
                flash("Username already exists.", "danger")
                return redirect(url_for("register"))
            if User.query.filter_by(email=email).first():
                flash("Email already exists.", "danger")
                return redirect(url_for("register"))
            user = User(username=username, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("User created successfully.", "success")
            return redirect(url_for("register"))
        except Exception as e:
            flash("User table does not exist. Please run migrations first.", "danger")
            return render_template("register.html", settings=get_settings())
    return render_template("register.html", settings=get_settings())

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not g.current_user or g.current_user.role != "admin":
        flash("Only admin can change settings.", "danger")
        return redirect(url_for("dashboard"))
    settings = AppSettings.query.first()
    if request.method == "POST":
        farm_name = request.form["farm_name"]
        settings.farm_name = farm_name
        db.session.commit()
        flash("Settings updated.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", settings=settings)

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method =="POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        try:
            user = User.query.filter_by(username=username).first()
            if user:
                print(f"[DEBUG] Login attempt for user '{username}'. Stored hash: {user.password_hash}")
                if user.check_password(password):
                    print("[DEBUG] Password check passed.")
                    session["user_id"] = user.id
                    session["user_role"] = user.role
                    flash("Logged in successfully!","success")
                    return redirect(url_for("dashboard"))
                else:
                    print("[DEBUG] Password check failed.")
            else:
                print(f"[DEBUG] No user found with username '{username}'")
            flash("Invalid username or password!","danger")
        except Exception as e:
            print(f"[DEBUG] Exception in login: {e}")
            flash("User table does not exist. Please run migrations first.", "danger")
            return render_template("login_form.html", settings=get_settings())

    return render_template("login_form.html", settings=get_settings())

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.","info")
    return redirect(url_for("login"))

@app.context_processor
def inject_globals():
    return dict(settings=get_settings(), get_flashed_messages=get_flashed_messages)

@app.route("/users")
def users():
    if not g.current_user or g.current_user.role != "admin":
        flash("Only admin can view users.", "danger")
        return redirect(url_for("dashboard"))
    users = User.query.all()
    return render_template("user_list.html", users=users)

@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
def edit_user(user_id):
    if not g.current_user or g.current_user.role != "admin":
        flash("Only admin can edit users.", "danger")
        return redirect(url_for("dashboard"))
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        new_username = request.form["username"].strip()
        new_email = request.form["email"].strip()
        new_role = request.form["role"].strip()
        password = request.form.get("password")
        if password is not None:
            password = password.strip()

        # Check for unique username (exclude current user)
        if User.query.filter(User.username == new_username, User.id != user.id).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("edit_user", user_id=user.id))
        # Check for unique email (exclude current user)
        if User.query.filter(User.email == new_email, User.id != user.id).first():
            flash("Email already exists.", "danger")
            return redirect(url_for("edit_user", user_id=user.id))

        user.username = new_username
        user.email = new_email
        user.role = new_role
        if password:
            user.set_password(password)
        db.session.commit()
        flash("User updated.", "success")
        return redirect(url_for("users"))
    return render_template("edit_user.html", user=user)

@app.route("/users/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    if not g.current_user or g.current_user.role != "admin":
        flash("Only admin can delete users.", "danger")
        return redirect(url_for("dashboard"))
    user = User.query.get_or_404(user_id)
    if user.username == "admin":
        flash("Cannot delete the main admin user.", "danger")
        return redirect(url_for("users"))
    db.session.delete(user)
    db.session.commit()
    flash("User deleted.", "info")
    return redirect(url_for("users"))

@app.route("/animal-tree")
def animal_tree():
    # Fetch all animals
    animals = Animal.query.all()
    # Build hierarchy: {species: {breed: [animal, ...]}}
    tree = {}
    for animal in animals:
        species = animal.species or "Unknown Species"
        breed = animal.breed or "Unknown Breed"
        tree.setdefault(species, {}).setdefault(breed, []).append(animal)
    # For search
    search = request.args.get("search", "")
    return render_template("animal_tree.html", tree=tree, search=search)

if __name__ == "__main__":
    # with app.app_context():
    #     db.create_all()  # Disabled for migration setup
    app.run(host='0.0.0.0', port=5000,debug=True)