# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
from flask_migrate import Migrate
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from flask import Flask, render_template, request, redirect, url_for, flash, make_response
import csv
from io import StringIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'my_super_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///productivity_final.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email Configuration (এখানে আপনার তথ্য বসান)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'shibaziroymridul2@gmail.com'     # <-- আপনার জিমেইল দিন
app.config['MAIL_PASSWORD'] = 'yvbmkjzqobbcwmuh'   # <-- আপনার ১৬ অক্ষরের App Password দিন
app.config['MAIL_DEFAULT_SENDER'] = 'YOUR_EMAIL@gmail.com' # <-- আপনার জিমেইল দিন

db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

# টোকেন জেনারেটর (সিকিউর লিংক তৈরির জন্য)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False) # ইমেইল ভেরিফিকেশন স্ট্যাটাস

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    time_info = db.Column(db.String(100), nullable=True)
    completed = db.Column(db.Boolean, default=False)
    is_important = db.Column(db.Boolean, default=False)
    is_urgent = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    milestones = db.relationship('Milestone', backref='goal', lazy=True, cascade="all, delete-orphan")

    @property
    def progress(self):
        total = len(self.milestones)
        if total == 0: return 0
        completed = len([m for m in self.milestones if m.completed])
        return int((completed / total) * 100)

class Milestone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.id'), nullable=False)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Journal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- নতুন রেজিস্ট্রেশন এবং ইমেইল ভেরিফিকেশন লজিক ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash('This email is already registered. Please login.', 'warning')
            return redirect(url_for('register'))
            
        new_user = User(name=name, email=email, password=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(new_user)
        db.session.commit()

        # ভেরিফিকেশন লিংক তৈরি করে ইমেইলে পাঠানো
        token = s.dumps(email, salt='email-confirm')
        confirm_url = url_for('confirm_email', token=token, _external=True)
        html_body = f"""
        <h2>Welcome to Align, {name}!</h2>
        <p>Please click the link below to verify your email address and activate your account:</p>
        <a href="{confirm_url}" style="padding: 10px 20px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">Verify My Account</a>
        <p>If the button doesn't work, copy and paste this link: {confirm_url}</p>
        """
        
        try:
            msg = Message('Verify your Align Account', recipients=[email])
            msg.html = html_body
            mail.send(msg)
            flash('Registration successful! Please check your email to verify your account.', 'success')
        except Exception as e:
            print(e)
            flash('Registered, but failed to send verification email. Please try again later.', 'danger')
            
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600) # ১ ঘণ্টার মধ্যে লিংক কাজ করবে
    except SignatureExpired:
        flash('The verification link has expired. Please register again.', 'danger')
        return redirect(url_for('login'))
    except Exception:
        flash('Invalid verification link.', 'danger')
        return redirect(url_for('login'))
        
    user = User.query.filter_by(email=email).first()
    if user.is_verified:
        flash('Account already verified. Please login.', 'success')
    else:
        user.is_verified = True
        db.session.commit()
        flash('Your account has been verified! You can now login.', 'success')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            # ইউজার যদি ভেরিফাইড না থাকে, তবে অটোমেটিক নতুন লিংক চলে যাবে
            if not user.is_verified:
                token = s.dumps(email, salt='email-confirm')
                confirm_url = url_for('confirm_email', token=token, _external=True)
                html_body = f"""
                <h2>Activate your Align Account</h2>
                <p>It looks like you tried to log in but your account isn't verified yet.</p>
                <p>Please click the link below to verify your email address:</p>
                <a href="{confirm_url}" style="padding: 10px 20px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">Verify My Account</a>
                <p>If the button doesn't work, copy and paste this link: {confirm_url}</p>
                """
                try:
                    msg = Message('Verify your Align Account (New Link)', recipients=[email])
                    msg.html = html_body
                    mail.send(msg)
                    flash('Your account is not verified yet. A FRESH verification link has been sent to your inbox right now. Please check your email.', 'warning')
                except Exception as e:
                    print(e)
                    flash('Account not verified, and failed to send a new link. Please try again later.', 'danger')
                
                return redirect(url_for('login'))
                
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- মূল রুট (ল্যান্ডিং পেজ এবং ড্যাশবোর্ড লজিক) ---
@app.route('/')
def home():
    if not current_user.is_authenticated:
        return render_template('landing.html')
        
    important_tasks = Task.query.filter_by(user_id=current_user.id, is_important=True).all()
    all_goals = Goal.query.filter_by(user_id=current_user.id).all()
    physical_habits = Habit.query.filter_by(user_id=current_user.id, category='Physical').all()
    mental_habits = Habit.query.filter_by(user_id=current_user.id, category='Mental').all()
    spiritual_habits = Habit.query.filter_by(user_id=current_user.id, category='Spiritual').all()
    social_habits = Habit.query.filter_by(user_id=current_user.id, category='Social').all()
    habits = {'Physical': physical_habits, 'Mental': mental_habits, 'Spiritual': spiritual_habits, 'Social': social_habits}
    habit_counts = [len(physical_habits), len(mental_habits), len(spiritual_habits), len(social_habits)]
    today_date = datetime.now().strftime("%B %d, %Y")
    
    return render_template('index.html', tasks=important_tasks, habits=habits, goals=all_goals, today_date=today_date, habit_counts=json.dumps(habit_counts))

# --- অন্যান্য মডিউলের ফাংশনস ---
@app.route('/add', methods=['POST'])
@login_required
def add():
    title = request.form.get('title')
    time_info_raw = request.form.get('time_info') 
    duration = request.form.get('duration')
    is_important = True if request.form.get('important') else False
    is_urgent = True if request.form.get('urgent') else False
    
    formatted_time = ""
    if time_info_raw:
        try:
            parsed_time = datetime.strptime(time_info_raw, '%Y-%m-%dT%H:%M')
            formatted_time = parsed_time.strftime('%b %d, %I:%M %p')
        except ValueError:
            formatted_time = time_info_raw
            
    final_time_info = formatted_time
    if duration:
        if final_time_info: final_time_info += f" • {duration}"
        else: final_time_info = duration

    if title:
        db.session.add(Task(title=title, time_info=final_time_info, is_important=is_important, is_urgent=is_urgent, user_id=current_user.id))
        db.session.commit()
    return redirect(request.referrer)

@app.route('/complete/<int:task_id>')
@login_required
def complete(task_id):
    task = Task.query.get(task_id)
    if task and task.user_id == current_user.id:
        task.completed = not task.completed
        db.session.commit()
    return redirect(request.referrer)

@app.route('/delete/<int:task_id>')
@login_required
def delete(task_id):
    task = Task.query.get(task_id)
    if task and task.user_id == current_user.id:
        db.session.delete(task)
        db.session.commit()
    return redirect(request.referrer)

@app.route('/goals')
@login_required
def goals_page():
    return render_template('goals.html', goals=Goal.query.filter_by(user_id=current_user.id).all())

@app.route('/add_goal', methods=['POST'])
@login_required
def add_goal():
    title = request.form.get('title')
    if title:
        db.session.add(Goal(title=title, user_id=current_user.id))
        db.session.commit()
    return redirect(url_for('goals_page'))

@app.route('/delete_goal/<int:goal_id>')
@login_required
def delete_goal(goal_id):
    goal = Goal.query.get(goal_id)
    if goal and goal.user_id == current_user.id:
        db.session.delete(goal)
        db.session.commit()
    return redirect(url_for('goals_page'))

@app.route('/add_milestone/<int:goal_id>', methods=['POST'])
@login_required
def add_milestone(goal_id):
    title = request.form.get('title')
    goal = Goal.query.get(goal_id)
    if title and goal and goal.user_id == current_user.id:
        db.session.add(Milestone(title=title, goal_id=goal_id))
        db.session.commit()
    return redirect(url_for('goals_page'))

@app.route('/complete_milestone/<int:milestone_id>')
@login_required
def complete_milestone(milestone_id):
    milestone = Milestone.query.get(milestone_id)
    if milestone and milestone.goal.user_id == current_user.id:
        milestone.completed = not milestone.completed
        db.session.commit()
    return redirect(request.referrer)

@app.route('/delete_milestone/<int:milestone_id>')
@login_required
def delete_milestone(milestone_id):
    milestone = Milestone.query.get(milestone_id)
    if milestone and milestone.goal.user_id == current_user.id:
        db.session.delete(milestone)
        db.session.commit()
    return redirect(request.referrer)

@app.route('/add_habit', methods=['POST'])
@login_required
def add_habit():
    title = request.form.get('title')
    category = request.form.get('category')
    if title and category:
        db.session.add(Habit(title=title, category=category, user_id=current_user.id))
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/complete_habit/<int:habit_id>')
@login_required
def complete_habit(habit_id):
    habit = Habit.query.get(habit_id)
    if habit and habit.user_id == current_user.id:
        habit.completed = not habit.completed
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/delete_habit/<int:habit_id>')
@login_required
def delete_habit(habit_id):
    habit = Habit.query.get(habit_id)
    if habit and habit.user_id == current_user.id:
        db.session.delete(habit)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/planner')
@login_required
def planner_page():
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    q1 = [t for t in all_tasks if t.is_important and t.is_urgent]
    q2 = [t for t in all_tasks if t.is_important and not t.is_urgent]
    q3 = [t for t in all_tasks if not t.is_important and t.is_urgent]
    q4 = [t for t in all_tasks if not t.is_important and not t.is_urgent]
    return render_template('planner.html', q1=q1, q2=q2, q3=q3, q4=q4)

@app.route('/journal')
@login_required
def journal_page():
    journals = Journal.query.filter_by(user_id=current_user.id).order_by(Journal.id.desc()).all()
    
    # সিম্পল streak ক্যালকুলেশন (শেষ ৭ দিনের মধ্যে কয়দিন লিখেছেন)
    streak = 0
    # এখানে জার্নালের তারিখ থেকে লজিক বসানো যাবে, আপাতত আমরা সহজ একটি ক্যালকুলেশন দিচ্ছি
    if journals:
        streak = 1 # লজিকটি আরও অ্যাডভান্সড করা সম্ভব
        
    return render_template('journal.html', journals=journals, streak=streak)

@app.route('/add_journal', methods=['POST'])
@login_required
def add_journal():
    content = request.form.get('content')
    if content:
        db.session.add(Journal(content=content, date=datetime.now().strftime("%B %d, %Y - %I:%M %p"), user_id=current_user.id))
        db.session.commit()
    return redirect(url_for('journal_page'))

@app.route('/delete_journal/<int:journal_id>')
@login_required
def delete_journal(journal_id):
    entry = Journal.query.get(journal_id)
    if entry and entry.user_id == current_user.id:
        db.session.delete(entry)
        db.session.commit()
    return redirect(url_for('journal_page'))
# --- পাসওয়ার্ড রিসেট লজিক ---
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = s.dumps(email, salt='password-reset')
            reset_url = url_for('reset_token', token=token, _external=True)
            html_body = f"""
            <h2>Align - Password Reset</h2>
            <p>To reset your password, visit the following link:</p>
            <a href="{reset_url}" style="padding: 10px 20px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">Reset Password</a>
            <p>If you did not make this request, please ignore this email. The link will expire in 30 minutes.</p>
            """
            try:
                msg = Message('Password Reset Request - Align', recipients=[email])
                msg.html = html_body
                mail.send(msg)
            except Exception as e:
                print(e)
                
        flash('If that email exists in our system, an email has been sent with instructions to reset your password.', 'success')
        return redirect(url_for('login'))
        
    return render_template('reset_request.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    try:
        email = s.loads(token, salt='password-reset', max_age=1800) # লিংক ৩০ মিনিট কাজ করবে
    except SignatureExpired:
        flash('The password reset link has expired. Please try again.', 'danger')
        return redirect(url_for('reset_request'))
    except Exception:
        flash('Invalid password reset link.', 'danger')
        return redirect(url_for('reset_request'))
        
    user = User.query.filter_by(email=email).first()
    
    if request.method == 'POST':
        password = request.form.get('password')
        user.password = generate_password_hash(password, method='pbkdf2:sha256')
        db.session.commit()
        flash('Your password has been updated! You can now log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('reset_token.html')
# --- Drag and Drop Logic ---
@app.route('/update_task_quadrant/<int:task_id>', methods=['POST'])
@login_required
def update_task_quadrant(task_id):
    task = Task.query.get(task_id)
    if task and task.user_id == current_user.id:
        data = request.get_json()
        quadrant = data.get('quadrant')

        # ম্যাট্রিক্সের বক্স অনুযায়ী স্ট্যাটাস আপডেট করা হচ্ছে
        if quadrant == 'q1':
            task.is_important = True
            task.is_urgent = True
        elif quadrant == 'q2':
            task.is_important = True
            task.is_urgent = False
        elif quadrant == 'q3':
            task.is_important = False
            task.is_urgent = True
        elif quadrant == 'q4':
            task.is_important = False
            task.is_urgent = False

        db.session.commit()
        return {"status": "success"}
    return {"status": "error"}, 400
# --- Data Export Logic (CSV) ---
@app.route('/export')
@login_required
def export_data():
    si = StringIO()
    cw = csv.writer(si)
    
    # ফাইলের হেডিং (কলামের নাম)
    cw.writerow(['Category', 'Title / Content', 'Status', 'Date / Time'])
    
    # ইউজারের সব টাস্ক এক্সপোর্ট করা
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    for t in tasks:
        status = 'Completed' if t.completed else 'Pending'
        cw.writerow(['Task', t.title, status, t.time_info or 'N/A'])
        
    # ইউজারের সব জার্নাল এক্সপোর্ট করা
    journals = Journal.query.filter_by(user_id=current_user.id).order_by(Journal.id.desc()).all()
    for j in journals:
        cw.writerow(['Journal', j.content, 'N/A', j.date])
        
    # রেসপন্স হিসেবে CSV ফাইলটি ব্রাউজারে পাঠানো
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=Align_Data_Export.csv"
    output.headers["Content-type"] = "text/csv"
    return output
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
if __name__ == '__main__':
    app.run(debug=True)