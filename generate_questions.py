#!/usr/bin/env python3
"""
Generate HSC-style questions via the Grok API and insert them into the database.

Usage:
  XAI_API_KEY=your_key_here .venv/bin/python generate_questions.py

Options (edit the CONFIG block below):
  SUBJECT   — one of math_ext1 | math_ext2 | math_adv | physics  (or "all")
  TOPIC     — a specific topic string, or None to cycle all topics
  COUNT     — total questions to generate (split across topics)
  MODEL     — Grok model to use (default: grok-3-mini)
"""
import os, sys, json, time

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openai import OpenAI
from app import app, db, User, Question, SUBJECTS, SUBJECT_LABELS, TOPICS

# ── CONFIG ────────────────────────────────────────────────────────────────────
SUBJECT   = "all"          # "math_ext1" | "math_ext2" | "math_adv" | "physics" | "all"
TOPIC     = None           # e.g. "Calculus" — or None to cover all topics
COUNT     = 5              # questions PER TOPIC (or total if TOPIC is set)
MODEL     = "grok-3-mini"
SEED_USER = "qbank"
SEED_PASS = "qbank1234"
# ─────────────────────────────────────────────────────────────────────────────

api_key = os.environ.get("XAI_API_KEY")
if not api_key:
    sys.exit("Set XAI_API_KEY environment variable before running.")

client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

SYSTEM_PROMPT = """\
You are an expert HSC (NSW, Australia) mathematics and physics examiner.
Generate exam-style questions in valid LaTeX. All mathematical expressions
must be valid LaTeX. Do NOT wrap the latex fields in $$ or $ delimiters —
the calling code adds those. Output ONLY a JSON array, no commentary."""

def build_user_prompt(subject: str, topic: str, n: int) -> str:
    return f"""\
Generate {n} distinct HSC-style questions for:
  Subject: {SUBJECT_LABELS[subject]}
  Topic:   {topic}

Return a JSON array where each element has exactly these keys:
  "latex"              — question in LaTeX (no $$ delimiters, raw LaTeX only)
  "answer_latex"       — full worked solution in LaTeX (no $$ delimiters)
  "difficulty"         — integer 1–10 matching HSC exam difficulty
  "marks"              — integer marks this question would be worth
  "marking_guidelines" — plain-text rubric (e.g. "1 mark for ... 2 marks for ...")

Rules:
- Questions must be multi-step and require working, not just recall.
- Vary difficulty across the batch (easy, medium, hard).
- All LaTeX must compile without errors.
- Use \\text{{}} for prose inside math environments.
- Output ONLY the JSON array, nothing else."""


def call_grok(subject: str, topic: str, n: int) -> list[dict]:
    prompt = build_user_prompt(subject, topic, n)
    print(f"  → Calling Grok for {subject}/{topic} ({n} questions)…", end=" ", flush=True)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.8,
    )
    raw = resp.choices[0].message.content.strip()
    # Strip markdown code fence if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    questions = json.loads(raw.strip())
    print(f"got {len(questions)}.")
    return questions


def run():
    with app.app_context():
        # Ensure seed user exists
        user = User.query.filter_by(username=SEED_USER).first()
        if not user:
            user = User(username=SEED_USER, credits=10_000)
            user.set_password(SEED_PASS)
            db.session.add(user)
            db.session.commit()
            print(f"Created user '{SEED_USER}'.")

        existing = {q.latex for q in Question.query.filter_by(author_id=user.id).all()}

        subjects = SUBJECTS if SUBJECT == "all" else [SUBJECT]
        total_added = 0

        for subj in subjects:
            topics = [TOPIC] if TOPIC else TOPICS[subj]
            for topic in topics:
                try:
                    questions = call_grok(subj, topic, COUNT)
                except Exception as e:
                    print(f"  ✗ Error ({subj}/{topic}): {e}")
                    continue

                added = 0
                for qdata in questions:
                    latex = qdata.get("latex", "").strip()
                    if not latex or latex in existing:
                        continue
                    try:
                        q = Question(
                            author_id=user.id,
                            subject=subj,
                            topic=topic,
                            latex=latex,
                            answer_latex=qdata.get("answer_latex", "").strip(),
                            difficulty=max(1, min(10, int(qdata.get("difficulty", 5)))),
                            marks=int(qdata["marks"]) if qdata.get("marks") else None,
                            marking_guidelines=qdata.get("marking_guidelines") or None,
                        )
                        db.session.add(q)
                        existing.add(latex)
                        added += 1
                    except Exception as e:
                        print(f"  ✗ Skipped a question ({e})")

                db.session.commit()
                print(f"     Inserted {added} into {subj}/{topic}.")
                total_added += added
                time.sleep(0.5)  # gentle rate limiting

        print(f"\nDone. Total inserted: {total_added}.")


if __name__ == "__main__":
    run()
