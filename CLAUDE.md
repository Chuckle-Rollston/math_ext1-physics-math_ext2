# QBank — project context for Claude

A Flask + SQLite web app where HSC students (NSW) submit LaTeX questions and
complete each other's. Credits gate the economy: contributing earns credits,
practising spends them.

## Running locally

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py          # http://127.0.0.1:5001
```

Debug mode and the reloader are on by default (`app.run(debug=True)`). If a
test leaves a process bound to the port, free it with
`lsof -ti :5001 | xargs -r kill -9`.

## File layout

- `app.py` — all routes, models, config, the lightweight `ALTER TABLE`
  migration that adds new columns to an existing `app.db`.
- `templates/` — Jinja templates. `base.html` loads MathJax from the jsdelivr
  CDN and defines the subject pill-bar.
- `static/style.css` — dark theme, subject colour tokens
  (`--math_ext1`, `--math_ext2`, `--math_adv`, `--physics`).
- `app.db` — SQLite, created on first boot. Not checked in.
- `.venv/` — local virtualenv. Not checked in.

## Data model

- `User(username, password_hash, credits)` — starts at 10 credits on signup.
- `Question(author_id, subject, topic, latex, answer_latex, difficulty,
  completion_count, credits_awarded_buckets)` — `credits_awarded_buckets`
  tracks how many times the author has been paid the +6 per-10-completions
  bonus, so the bonus is idempotent.
- `Completion(user_id, question_id, rated_difficulty, credits_charged,
  submitted_answer, was_correct)` — unique per (user, question).
- `Challenge(question_id, challenger_id, proposed_answer_latex, note, status)`
  — status is `open | original_wrong | both_correct | rejected`; the
  question's author resolves.

## Credit rules (single source of truth — keep in sync with `/credits` page)

- Signup: +10.
- Add a question: +20.
- Complete a question: −2, or −1 if the user also rates difficulty.
- Every 10 completions on your question: +6 to the author.
- Challenge resolved as `original_wrong`: −1 from author, +1 to challenger;
  official answer is replaced with the challenger's.
- Challenge resolved as `both_correct`: +1 to challenger (system-granted).
- Challenge resolved as `rejected`: no credit movement.

The credit logic lives in `add_question`, `view_question`, and
`resolve_challenge` in `app.py`. The user-facing explanation lives in
`templates/credits.html`. When changing the rules, update both.

## Subjects and topics

Subjects: `math_ext1`, `math_ext2`, `math_adv`, `physics`. Topics are defined
in the `TOPICS` dict at the top of `app.py` and sourced from the NESA Stage 6
syllabuses. When the Subject dropdown changes in the add-question modal, the
Topic dropdown is rewired client-side from `TOPICS` (passed via `|tojson`).
The server also validates that the submitted topic belongs to the subject.

## Conventions

- LaTeX is rendered by MathJax 3 with both `$...$` / `$$...$$` and
  `\(...\)` / `\[...\]` delimiters enabled. Previews re-typeset via
  `MathJax.typesetPromise`.
- Passwords use `werkzeug.security.generate_password_hash` /
  `check_password_hash`. Sessions are Flask's default (signed cookies).
- Schema changes: add a `db.Column` to the model AND extend the migration
  block at the bottom of `app.py` so existing `app.db` files get the new
  column without being deleted.
- No correctness check on LaTeX answers — completion is self-marked; disputes
  are resolved by the question's author. Don't add a CAS-based comparator
  without discussing scope first.

## Permissions — what Claude can do without asking

Free to do in this repo:

- Read, edit, and create files under the project root.
- Create/modify templates, CSS, and Python code.
- Install Python packages into `.venv/` and update `requirements.txt`.
- Boot the dev server (`.venv/bin/python app.py`), hit it with `curl`, and
  kill it afterwards (`lsof -ti :5001 | xargs -r kill -9`).
- Delete `app.db` when running end-to-end tests from a clean slate.
- Run `git status`, `git diff`, `git log`, `git branch` for orientation.

Ask first:

- `git commit`, `git push`, branch creation, rebases, or anything that
  changes git history.
- Installing system-level software or anything outside `.venv/`.
- Touching files outside this project directory.
- Deleting or renaming files the user hasn't mentioned.

Never:

- `git push --force`, `git reset --hard` on shared branches, or `--no-verify`
  on commits.
- Commit secrets. `SECRET_KEY` is read from the env; don't hardcode one.

## Common tasks

- Nuke the DB during testing: `rm -f app.db`.
- Add a new topic: edit `TOPICS` in `app.py`. No DB migration needed (topic
  is a free-text column validated against the dict on write).
- Add a new subject: add to `SUBJECTS`, `SUBJECT_LABELS`, and `TOPICS`; add a
  `--subject-name` CSS token and the `.pill.subject-name.active`,
  `.tag.subject-name`, and `.card.subject-accent-name` rules in
  `static/style.css`.
