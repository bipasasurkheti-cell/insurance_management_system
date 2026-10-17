import os
from datetime import datetime, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "replace-with-a-long-random-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///insurance.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="customer", nullable=False)
    customer_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    customer_policies = db.relationship("CustomerPolicy", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Policy(db.Model):
    __tablename__ = "policies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    policy_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    premium_amount = db.Column(db.Float, nullable=False, default=0.0)
    duration_months = db.Column(db.Integer, nullable=False, default=12)
    customer_policies = db.relationship("CustomerPolicy", back_populates="policy", cascade="all, delete-orphan")


class CustomerPolicy(db.Model):
    __tablename__ = "customer_policies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False)
    status = db.Column(db.String(30), default="pending_payment", nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="customer_policies")
    policy = db.relationship("Policy", back_populates="customer_policies")
    payments = db.relationship("Payment", back_populates="customer_policy", cascade="all, delete-orphan")
    claims = db.relationship("Claim", back_populates="customer_policy", cascade="all, delete-orphan")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    customer_policy_id = db.Column(db.Integer, db.ForeignKey("customer_policies.id"), nullable=False)
    reference = db.Column(db.String(80), unique=True, nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    method = db.Column(db.String(50), default="demo_card", nullable=False)
    status = db.Column(db.String(30), default="paid", nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    customer_policy = db.relationship("CustomerPolicy", back_populates="payments")

    @property
    def user(self):
        return self.customer_policy.user


class Claim(db.Model):
    __tablename__ = "claims"

    id = db.Column(db.Integer, primary_key=True)
    customer_policy_id = db.Column(db.Integer, db.ForeignKey("customer_policies.id"), nullable=False)
    claim_reference = db.Column(db.String(80), unique=True, nullable=False, index=True)
    claim_amount = db.Column(db.Float, nullable=False, default=0.0)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="under_review", nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    customer_policy = db.relationship("CustomerPolicy", back_populates="claims")

    @property
    def user(self):
        return self.customer_policy.user


class CustomerQuestion(db.Model):
    __tablename__ = "customer_questions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, default="", nullable=False)
    status = db.Column(db.String(30), default="open", nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref="questions")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            flash("Admin access required.")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)

    return wrapped


def seed_policies():
    if Policy.query.first():
        return

    default_policies = [
        {
            "name": "SafeDrive Auto",
            "category": "Auto",
            "description": "Roadside assistance, accident support and accident damage protection.",
            "policy_code": "SD-101",
            "premium_amount": 1200.0,
            "duration_months": 12,
        },
        {
            "name": "HealthPlus",
            "category": "Health",
            "description": "Hospital cover, outpatient benefits and wellness support for families.",
            "policy_code": "HP-240",
            "premium_amount": 1800.0,
            "duration_months": 12,
        },
        {
            "name": "HomeSecure",
            "category": "Home",
            "description": "Protection for your home structure, contents and emergency repairs.",
            "policy_code": "HS-380",
            "premium_amount": 2100.0,
            "duration_months": 12,
        },
    ]

    for item in default_policies:
        db.session.add(Policy(**item))

    db.session.commit()


def ensure_default_admin():
    if User.query.filter_by(role="admin").first():
        return

    admin = User(
        full_name="System Admin",
        username="bipasa",
        email="admin@insurecare.local",
        phone="0000000000",
        customer_id="CUST-ADMIN",
        role="admin",
    )
    admin.set_password("bipasa@1234")
    db.session.add(admin)
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_policies()
    ensure_default_admin()


@app.before_request
def ensure_database_ready():
    db.create_all()
    seed_policies()
    ensure_default_admin()


@app.route("/")
def index():
    return render_template("index.html", policies=Policy.query.order_by(Policy.id).all())


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin" if current_user.role == "admin" else "dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("admin" if user.role == "admin" else "dashboard"))

        flash("Invalid username or password.")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("admin" if current_user.role == "admin" else "dashboard"))

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not all([full_name, username, email, phone]):
            flash("Please complete all required fields.")
        elif len(password) < 12:
            flash("Password must be at least 12 characters long.")
        elif password != confirm_password:
            flash("Passwords do not match.")
        elif User.query.filter((User.username == username) | (User.email == email)).first():
            flash("A customer with that username or email already exists.")
        else:
            customer_id = f"CUST-{User.query.count() + 1:04d}"
            user = User(
                full_name=full_name,
                username=username,
                email=email,
                phone=phone,
                customer_id=customer_id,
                role="customer",
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Your account has been created successfully.")
            return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/dashboard")
@login_required
def dashboard():
    my_policies = CustomerPolicy.query.filter_by(user_id=current_user.id).order_by(CustomerPolicy.created_at.desc()).all()
    available_policies = Policy.query.order_by(Policy.id).all()
    applied_policy_ids = {enrollment.policy_id for enrollment in my_policies}
    payments = Payment.query.join(CustomerPolicy).filter(CustomerPolicy.user_id == current_user.id).order_by(Payment.created_at.desc()).all()
    claims = Claim.query.join(CustomerPolicy).filter(CustomerPolicy.user_id == current_user.id).order_by(Claim.created_at.desc()).all()
    questions = CustomerQuestion.query.filter_by(user_id=current_user.id).order_by(CustomerQuestion.created_at.desc()).all()
    return render_template("dashboard.html", my_policies=my_policies, available_policies=available_policies, applied_policy_ids=applied_policy_ids, payments=payments, claims=claims, questions=questions)


@app.route("/ask_question", methods=["GET", "POST"])
@login_required
def ask_question():
    if request.method == "POST":
        question = (request.form.get("question") or "").strip()
        if not question:
            flash("Please enter a question.")
            return redirect(url_for("dashboard"))

        db.session.add(CustomerQuestion(user_id=current_user.id, question=question))
        db.session.commit()
        flash("Your question was sent to the admin.")
        return redirect(url_for("dashboard"))

    return redirect(url_for("dashboard"))


@app.route("/admin")
@admin_required
def admin():
    users = User.query.filter_by(role="customer").order_by(User.created_at.desc()).all()
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    claims = Claim.query.order_by(Claim.created_at.desc()).all()
    policies = Policy.query.order_by(Policy.id).all()
    applications = CustomerPolicy.query.order_by(CustomerPolicy.created_at.desc()).all()
    questions = CustomerQuestion.query.order_by(CustomerQuestion.created_at.desc()).all()
    stats = {
        "customer_count": len(users),
        "policy_holders": CustomerPolicy.query.count(),
        "approved_policy_holders": CustomerPolicy.query.filter(CustomerPolicy.status.in_(["active", "approved"])).count(),
        "disapproved_policy_holders": CustomerPolicy.query.filter_by(status="rejected").count(),
        "waiting_policy_holders": CustomerPolicy.query.filter(CustomerPolicy.status.in_(["pending", "pending_payment"])).count(),
        "pending_applications": CustomerPolicy.query.filter_by(status="pending").count(),
        "open_questions": CustomerQuestion.query.filter_by(status="open").count(),
        "claims_to_review": Claim.query.filter_by(status="under_review").count(),
        "collected_premiums": sum(payment.amount for payment in payments if payment.status == "paid"),
    }
    return render_template("admin.html", users=users, payments=payments, claims=claims, policies=policies, applications=applications, questions=questions, stats=stats)


@app.route("/policies")
def policies():
    return render_template("policies.html", policies=Policy.query.order_by(Policy.id).all())


@app.route("/buy_policy/<int:policy_id>", methods=["POST"])
@login_required
def buy_policy(policy_id):
    policy = Policy.query.get_or_404(policy_id)

    existing = CustomerPolicy.query.filter_by(user_id=current_user.id, policy_id=policy.id).first()
    if existing:
        flash("This policy is already in your account.")
        return redirect(url_for("dashboard"))

    enrollment = CustomerPolicy(user_id=current_user.id, policy_id=policy.id, status="pending_payment")
    db.session.add(enrollment)
    db.session.commit()
    flash(f"{policy.name} has been added. Complete payment to activate it.")
    return redirect(url_for("pay", enrollment_id=enrollment.id))


@app.route("/pay/<int:enrollment_id>", methods=["GET", "POST"])
@login_required
def pay(enrollment_id):
    enrollment = CustomerPolicy.query.filter_by(id=enrollment_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        reference = f"PAY-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{enrollment.id}"
        payment = Payment(
            customer_policy_id=enrollment.id,
            reference=reference,
            amount=enrollment.policy.premium_amount,
            method="demo_card",
            status="paid",
        )
        enrollment.status = "active"
        db.session.add(payment)
        db.session.commit()
        flash("Payment successful. Your policy is now active.")
        return redirect(url_for("dashboard"))

    return render_template("payment.html", enrollment=enrollment)


@app.route("/submit_claim/<int:enrollment_id>", methods=["GET", "POST"])
@login_required
def submit_claim(enrollment_id):
    enrollment = CustomerPolicy.query.filter_by(id=enrollment_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        claim_amount = float(request.form.get("claim_amount") or 0)
        description = (request.form.get("description") or "").strip()

        if claim_amount <= 0:
            flash("Claim amount must be greater than zero.")
        elif not description:
            flash("Please describe the claim.")
        else:
            claim = Claim(
                customer_policy_id=enrollment.id,
                claim_reference=f"CLM-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{enrollment.id}",
                claim_amount=claim_amount,
                description=description,
                status="under_review",
            )
            db.session.add(claim)
            db.session.commit()
            flash("Claim submitted successfully.")
            return redirect(url_for("dashboard"))

    return render_template("claim.html", enrollment=enrollment)


@app.route("/update_claim/<int:claim_id>", methods=["POST"])
@admin_required
def update_claim(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    claim.status = request.form.get("status", "under_review")
    db.session.commit()
    flash("Claim status updated.")
    return redirect(url_for("admin"))


@app.route("/admin/approve_policy/<int:application_id>", methods=["POST"])
@admin_required
def approve_policy(application_id):
    application = CustomerPolicy.query.get_or_404(application_id)
    application.status = "approved"
    db.session.commit()
    flash("Policy application approved.")
    return redirect(url_for("admin"))


@app.route("/admin/reject_policy/<int:application_id>", methods=["POST"])
@admin_required
def reject_policy(application_id):
    application = CustomerPolicy.query.get_or_404(application_id)
    application.status = "rejected"
    db.session.commit()
    flash("Policy application rejected.")
    return redirect(url_for("admin"))


@app.route("/admin/add_policy", methods=["POST"])
@admin_required
def add_policy():
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "").strip()
    description = (request.form.get("description") or "").strip()
    policy_code = (request.form.get("policy_code") or "").strip()
    premium_amount = float(request.form.get("premium_amount") or 0)
    duration_months = int(request.form.get("duration_months") or 0)

    if not all([name, category, description, policy_code]) or premium_amount <= 0 or duration_months <= 0:
        flash("Please complete all policy fields correctly.")
        return redirect(url_for("admin"))

    if Policy.query.filter_by(policy_code=policy_code).first():
        flash("A policy with that code already exists.")
        return redirect(url_for("admin"))

    db.session.add(Policy(
        name=name,
        category=category,
        description=description,
        policy_code=policy_code,
        premium_amount=premium_amount,
        duration_months=duration_months,
    ))
    db.session.commit()
    flash("Policy added successfully.")
    return redirect(url_for("admin"))


@app.route("/admin/update_policy/<int:policy_id>", methods=["POST"])
@admin_required
def update_policy(policy_id):
    policy = Policy.query.get_or_404(policy_id)
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "").strip()
    description = (request.form.get("description") or "").strip()
    policy_code = (request.form.get("policy_code") or "").strip()

    try:
        premium_amount = float(request.form.get("premium_amount") or 0)
        duration_months = int(request.form.get("duration_months") or 0)
    except ValueError:
        flash("Enter a valid premium and policy duration.")
        return redirect(url_for("admin"))

    if not all([name, category, description, policy_code]) or premium_amount <= 0 or duration_months <= 0:
        flash("Please complete all policy fields correctly.")
        return redirect(url_for("admin"))

    duplicate = Policy.query.filter(Policy.policy_code == policy_code, Policy.id != policy.id).first()
    if duplicate:
        flash("A policy with that code already exists.")
        return redirect(url_for("admin"))

    policy.name = name
    policy.category = category
    policy.description = description
    policy.policy_code = policy_code
    policy.premium_amount = premium_amount
    policy.duration_months = duration_months
    db.session.commit()
    flash("Policy updated successfully.")
    return redirect(url_for("admin"))


@app.route("/admin/delete_policy/<int:policy_id>", methods=["POST"])
@admin_required
def delete_policy(policy_id):
    policy = Policy.query.get_or_404(policy_id)
    db.session.delete(policy)
    db.session.commit()
    flash("Policy deleted.")
    return redirect(url_for("admin"))


@app.route("/admin/answer_question/<int:question_id>", methods=["POST"])
@admin_required
def answer_question(question_id):
    question = CustomerQuestion.query.get_or_404(question_id)
    answer = (request.form.get("answer") or "").strip()
    if not answer:
        flash("Answer cannot be empty.")
        return redirect(url_for("admin"))
    question.answer = answer
    question.status = "answered"
    db.session.commit()
    flash("Customer question answered.")
    return redirect(url_for("admin"))


@app.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for("index"))


@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", code=404, message="The requested page was not found."), 404


if __name__ == "__main__":
    app.run(debug=True)
