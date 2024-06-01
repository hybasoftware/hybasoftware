from datetime import datetime
import random

from flask import Flask, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    employee_id = db.Column(db.String(50), unique=True, nullable=False)
    hours_worked = db.Column(db.Float, default=0.0)
    benefits = db.Column(db.String(150))
    equity_allocation = db.Column(db.Float, default=0.0)


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Performance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    metrics = db.Column(db.JSON)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Payroll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    hours_worked = db.Column(db.Float, nullable=False)
    payment_amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class BoardMeeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    details = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    minutes = db.Column(db.Text)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)


@app.route('/employee/create', methods=['GET', 'POST'])
@login_required
def create_employee():
    if request.method == 'POST':
        name = request.form['name']
        if not name:
            flash('Name is required!')
            return redirect(url_for('create_employee'))
        employee_id = generate_unique_employee_id()
        new_employee = Employee(name=name, employee_id=employee_id)
        db.session.add(new_employee)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('create_employee.html')


@app.route('/employee/<int:id>', methods=['GET'])
@login_required
def view_employee(id):
    employee = Employee.query.get_or_404(id)
    return render_template('view_employee.html', employee=employee)


@app.route('/employee/<int:id>/log_time', methods=['POST'])
@login_required
def log_time(id):
    employee = Employee.query.get_or_404(id)
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    if not start_time or not end_time:
        flash('Start time and end time are required!')
        return redirect(url_for('view_employee', id=id))
    try:
        start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        hours_worked = calculate_hours_worked(start_time, end_time)
        employee.hours_worked += hours_worked
        db.session.commit()
        return redirect(url_for('view_employee', id=id))
    except ValueError:
        flash('Invalid time format!')
        return redirect(url_for('view_employee', id=id))


@app.route('/feedback/create', methods=['POST'])
@login_required
def create_feedback():
    employee_id = request.form['employee_id']
    content = request.form['content']
    if not employee_id or not content:
        flash('Employee ID and content are required!')
        return redirect(url_for('dashboard'))
    feedback = Feedback(employee_id=employee_id, content=content)
    db.session.add(feedback)
    db.session.commit()
    link_feedback_to_performance(employee_id, content)
    return redirect(url_for('dashboard'))


def link_feedback_to_performance(employee_id, feedback_content):
    performance = Performance.query.filter_by(employee_id=employee_id).first()
    if performance:
        if 'feedback' not in performance.metrics:
            performance.metrics['feedback'] = []
        performance.metrics['feedback'].append(feedback_content)
        db.session.commit()


@app.route('/payroll/process', methods=['POST'])
@login_required
def process_payroll():
    employee_id = request.form['employee_id']
    hours_worked = request.form['hours_worked']
    try:
        hours_worked = float(hours_worked)
        payroll_details = fetch_payroll_details(employee_id)
        payment_amount = calculate_payment(payroll_details, hours_worked)
        payroll = Payroll(
            employee_id=employee_id,
            hours_worked=hours_worked,
            payment_amount=payment_amount
        )
        db.session.add(payroll)
        db.session.commit()
        return redirect(url_for('dashboard'))
    except ValueError:
        flash('Invalid hours worked!')
        return redirect(url_for('dashboard'))


@app.route('/board/meeting/create', methods=['GET', 'POST'])
@login_required
def create_board_meeting():
    if request.method == 'POST':
        title = request.form['title']
        details = request.form['details']
        date = request.form['date']
        if not title or not details or not date:
            flash('All fields are required!')
            return redirect(url_for('create_board_meeting'))
        try:
            date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
            new_meeting = BoardMeeting(title=title, details=details, date=date)
            db.session.add(new_meeting)
            db.session.commit()
            notify_participants(details)
            return redirect(url_for('dashboard'))
        except ValueError:
            flash('Invalid date format!')
            return redirect(url_for('create_board_meeting'))
    return render_template('create_board_meeting.html')


@app.route('/board/meeting/<int:id>', methods=['GET'])
@login_required
def view_board_meeting(id):
    meeting = BoardMeeting.query.get_or_404(id)
    return render_template('view_board_meeting.html', meeting=meeting)


@app.route('/board/meeting/<int:id>/record_minutes', methods=['POST'])
@login_required
def record_meeting_minutes(id):
    meeting = BoardMeeting.query.get_or_404(id)
    minutes = request.form['minutes']
    if not minutes:
        flash('Minutes are required!')
        return redirect(url_for('view_board_meeting', id=id))
    meeting.minutes = minutes
    db.session.commit()
    link_minutes_to_board_records(id, minutes)
    return redirect(url_for('view_board_meeting', id=id))


def notify_participants(details):
    # Logic to send notifications to participants
    pass


def link_minutes_to_board_records(meeting_id, minutes):
    meeting = BoardMeeting.query.get_or_404(meeting_id)
    meeting.minutes = minutes
    db.session.commit()


def generate_unique_employee_id():
    # Logic to generate a unique employee ID
    return "EMP" + str(random.randint(1000, 9999))


def calculate_hours_worked(start_time, end_time):
    # Logic to calculate hours worked
    return (end_time - start_time).total_seconds() / 3600


def fetch_payroll_details(employee_id):
    # Logic to fetch payroll details for an employee
    return {'hourly_rate': 20.0}


def calculate_payment(payroll_details, hours_worked):
    return payroll_details['hourly_rate'] * hours_worked


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
