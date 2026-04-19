import os
import secrets
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, abort
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash, check_password_hash

SUBJECTS = ["math_ext1", "math_ext2", "math_adv", "physics"]
SUBJECT_LABELS = {
    "math_ext1": "Math Ext 1",
    "math_ext2": "Math Ext 2",
    "math_adv":  "Math Adv",
    "physics":   "Physics",
}

TOPICS = {
    "math_ext1": [
        "Functions",
        "Trigonometric functions",
        "Proof",
        "Vectors",
        "Calculus",
        "Differential equations",
        "Combinatorics",
        "Projectile motion",
        "Binomial distribution",
    ],
    "math_ext2": [
        "Complex numbers",
        "Further proof",
        "Further integration",
        "Applications of calculus to mechanics",
        "Vectors",
    ],
    "math_adv": [
        "Functions",
        "Trigonometric functions",
        "Calculus",
        "Exponential and logarithmic functions",
        "Financial mathematics",
        "Sequences and series",
        "Statistical analysis",
        "Probability",
    ],
    "physics": [
        "Kinematics",
        "Dynamics",
        "Waves and thermodynamics",
        "Electricity and magnetism",
        "Advanced mechanics",
        "Electromagnetism",
        "The nature of light",
        "From the universe to the atom",
    ],
}

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def _database_uri() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        # Some providers (Heroku, older Neon) hand out postgres:// — SQLAlchemy wants postgresql://
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        # psycopg2 driver
        if url.startswith("postgresql://") and "+psycopg2" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url
    # Local dev fallback: writable SQLite under /tmp on serverless, alongside app.py locally.
    if os.environ.get("VERCEL"):
        return "sqlite:////tmp/app.db"
    return "sqlite:///" + os.path.join(BASE_DIR, "app.db")


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    credits = db.Column(db.Integer, default=10, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship("Question", backref="author", lazy=True,
                                foreign_keys="Question.author_id")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(20), nullable=False)
    topic = db.Column(db.String(80), nullable=True)
    latex = db.Column(db.Text, nullable=False)
    answer_latex = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Integer, nullable=False)  # 1-10
    completion_count = db.Column(db.Integer, default=0, nullable=False)
    credits_awarded_buckets = db.Column(db.Integer, default=0, nullable=False)  # per-10 bonus payouts
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Completion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    rated_difficulty = db.Column(db.Integer, nullable=True)  # 1-10 if rated
    credits_charged = db.Column(db.Integer, nullable=False)
    submitted_answer = db.Column(db.Text, nullable=True)
    was_correct = db.Column(db.Boolean, default=False, nullable=False)  # self-marked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "question_id",
                                          name="uix_user_question"),)


class Challenge(db.Model):
    """User disputes the official answer for a question."""
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    challenger_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    proposed_answer_latex = db.Column(db.Text, nullable=False)
    note = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="open", nullable=False)
    # open | original_wrong | both_correct | rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    question = db.relationship("Question", backref="challenges")
    challenger = db.relationship("User", foreign_keys=[challenger_id])


# ---------- auth helpers ----------

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db.session.get(User, uid)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Log in to continue.", "warn")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {
        "current_user": current_user(),
        "SUBJECTS": SUBJECTS,
        "SUBJECT_LABELS": SUBJECT_LABELS,
        "TOPICS": TOPICS,
    }


# ---------- routes ----------

@app.route("/")
def index():
    subject = request.args.get("subject", "all")
    q = Question.query
    if subject in SUBJECTS:
        q = q.filter_by(subject=subject)
    questions = q.order_by(Question.created_at.desc()).limit(200).all()

    # For logged-in users, mark which are already completed
    done_ids = set()
    user = current_user()
    if user:
        rows = Completion.query.with_entities(Completion.question_id).filter_by(user_id=user.id).all()
        done_ids = {r[0] for r in rows}

    return render_template("index.html",
                           questions=questions,
                           active_subject=subject,
                           done_ids=done_ids)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password required.", "error")
            return redirect(url_for("register"))
        if User.query.filter_by(username=username).first():
            flash("Username taken.", "error")
            return redirect(url_for("register"))
        u = User(username=username, credits=10)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        session["user_id"] = u.id
        flash("Welcome! You start with 10 credits.", "ok")
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        u = User.query.filter_by(username=username).first()
        if not u or not u.check_password(password):
            flash("Invalid credentials.", "error")
            return redirect(url_for("login"))
        session["user_id"] = u.id
        return redirect(request.args.get("next") or url_for("index"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/add", methods=["POST"])
@login_required
def add_question():
    user = current_user()
    subject = request.form.get("subject", "")
    topic = request.form.get("topic", "").strip()
    latex = request.form.get("latex", "").strip()
    answer_latex = request.form.get("answer_latex", "").strip()
    try:
        difficulty = int(request.form.get("difficulty", "5"))
    except ValueError:
        difficulty = 5
    difficulty = max(1, min(10, difficulty))

    if subject not in SUBJECTS or not latex or not answer_latex:
        flash("Subject, question, and answer are all required.", "error")
        return redirect(url_for("index"))
    if topic and topic not in TOPICS.get(subject, []):
        flash("Topic doesn't match subject.", "error")
        return redirect(url_for("index"))

    q = Question(
        author_id=user.id,
        subject=subject,
        topic=topic or None,
        latex=latex,
        answer_latex=answer_latex,
        difficulty=difficulty,
    )
    user.credits += 20
    db.session.add(q)
    db.session.commit()
    flash("Question added. +20 credits.", "ok")
    return redirect(url_for("index", subject=subject))


@app.route("/question/<int:qid>", methods=["GET", "POST"])
@login_required
def view_question(qid):
    user = current_user()
    q = db.session.get(Question, qid)
    if not q:
        abort(404)

    existing = Completion.query.filter_by(user_id=user.id, question_id=q.id).first()

    if request.method == "POST" and not existing:
        if q.author_id == user.id:
            flash("You can't complete your own question.", "error")
            return redirect(url_for("view_question", qid=q.id))

        submitted = request.form.get("submitted_answer", "").strip()
        was_correct = request.form.get("was_correct") == "yes"
        rated = request.form.get("rated_difficulty", "").strip()
        try:
            rated_int = int(rated) if rated else None
        except ValueError:
            rated_int = None
        if rated_int is not None:
            rated_int = max(1, min(10, rated_int))

        cost = 1 if rated_int is not None else 2
        if user.credits < cost:
            flash(f"Not enough credits (need {cost}).", "error")
            return redirect(url_for("view_question", qid=q.id))

        user.credits -= cost
        comp = Completion(
            user_id=user.id,
            question_id=q.id,
            rated_difficulty=rated_int,
            credits_charged=cost,
            submitted_answer=submitted or None,
            was_correct=was_correct,
        )
        q.completion_count += 1

        # Every 10 completions → +6 credits to author
        due_buckets = q.completion_count // 10
        if due_buckets > q.credits_awarded_buckets:
            missed = due_buckets - q.credits_awarded_buckets
            author = db.session.get(User, q.author_id)
            if author:
                author.credits += 6 * missed
            q.credits_awarded_buckets = due_buckets

        db.session.add(comp)
        db.session.commit()
        flash(f"Completed. -{cost} credits.", "ok")
        return redirect(url_for("view_question", qid=q.id))

    return render_template("question.html", q=q, existing=existing)


@app.route("/question/<int:qid>/challenge", methods=["POST"])
@login_required
def submit_challenge(qid):
    user = current_user()
    q = db.session.get(Question, qid)
    if not q:
        abort(404)
    if q.author_id == user.id:
        flash("You can't challenge your own question.", "error")
        return redirect(url_for("view_question", qid=q.id))

    proposed = request.form.get("proposed_answer_latex", "").strip()
    note = request.form.get("note", "").strip() or None
    if not proposed:
        flash("Proposed answer is required.", "error")
        return redirect(url_for("view_question", qid=q.id))

    ch = Challenge(
        question_id=q.id,
        challenger_id=user.id,
        proposed_answer_latex=proposed,
        note=note,
    )
    db.session.add(ch)
    db.session.commit()
    flash("Challenge submitted. The question's author will resolve it.", "ok")
    return redirect(url_for("view_question", qid=q.id))


@app.route("/challenges")
@login_required
def challenges():
    user = current_user()
    # Open challenges on questions I authored
    incoming = (Challenge.query
                .join(Question, Challenge.question_id == Question.id)
                .filter(Question.author_id == user.id,
                        Challenge.status == "open")
                .order_by(Challenge.created_at.desc())
                .all())
    # My own submitted challenges
    outgoing = (Challenge.query
                .filter(Challenge.challenger_id == user.id)
                .order_by(Challenge.created_at.desc())
                .all())
    return render_template("challenges.html", incoming=incoming, outgoing=outgoing)


@app.route("/challenges/<int:cid>/resolve", methods=["POST"])
@login_required
def resolve_challenge(cid):
    user = current_user()
    ch = db.session.get(Challenge, cid)
    if not ch:
        abort(404)
    q = db.session.get(Question, ch.question_id)
    if q.author_id != user.id:
        abort(403)
    if ch.status != "open":
        flash("Already resolved.", "error")
        return redirect(url_for("challenges"))

    outcome = request.form.get("outcome", "")
    challenger = db.session.get(User, ch.challenger_id)

    if outcome == "original_wrong":
        # Move 1 credit from author to challenger, replace official answer
        if user.credits >= 1:
            user.credits -= 1
        challenger.credits += 1
        q.answer_latex = ch.proposed_answer_latex
        ch.status = "original_wrong"
    elif outcome == "both_correct":
        challenger.credits += 1  # system-granted bonus
        ch.status = "both_correct"
    elif outcome == "rejected":
        ch.status = "rejected"
    else:
        flash("Unknown outcome.", "error")
        return redirect(url_for("challenges"))

    ch.resolved_at = datetime.utcnow()
    db.session.commit()
    flash("Challenge resolved.", "ok")
    return redirect(url_for("challenges"))


@app.route("/credits")
def credits_info():
    return render_template("credits.html")


@app.route("/profile")
@login_required
def profile():
    user = current_user()
    mine = Question.query.filter_by(author_id=user.id).order_by(Question.created_at.desc()).all()
    done = (Completion.query
            .filter_by(user_id=user.id)
            .order_by(Completion.created_at.desc())
            .limit(50).all())
    return render_template("profile.html", mine=mine, done=done)


@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("DB initialised.")


with app.app_context():
    db.create_all()
    # Lightweight migration: add `topic` column if an older DB is missing it.
    insp = inspect(db.engine)
    if "question" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("question")}
        if "topic" not in cols:
            db.session.execute(text("ALTER TABLE question ADD COLUMN topic VARCHAR(80)"))
            db.session.commit()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
