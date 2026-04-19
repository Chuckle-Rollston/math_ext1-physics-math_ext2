import os
import random
import secrets
import uuid
from collections import Counter
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, abort
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, inspect, text
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


UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_IMAGE_BYTES = 150 * 1024  # 150 KB

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
    marks = db.Column(db.Integer, nullable=True)
    marking_guidelines = db.Column(db.Text, nullable=True)
    graph_url = db.Column(db.String(300), nullable=True)
    answer_graph_url = db.Column(db.String(300), nullable=True)
    image_filename = db.Column(db.String(100), nullable=True)
    completion_count = db.Column(db.Integer, default=0, nullable=False)
    credits_awarded_buckets = db.Column(db.Integer, default=0, nullable=False)  # per-10 bonus payouts
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Completion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    rated_difficulty = db.Column(db.Integer, nullable=True)  # 1-10 if rated
    quality_rating = db.Column(db.Integer, nullable=True)   # 1-10 question quality
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


class CommunityVote(db.Model):
    """Community member votes on how a challenge should be resolved."""
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenge.id"), nullable=False)
    voter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    vote = db.Column(db.String(20), nullable=False)  # original_wrong | both_correct | rejected
    working_out = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("challenge_id", "voter_id", name="uix_challenge_voter"),)

    challenge = db.relationship("Challenge", backref="community_votes")
    voter = db.relationship("User", foreign_keys=[voter_id])


VOTE_THRESHOLD = 10   # total votes needed to resolve
AGREE_THRESHOLD = 9   # votes for the same outcome to reach consensus


def _dispute_credit_value(challenge):
    """Credits awarded for voting: 3 normally, +1 per week of inactivity, max 5."""
    now = datetime.utcnow()
    last = (CommunityVote.query
            .filter_by(challenge_id=challenge.id)
            .order_by(CommunityVote.created_at.desc())
            .first())
    last_activity = last.created_at if last else challenge.created_at
    days = (now - last_activity).days
    if days >= 14:
        return 5
    if days >= 7:
        return 4
    return 3


def _check_community_resolution(challenge):
    """Resolve challenge if community consensus reached. Does not commit."""
    if challenge.status != "open":
        return
    votes = CommunityVote.query.filter_by(challenge_id=challenge.id).all()
    if len(votes) < VOTE_THRESHOLD:
        return
    counts = Counter(v.vote for v in votes)
    top_outcome, top_count = counts.most_common(1)[0]
    if top_count < AGREE_THRESHOLD:
        return

    credit_value = _dispute_credit_value(challenge)
    q = db.session.get(Question, challenge.question_id)
    author = db.session.get(User, q.author_id)
    challenger = db.session.get(User, challenge.challenger_id)

    if top_outcome == "original_wrong":
        if author and author.credits >= 1:
            author.credits -= 1
        if challenger:
            challenger.credits += 1
        q.answer_latex = challenge.proposed_answer_latex
    elif top_outcome == "both_correct":
        if challenger:
            challenger.credits += 1

    for v in votes:
        if v.vote == top_outcome:
            voter = db.session.get(User, v.voter_id)
            if voter:
                voter.credits += credit_value

    challenge.status = top_outcome
    challenge.resolved_at = datetime.utcnow()


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


def _clean_desmos_url(raw):
    url = (raw or "").strip()
    if url.startswith("https://www.desmos.com/calculator/"):
        return url.split("?")[0]  # strip any existing query params
    return None


@app.route("/add", methods=["POST"])
@login_required
def add_question():
    user = current_user()
    subject = request.form.get("subject", "")
    topic = request.form.get("topic", "").strip()
    latex = request.form.get("latex", "").strip()
    answer_latex = request.form.get("answer_latex", "").strip()
    graph_url = _clean_desmos_url(request.form.get("graph_url", ""))
    answer_graph_url = _clean_desmos_url(request.form.get("answer_graph_url", ""))
    marking_guidelines = request.form.get("marking_guidelines", "").strip() or None
    try:
        difficulty = int(request.form.get("difficulty", "5"))
    except ValueError:
        difficulty = 5
    difficulty = max(1, min(10, difficulty))
    try:
        marks = int(request.form.get("marks", ""))
    except (ValueError, TypeError):
        marks = None

    if subject not in SUBJECTS or not latex or not answer_latex:
        flash("Subject, question, and answer are all required.", "error")
        return redirect(url_for("index"))
    if topic and topic not in TOPICS.get(subject, []):
        flash("Topic doesn't match subject.", "error")
        return redirect(url_for("index"))
    if not request.form.get("agree_tos"):
        flash("You must agree to the Terms of Service to post a question.", "error")
        return redirect(url_for("index"))

    image_filename = None
    img = request.files.get("image")
    if img and img.filename:
        ext = img.filename.rsplit(".", 1)[-1].lower() if "." in img.filename else ""
        if ext not in ALLOWED_IMAGE_EXTS:
            flash("Image must be PNG, JPG, GIF, or WEBP.", "error")
            return redirect(url_for("index"))
        img_data = img.read()
        if len(img_data) > MAX_IMAGE_BYTES:
            flash("Image must be under 150 KB.", "error")
            return redirect(url_for("index"))
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        image_filename = str(uuid.uuid4()) + "." + ext
        with open(os.path.join(UPLOAD_FOLDER, image_filename), "wb") as f:
            f.write(img_data)

    q = Question(
        author_id=user.id,
        subject=subject,
        topic=topic or None,
        latex=latex,
        answer_latex=answer_latex,
        difficulty=difficulty,
        marks=marks,
        marking_guidelines=marking_guidelines,
        graph_url=graph_url,
        answer_graph_url=answer_graph_url,
        image_filename=image_filename,
    )
    user.credits += 5
    db.session.add(q)
    db.session.commit()
    flash("Question added. +5 credits.", "ok")
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
        quality = request.form.get("quality_rating", "").strip()
        study_mode = request.form.get("study") == "1"
        try:
            rated_int = int(rated) if rated else None
        except ValueError:
            rated_int = None
        if rated_int is not None:
            rated_int = max(1, min(10, rated_int))
        try:
            quality_int = int(quality) if quality else None
        except ValueError:
            quality_int = None
        if quality_int is not None:
            quality_int = max(1, min(10, quality_int))

        cost = 1 if rated_int is not None else 2
        if user.credits < cost:
            return redirect(url_for("view_question", qid=q.id, no_credits=1))

        user.credits -= cost
        comp = Completion(
            user_id=user.id,
            question_id=q.id,
            rated_difficulty=rated_int,
            quality_rating=quality_int,
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
        msg = "Completed. +1 credit for rating!" if rated_int is not None else "Completed."
        flash(msg, "ok")
        if study_mode:
            return redirect(url_for("study_next"))
        return redirect(url_for("view_question", qid=q.id))

    study_mode = request.args.get("study") == "1"
    return render_template("question.html", q=q, existing=existing, study_mode=study_mode)


@app.route("/question/<int:qid>/update-ratings", methods=["POST"])
@login_required
def update_ratings(qid):
    user = current_user()
    comp = Completion.query.filter_by(user_id=user.id, question_id=qid).first()
    if not comp:
        abort(404)
    rated_diff = request.form.get("rated_difficulty")
    quality = request.form.get("quality_rating")
    if rated_diff:
        new_diff = int(rated_diff)
        if comp.rated_difficulty is None and comp.credits_charged == 2:
            user.credits += 1
            comp.credits_charged = 1
        comp.rated_difficulty = new_diff
    if quality:
        comp.quality_rating = int(quality)
    db.session.commit()
    flash("Ratings updated.", "ok")
    study = request.form.get("study") == "1"
    kwargs = {"qid": qid}
    if study:
        kwargs["study"] = 1
    return redirect(url_for("view_question", **kwargs))


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
    study = request.form.get("study") == "1"
    kwargs = {"qid": q.id, "challenged": 1}
    if study:
        kwargs["study"] = 1
    return redirect(url_for("view_question", **kwargs))


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


@app.route("/gain-credits")
def gain_credits():
    open_count = 0
    user = current_user()
    if user:
        voted_ids = [v.challenge_id for v in
                     CommunityVote.query.filter_by(voter_id=user.id).all()]
        q = (Challenge.query
             .join(Question, Challenge.question_id == Question.id)
             .filter(Challenge.status == "open",
                     Question.author_id != user.id,
                     Challenge.challenger_id != user.id))
        if voted_ids:
            q = q.filter(Challenge.id.notin_(voted_ids))
        open_count = q.count()
    return render_template("gain_credits.html", open_count=open_count)


@app.route("/community-disputes")
@login_required
def community_disputes():
    user = current_user()
    voted_ids = [v.challenge_id for v in
                 CommunityVote.query.filter_by(voter_id=user.id).all()]
    q = (Challenge.query
         .join(Question, Challenge.question_id == Question.id)
         .filter(Challenge.status == "open",
                 Question.author_id != user.id,
                 Challenge.challenger_id != user.id)
         .order_by(Challenge.created_at.asc()))
    if voted_ids:
        q = q.filter(Challenge.id.notin_(voted_ids))
    disputes = [(ch, _dispute_credit_value(ch)) for ch in q.all()]
    return render_template("community_disputes.html", disputes=disputes)


@app.route("/disputes/<int:cid>")
@login_required
def view_dispute(cid):
    user = current_user()
    ch = db.session.get(Challenge, cid)
    if not ch:
        abort(404)
    q = db.session.get(Question, ch.question_id)
    my_vote = CommunityVote.query.filter_by(challenge_id=cid, voter_id=user.id).first()
    all_votes = CommunityVote.query.filter_by(challenge_id=cid).all()
    vote_counts = dict(Counter(v.vote for v in all_votes))
    credit_value = _dispute_credit_value(ch)
    can_vote = (ch.status == "open" and not my_vote
                and q.author_id != user.id and ch.challenger_id != user.id)
    return render_template("view_dispute.html", ch=ch, q=q, my_vote=my_vote,
                           all_votes=all_votes, vote_counts=vote_counts,
                           credit_value=credit_value, can_vote=can_vote,
                           total_votes=len(all_votes))


@app.route("/disputes/<int:cid>/vote", methods=["POST"])
@login_required
def vote_on_dispute(cid):
    user = current_user()
    ch = db.session.get(Challenge, cid)
    if not ch:
        abort(404)
    q = db.session.get(Question, ch.question_id)

    if ch.status != "open":
        flash("This dispute is already resolved.", "error")
        return redirect(url_for("view_dispute", cid=cid))
    if q.author_id == user.id:
        flash("You can't vote on a dispute about your own question.", "error")
        return redirect(url_for("community_disputes"))
    if ch.challenger_id == user.id:
        flash("You can't vote on your own challenge.", "error")
        return redirect(url_for("community_disputes"))
    if CommunityVote.query.filter_by(challenge_id=cid, voter_id=user.id).first():
        flash("You've already voted on this dispute.", "error")
        return redirect(url_for("view_dispute", cid=cid))

    vote = request.form.get("vote", "")
    working_out = request.form.get("working_out", "").strip()

    if vote not in ("original_wrong", "both_correct", "rejected"):
        flash("Select a verdict.", "error")
        return redirect(url_for("view_dispute", cid=cid))
    if not working_out:
        flash("You must provide working out.", "error")
        return redirect(url_for("view_dispute", cid=cid))

    cv = CommunityVote(challenge_id=cid, voter_id=user.id,
                       vote=vote, working_out=working_out)
    db.session.add(cv)
    db.session.commit()

    _check_community_resolution(ch)
    db.session.commit()

    if ch.status != "open":
        flash("Your vote resolved the dispute! Credits awarded to the winning voters.", "ok")
    else:
        flash(f"Vote submitted. {VOTE_THRESHOLD - CommunityVote.query.filter_by(challenge_id=cid).count()} more vote(s) needed.", "ok")
    return redirect(url_for("view_dispute", cid=cid))


@app.route("/study", methods=["GET", "POST"])
@login_required
def study():
    if request.method == "POST":
        subjects = request.form.getlist("subjects")
        topics = request.form.getlist("topics")
        try:
            diff_min = max(1, min(10, int(request.form.get("diff_min", 1))))
            diff_max = max(1, min(10, int(request.form.get("diff_max", 10))))
        except ValueError:
            diff_min, diff_max = 1, 10
        if diff_min > diff_max:
            diff_min, diff_max = diff_max, diff_min
        try:
            qual_min = max(1, min(10, int(request.form.get("qual_min", 1))))
            qual_max = max(1, min(10, int(request.form.get("qual_max", 10))))
        except ValueError:
            qual_min, qual_max = 1, 10
        if qual_min > qual_max:
            qual_min, qual_max = qual_max, qual_min
        session["study_prefs"] = dict(subjects=subjects, topics=topics,
                                      diff_min=diff_min, diff_max=diff_max,
                                      qual_min=qual_min, qual_max=qual_max)
        return redirect(url_for("study_next"))
    prefs = session.get("study_prefs", {})
    return render_template("study.html", prefs=prefs)


@app.route("/study/next")
@login_required
def study_next():
    user = current_user()
    prefs = session.get("study_prefs")
    if not prefs:
        return redirect(url_for("study"))

    subjects = prefs.get("subjects") or SUBJECTS
    topics = prefs.get("topics") or []
    diff_min = prefs.get("diff_min", 1)
    diff_max = prefs.get("diff_max", 10)
    qual_min = prefs.get("qual_min", 1)
    qual_max = prefs.get("qual_max", 10)

    q = Question.query.filter(
        Question.subject.in_(subjects),
        Question.difficulty >= diff_min,
        Question.difficulty <= diff_max,
        Question.author_id != user.id,
    )
    if topics:
        q = q.filter(Question.topic.in_(topics))

    all_matching = q.all()
    if not all_matching:
        flash("No questions match your study filters — try widening them.", "warn")
        return redirect(url_for("study"))

    # Filter by average quality rating; questions with no ratings always pass
    if qual_min != 1 or qual_max != 10:
        qual_avgs = dict(
            db.session.query(Completion.question_id, func.avg(Completion.quality_rating))
            .filter(Completion.quality_rating.isnot(None))
            .group_by(Completion.question_id)
            .all()
        )
        quality_filtered = [
            x for x in all_matching
            if x.id not in qual_avgs or qual_min <= qual_avgs[x.id] <= qual_max
        ]
        if quality_filtered:
            all_matching = quality_filtered

    done_ids = {c.question_id for c in Completion.query.filter_by(user_id=user.id).all()}
    undone = [x for x in all_matching if x.id not in done_ids]
    pool = undone if undone else all_matching
    next_q = random.choice(pool)
    return redirect(url_for("view_question", qid=next_q.id, study=1))


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
    insp = inspect(db.engine)
    if "question" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("question")}
        for col, ddl in [
            ("topic",               "ALTER TABLE question ADD COLUMN topic VARCHAR(80)"),
            ("graph_url",           "ALTER TABLE question ADD COLUMN graph_url VARCHAR(300)"),
            ("answer_graph_url",    "ALTER TABLE question ADD COLUMN answer_graph_url VARCHAR(300)"),
            ("marks",               "ALTER TABLE question ADD COLUMN marks INTEGER"),
            ("marking_guidelines",  "ALTER TABLE question ADD COLUMN marking_guidelines TEXT"),
            ("image_filename",      "ALTER TABLE question ADD COLUMN image_filename VARCHAR(100)"),
        ]:
            if col not in cols:
                db.session.execute(text(ddl))
                db.session.commit()
    if "completion" in insp.get_table_names():
        ccols = {c["name"] for c in insp.get_columns("completion")}
        if "quality_rating" not in ccols:
            db.session.execute(text("ALTER TABLE completion ADD COLUMN quality_rating INTEGER"))
            db.session.commit()


@app.route("/terms")
def tos():
    return render_template("tos.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


if __name__ == "__main__":
    app.run(debug=True, port=5001)
