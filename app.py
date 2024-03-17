from flask import Flask, render_template, redirect, url_for, request, flash, g, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy.exc import IntegrityError
import qrcode
from io import BytesIO
import base64
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

@app.route("/")
def home():
    return render_template('home.html')

@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        try:
            db.session.add(user)
            db.session.commit()
            flash('Your account has been created! You are now able to log in', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('An account with this email address already exists. Please use a different email address.', 'danger')
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            flash('You have been logged in!', 'success')
            return redirect(url_for('appointment_booking'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)

class Doctor:
    def __init__(self, name, speciality, availability):
        self.name = name
        self.speciality = speciality
        self.availability = availability

doctors = [
    Doctor("Dr. Smith", "Cardiologist", "Monday, Wednesday, Friday"),
    Doctor("Dr. Johnson", "Dermatologist", "Tuesday, Thursday")
]

DATABASE = 'appointments.db'


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor = db.Column(db.String(100), nullable=False)
    patient = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(100), nullable=False)
    time = db.Column(db.String(100), nullable=False)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/index', methods=['GET', 'POST'])
def appointment_booking():
    if request.method == 'POST':
        doctor_name = request.form['doctor']
        patient_name = request.form['patient']
        date = request.form['date']
        time = request.form['time']
        message, qr_code_data = book_appointment(doctor_name, patient_name, date, time)
        return render_template('index.html', doctors=doctors, message=message, qr_code_data=qr_code_data)
    return render_template('index.html', doctors=doctors)

def book_appointment(doctor_name, patient_name, date, time):
    doctor = next((doc for doc in doctors if doc.name == doctor_name), None)
    if doctor:
        appointment_date = datetime.strptime(date, "%Y-%m-%d").date()
        with get_db() as conn:
            c = conn.cursor()
            existing_appointments = c.execute('''SELECT * FROM appointments 
                                                 WHERE doctor=? AND date=? AND time=?''', 
                                                 (doctor_name, date, time)).fetchall()
            if existing_appointments:
                return "Appointment slot already booked. Available timings for this day.", None
            else:
                c.execute('''INSERT INTO appointments (doctor, patient, date, time) 
                             VALUES (?, ?, ?, ?)''', (doctor_name, patient_name, date, time))
                conn.commit()
                qr_code_data = generate_qr_code(patient_name, date, time)
                return "Appointment booked successfully!", qr_code_data
    else:
        return "Doctor not found.", None

def generate_qr_code(patient_name, date, time):
    data = f"Patient: {patient_name}\nDate: {date}\nTime: {time}"
    qr = qrcode.make(data)
    qr_bytes = BytesIO()
    qr.save(qr_bytes)
    qr_bytes.seek(0)
    qr_b64 = base64.b64encode(qr_bytes.read()).decode('utf-8')
    return qr_b64

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create all database tables
    app.run(debug=True)
