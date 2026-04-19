#!/usr/bin/env python3
"""
Seed the QBank database with HSC-style questions.

Usage:
  .venv/bin/python seed.py

Creates a 'qbank' author account (password: qbank1234) if it doesn't
already exist, then inserts every question not already present.
Run as many times as you like — it's idempotent.
"""
import os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db, User, Question

SEED_USER = "qbank"
SEED_PASS = "qbank1234"

# Each entry: subject, topic, difficulty (1-10), latex, answer_latex
# latex/answer_latex are raw LaTeX — the template wraps them in $$ ... $$
QUESTIONS = [

    # ── Math Ext 2 ──────────────────────────────────────────────────────────

    dict(subject="math_ext2", topic="Complex numbers", difficulty=3,
         latex=r"\text{Express } z = -\sqrt{3} + i \text{ in modulus-argument form } r(\cos\theta + i\sin\theta).",
         answer_latex=r"r = |z| = \sqrt{(-\sqrt{3})^2 + 1^2} = 2, \quad \theta = \pi - \frac{\pi}{6} = \frac{5\pi}{6} \\ z = 2\!\left(\cos\frac{5\pi}{6} + i\sin\frac{5\pi}{6}\right)"),

    dict(subject="math_ext2", topic="Complex numbers", difficulty=4,
         latex=r"\text{Let } z = 1 + i. \text{ Find } z^8 \text{ in the form } a + bi.",
         answer_latex=r"z = \sqrt{2}\,e^{i\pi/4} \implies z^8 = (\sqrt{2})^8 e^{i \cdot 2\pi} = 16 \cdot 1 = 16 + 0i"),

    dict(subject="math_ext2", topic="Complex numbers", difficulty=6,
         latex=r"\text{Find all cube roots of } -8 \text{ in the form } a + bi.",
         answer_latex=r"-8 = 8e^{i\pi} \implies \text{roots} = 2e^{i(\pi+2k\pi)/3},\ k=0,1,2 \\ = 1+i\sqrt{3},\quad -2,\quad 1-i\sqrt{3}"),

    dict(subject="math_ext2", topic="Further integration", difficulty=4,
         latex=r"\text{Use integration by parts to evaluate } \int x e^x \, dx.",
         answer_latex=r"\int x e^x\,dx = x e^x - \int e^x\,dx = x e^x - e^x + C = e^x(x-1) + C"),

    dict(subject="math_ext2", topic="Further integration", difficulty=5,
         latex=r"\text{Evaluate } \int \frac{1}{x^2 + 4x + 5}\,dx.",
         answer_latex=r"x^2+4x+5 = (x+2)^2+1 \implies \int \frac{1}{(x+2)^2+1}\,dx = \arctan(x+2) + C"),

    dict(subject="math_ext2", topic="Further integration", difficulty=6,
         latex=r"\text{Evaluate } \int_0^1 x^2 \ln x \, dx.",
         answer_latex=r"\left[\frac{x^3}{3}\ln x\right]_0^1 - \int_0^1 \frac{x^3}{3}\cdot\frac{1}{x}\,dx = 0 - \frac{1}{3}\cdot\frac{x^3}{3}\Big|_0^1 = -\frac{1}{9}"),

    dict(subject="math_ext2", topic="Further proof", difficulty=5,
         latex=r"\text{Prove by mathematical induction: } \sum_{k=1}^n k^2 = \frac{n(n+1)(2n+1)}{6}.",
         answer_latex=r"\textbf{Base: } n=1:\ 1 = \tfrac{1\cdot2\cdot3}{6}=1\ \checkmark \\ \textbf{Step: } \text{Assume true for } n=m. \text{ Then} \\ \sum_{k=1}^{m+1}k^2 = \frac{m(m+1)(2m+1)}{6}+(m+1)^2 = \frac{(m+1)(m+2)(2m+3)}{6}\ \checkmark"),

    dict(subject="math_ext2", topic="Further proof", difficulty=6,
         latex=r"\text{Prove that } \sqrt{2} \text{ is irrational.}",
         answer_latex=r"\text{Assume } \sqrt{2}=\frac{p}{q} \text{ in lowest terms. Then } 2q^2=p^2, \text{ so } p \text{ is even.} \\ \text{Write } p=2m \Rightarrow 2q^2=4m^2 \Rightarrow q^2=2m^2, \text{ so } q \text{ is even.} \\ \text{Contradicts lowest terms. Hence } \sqrt{2} \text{ is irrational.}"),

    dict(subject="math_ext2", topic="Vectors", difficulty=4,
         latex=r"\text{Find the angle between } \mathbf{a} = (1, 2, 2) \text{ and } \mathbf{b} = (2, 1, -2).",
         answer_latex=r"\cos\theta = \frac{\mathbf{a}\cdot\mathbf{b}}{|\mathbf{a}||\mathbf{b}|} = \frac{2+2-4}{3\cdot 3} = 0 \implies \theta = 90°"),

    dict(subject="math_ext2", topic="Applications of calculus to mechanics", difficulty=5,
         latex=r"\text{A particle has velocity } v = t^2 - 5t + 6 \text{ m/s}. \text{ Find all times when the particle is at rest and determine the displacement from } t=0 \text{ to } t=4.",
         answer_latex=r"v=0: (t-2)(t-3)=0 \Rightarrow t=2,3 \text{ s} \\ x = \int_0^4(t^2-5t+6)\,dt = \left[\frac{t^3}{3}-\frac{5t^2}{2}+6t\right]_0^4 = \frac{64}{3}-40+24 = \frac{16}{3} \approx 5.33 \text{ m}"),

    # ── Math Ext 1 ──────────────────────────────────────────────────────────

    dict(subject="math_ext1", topic="Binomial distribution", difficulty=4,
         latex=r"X \sim B(8,\, 0.4). \text{ Find } P(X = 3).",
         answer_latex=r"P(X=3) = \binom{8}{3}(0.4)^3(0.6)^5 = 56 \times 0.064 \times 0.07776 \approx 0.2787"),

    dict(subject="math_ext1", topic="Binomial distribution", difficulty=5,
         latex=r"X \sim B(10,\, 0.3). \text{ Find } P(X \geq 2).",
         answer_latex=r"P(X\geq2)=1-P(X=0)-P(X=1) \\ =1-(0.7)^{10}-10(0.3)(0.7)^9 \\ =1-0.0282-0.1211 \approx 0.8507"),

    dict(subject="math_ext1", topic="Proof", difficulty=4,
         latex=r"\text{Prove by induction: } 1+2+3+\cdots+n = \frac{n(n+1)}{2} \text{ for all } n \in \mathbb{Z}^+.",
         answer_latex=r"\textbf{Base: } n=1:\ 1=\frac{1\cdot2}{2}=1\ \checkmark \\ \textbf{Step: } \text{Assume true for }n=m. \text{ Then} \\ 1+\cdots+m+(m+1)=\frac{m(m+1)}{2}+(m+1)=\frac{(m+1)(m+2)}{2}\ \checkmark"),

    dict(subject="math_ext1", topic="Combinatorics", difficulty=4,
         latex=r"\text{How many ways can 4 boys and 4 girls be arranged in a row if no two boys are adjacent?}",
         answer_latex=r"\text{Arrange 4 girls: } 4! \text{ ways. Place boys in the 5 gaps: } P(5,4) = 5\times4\times3\times2 = 120 \\ \text{Total} = 4!\times120 = 24\times120 = 2880"),

    dict(subject="math_ext1", topic="Trigonometric functions", difficulty=4,
         latex=r"\text{Solve } 2\sin^2 x - \sin x - 1 = 0 \text{ for } x \in [0,\, 2\pi].",
         answer_latex=r"(2\sin x + 1)(\sin x - 1)=0 \Rightarrow \sin x = -\tfrac{1}{2} \text{ or } \sin x = 1 \\ x = \frac{\pi}{2},\ \frac{7\pi}{6},\ \frac{11\pi}{6}"),

    dict(subject="math_ext1", topic="Calculus", difficulty=5,
         latex=r"\text{Find } \int \frac{x}{\sqrt{1-x^2}}\,dx.",
         answer_latex=r"\text{Let } u = 1-x^2,\ du=-2x\,dx \\ \int \frac{x}{\sqrt{1-x^2}}\,dx = -\tfrac{1}{2}\int u^{-1/2}\,du = -\sqrt{1-x^2}+C"),

    dict(subject="math_ext1", topic="Projectile motion", difficulty=6,
         latex=r"\text{A ball is launched at } 20\text{ m/s} \text{ at an angle of } 30° \text{ to the horizontal. Find the maximum height and horizontal range.} \\ \text{(Take } g = 10 \text{ m/s}^2\text{)}",
         answer_latex=r"v_y = 20\sin30°=10 \text{ m/s},\quad v_x=20\cos30°=10\sqrt{3} \text{ m/s} \\ H = \frac{v_y^2}{2g} = \frac{100}{20} = 5 \text{ m} \\ T = \frac{2v_y}{g}=2 \text{ s},\quad R = v_x T = 10\sqrt{3}\times2 = 20\sqrt{3} \approx 34.6 \text{ m}"),

    dict(subject="math_ext1", topic="Differential equations", difficulty=6,
         latex=r"\text{Solve the differential equation } \frac{dy}{dx} = \frac{y}{x},\quad y(1)=3.",
         answer_latex=r"\frac{dy}{y}=\frac{dx}{x} \Rightarrow \ln|y|=\ln|x|+C \Rightarrow y=Ax \\ y(1)=3 \Rightarrow A=3 \quad\therefore\quad y=3x"),

    # ── Math Adv ────────────────────────────────────────────────────────────

    dict(subject="math_adv", topic="Calculus", difficulty=3,
         latex=r"\text{Differentiate } y = x^2 e^x.",
         answer_latex=r"\frac{dy}{dx} = 2xe^x + x^2 e^x = xe^x(2+x)"),

    dict(subject="math_adv", topic="Calculus", difficulty=3,
         latex=r"\text{Evaluate } \int_0^2 (3x^2 - 2x + 1)\,dx.",
         answer_latex=r"\left[x^3 - x^2 + x\right]_0^2 = (8-4+2)-0 = 6"),

    dict(subject="math_adv", topic="Calculus", difficulty=4,
         latex=r"\text{Find the area enclosed between } y = x^2 \text{ and } y = x + 2.",
         answer_latex=r"x^2=x+2 \Rightarrow x=-1,2 \\ A=\int_{-1}^{2}(x+2-x^2)\,dx=\left[\frac{x^2}{2}+2x-\frac{x^3}{3}\right]_{-1}^{2}=\frac{9}{2}"),

    dict(subject="math_adv", topic="Exponential and logarithmic functions", difficulty=3,
         latex=r"\text{Differentiate } y = \ln(x^2 + 1).",
         answer_latex=r"\frac{dy}{dx} = \frac{2x}{x^2+1}"),

    dict(subject="math_adv", topic="Exponential and logarithmic functions", difficulty=4,
         latex=r"\text{Solve } 3e^{2x} - 5e^x + 2 = 0.",
         answer_latex=r"\text{Let } u=e^x:\ 3u^2-5u+2=(3u-2)(u-1)=0 \\ u=\tfrac{2}{3} \Rightarrow x=\ln\tfrac{2}{3},\quad u=1 \Rightarrow x=0"),

    dict(subject="math_adv", topic="Financial mathematics", difficulty=4,
         latex=r"\text{Find the present value of an annuity paying \$500 at the end of each year for 10 years at an interest rate of 5\% p.a.}",
         answer_latex=r"PV = 500 \times \frac{1-(1.05)^{-10}}{0.05} = 500 \times 7.7217 \approx \$3860.87"),

    dict(subject="math_adv", topic="Sequences and series", difficulty=3,
         latex=r"\text{The 4th term of an arithmetic sequence is 11 and the 9th term is 26. Find the sum of the first 20 terms.}",
         answer_latex=r"d = \frac{26-11}{9-4}=3,\quad a = 11-3(3)=2 \\ S_{20}=\frac{20}{2}(2\times2+19\times3)=10\times61=610"),

    dict(subject="math_adv", topic="Statistical analysis", difficulty=4,
         latex=r"X \sim N(70, 100). \text{ Find } P(60 < X < 80), \text{ given the 68-95-99.7 rule.}",
         answer_latex=r"\sigma=10,\quad 60 = \mu-\sigma,\quad 80=\mu+\sigma \\ P(60<X<80)=P(\mu-\sigma<X<\mu+\sigma)\approx 0.68"),

    dict(subject="math_adv", topic="Trigonometric functions", difficulty=3,
         latex=r"\text{Find the exact value of } \sin\frac{7\pi}{6}.",
         answer_latex=r"\frac{7\pi}{6} = \pi + \frac{\pi}{6} \Rightarrow \sin\frac{7\pi}{6} = -\sin\frac{\pi}{6} = -\frac{1}{2}"),

    # ── Physics ─────────────────────────────────────────────────────────────

    dict(subject="physics", topic="Kinematics", difficulty=3,
         latex=r"\text{A ball is dropped from rest at a height of 80 m. Taking } g = 9.8 \text{ m/s}^2, \text{ find:} \\ \text{(a) the time to reach the ground} \\ \text{(b) the speed on impact}",
         answer_latex=r"(a)\ h = \tfrac{1}{2}gt^2 \Rightarrow t=\sqrt{\frac{2\times80}{9.8}}\approx4.04 \text{ s} \\ (b)\ v=gt=9.8\times4.04\approx39.6 \text{ m/s}"),

    dict(subject="physics", topic="Kinematics", difficulty=4,
         latex=r"\text{A car accelerates uniformly from } 10 \text{ m/s to } 30 \text{ m/s in } 8 \text{ s.} \\ \text{Find the acceleration and the distance covered.}",
         answer_latex=r"a = \frac{30-10}{8} = 2.5 \text{ m/s}^2 \\ d = \frac{v^2-u^2}{2a}=\frac{900-100}{5}=160 \text{ m}"),

    dict(subject="physics", topic="Dynamics", difficulty=4,
         latex=r"\text{A 5 kg block is pushed along a surface with a force of 30 N. The coefficient of kinetic friction is 0.3. Find the acceleration.} \\ (g = 9.8 \text{ m/s}^2)",
         answer_latex=r"F_f = \mu mg = 0.3\times5\times9.8=14.7 \text{ N} \\ F_{net}=30-14.7=15.3 \text{ N} \\ a=\frac{F_{net}}{m}=\frac{15.3}{5}=3.06 \text{ m/s}^2"),

    dict(subject="physics", topic="Electricity and magnetism", difficulty=3,
         latex=r"\text{Three resistors of } 4\,\Omega,\ 6\,\Omega \text{ and } 12\,\Omega \text{ are connected in parallel across a 12 V supply.} \\ \text{Find the total current drawn from the supply.}",
         answer_latex=r"\frac{1}{R_T}=\frac{1}{4}+\frac{1}{6}+\frac{1}{12}=\frac{3+2+1}{12}=\frac{1}{2} \Rightarrow R_T=2\,\Omega \\ I=\frac{V}{R_T}=\frac{12}{2}=6 \text{ A}"),

    dict(subject="physics", topic="Electricity and magnetism", difficulty=5,
         latex=r"\text{An electron (charge } {-e},\ \text{mass } m_e\text{) moves at } 2\times10^6 \text{ m/s perpendicular to a uniform magnetic field of } 0.5 \text{ T.} \\ \text{Find the radius of its circular orbit.} \\ (e=1.6\times10^{-19}\text{ C},\ m_e=9.11\times10^{-31}\text{ kg})",
         answer_latex=r"qvB=\frac{m_e v^2}{r} \Rightarrow r=\frac{m_e v}{eB}=\frac{9.11\times10^{-31}\times2\times10^6}{1.6\times10^{-19}\times0.5}\approx2.28\times10^{-5}\text{ m}"),

    dict(subject="physics", topic="Advanced mechanics", difficulty=5,
         latex=r"\text{A 0.5 kg ball on a string of length 1.2 m moves in a horizontal circle at 3 revolutions per second.} \\ \text{Find the tension in the string and the angle it makes with the vertical.} \\ (g=9.8 \text{ m/s}^2)",
         answer_latex=r"\omega=2\pi\times3=6\pi \text{ rad/s},\quad v=r\omega \\ T\sin\theta=mr\omega^2,\quad T\cos\theta=mg \\ \tan\theta=\frac{r\omega^2}{g};\quad r=1.2\sin\theta\ \Rightarrow \text{ (solve numerically) }\theta\approx89°,\ T\approx213 \text{ N}"),

    dict(subject="physics", topic="Waves and thermodynamics", difficulty=3,
         latex=r"\text{A string fixed at both ends has length 0.8 m. The speed of waves on the string is 240 m/s.} \\ \text{Find the frequencies of the first three harmonics.}",
         answer_latex=r"f_n = \frac{nv}{2L} \\ f_1=\frac{240}{1.6}=150 \text{ Hz},\quad f_2=300 \text{ Hz},\quad f_3=450 \text{ Hz}"),

    dict(subject="physics", topic="The nature of light", difficulty=4,
         latex=r"\text{Light of wavelength 480 nm strikes a metal with work function 1.8 eV. Find the maximum kinetic energy of the emitted electrons.} \\ (h=6.63\times10^{-34}\text{ J s},\ c=3\times10^8\text{ m/s},\ 1\text{ eV}=1.6\times10^{-19}\text{ J})",
         answer_latex=r"E_{photon}=\frac{hc}{\lambda}=\frac{6.63\times10^{-34}\times3\times10^8}{480\times10^{-9}}\approx4.14\times10^{-19}\text{ J}=2.59\text{ eV} \\ KE_{max}=2.59-1.8=0.79\text{ eV}=1.26\times10^{-19}\text{ J}"),

    dict(subject="physics", topic="From the universe to the atom", difficulty=5,
         latex=r"\text{Calculate the energy released (in MeV) when deuterium and tritium fuse:} \\ {}^2_1\text{H} + {}^3_1\text{H} \to {}^4_2\text{He} + {}^1_0\text{n} \\ \text{Masses: }{}^2\text{H}=2.01410\text{ u},\ {}^3\text{H}=3.01605\text{ u},\ {}^4\text{He}=4.00260\text{ u},\ n=1.00867\text{ u} \\ (1\text{ u} = 931.5\text{ MeV}/c^2)",
         answer_latex=r"\Delta m = (2.01410+3.01605)-(4.00260+1.00867)=0.01888\text{ u} \\ E=0.01888\times931.5\approx17.6\text{ MeV}"),

    # ── Math Ext 1 — Functions (ChatGPT batch) ──────────────────────────────

    dict(subject="math_ext1", topic="Functions", difficulty=2, marks=3,
         marking_guidelines="1 mark completing the square, 1 mark vertex, 1 mark minimum value",
         latex=r"\text{Let } f(x)=x^2-4x+3. \text{ (a) Find the vertex. (b) Hence find the minimum value.}",
         answer_latex=r"f(x)=(x-2)^2-1 \\ \text{Vertex } (2,-1). \quad \text{Minimum value } -1."),

    dict(subject="math_ext1", topic="Functions", difficulty=4, marks=4,
         marking_guidelines="2 marks rearranging, 1 mark solving for x, 1 mark correct inverse",
         latex=r"\text{Find the inverse of } f(x)=\frac{2x+3}{x-1}.",
         answer_latex=r"y=\frac{2x+3}{x-1} \Rightarrow y(x-1)=2x+3 \Rightarrow x(y-2)=y+3 \Rightarrow x=\frac{y+3}{y-2} \\ \therefore f^{-1}(x)=\frac{x+3}{x-2}"),

    dict(subject="math_ext1", topic="Functions", difficulty=5, marks=4,
         marking_guidelines="2 marks setting up inequality, 1 mark solving, 1 mark correct domain",
         latex=r"\text{Determine the domain of } f(x)=\sqrt{\frac{x-1}{x+2}}.",
         answer_latex=r"\text{Require } \frac{x-1}{x+2}\ge0 \text{ and } x\ne -2. \\ \text{Solution: } x\le -2 \text{ or } x\ge 1, \text{ excluding } x=-2 \\ \therefore \text{Domain} = (-\infty,-2)\cup[1,\infty)"),

    dict(subject="math_ext1", topic="Functions", difficulty=5, marks=4,
         marking_guidelines="2 marks expanding f(f(x)), 1 mark solving, 1 mark all answers",
         latex=r"\text{Solve } f(f(x))=0 \text{ for } f(x)=x^2-1.",
         answer_latex=r"f(f(x))=(x^2-1)^2-1=0 \Rightarrow (x^2-1)^2=1 \\ \Rightarrow x^2-1=\pm1 \Rightarrow x^2=2 \text{ or } x^2=0 \\ \therefore x=\pm\sqrt{2},\ 0"),

    dict(subject="math_ext1", topic="Functions", difficulty=3, marks=3,
         marking_guidelines="1 mark correct intercepts, 1 mark parabola shape, 1 mark reflection above x-axis",
         latex=r"\text{Sketch } y=|x^2-4|.",
         answer_latex=r"\text{Start with parabola } y=x^2-4 \text{ (zeros at } x=\pm2\text{).} \\ \text{Reflect the portion below the x-axis upward.} \\ \text{Minimum values occur at } x=\pm2 \ (y=0); \text{ local max at } (0,4)."),

    # ── Math Ext 1 — Trigonometric functions (ChatGPT batch) ────────────────

    dict(subject="math_ext1", topic="Trigonometric functions", difficulty=2, marks=2,
         marking_guidelines="1 mark correct general solution, 1 mark both values in range",
         latex=r"\text{Solve } 2\sin x=1 \text{ for } 0\le x<2\pi.",
         answer_latex=r"\sin x=\frac{1}{2} \Rightarrow x=\frac{\pi}{6},\ \frac{5\pi}{6}"),

    dict(subject="math_ext1", topic="Trigonometric functions", difficulty=2, marks=2,
         marking_guidelines="1 mark unit circle reference, 1 mark conclusion",
         latex=r"\text{Prove } \sin^2 x+\cos^2 x=1.",
         answer_latex=r"\text{On the unit circle, a point at angle } x \text{ has coordinates } (\cos x,\sin x). \\ \text{Since it lies on } X^2+Y^2=1, \text{ we have } \cos^2 x+\sin^2 x=1. \quad \square"),

    dict(subject="math_ext1", topic="Trigonometric functions", difficulty=2, marks=2,
         marking_guidelines="1 mark principal value, 1 mark second solution",
         latex=r"\text{Solve } \tan x=1 \text{ for } 0\le x<2\pi.",
         answer_latex=r"x=\frac{\pi}{4},\ \frac{5\pi}{4}"),

    dict(subject="math_ext1", topic="Trigonometric functions", difficulty=5, marks=4,
         marking_guidelines="1 mark writing 75° as sum, 1 mark applying addition formula, 2 marks correct simplification",
         latex=r"\text{Find the exact value of } \sin 75°.",
         answer_latex=r"\sin 75° = \sin(45°+30°) = \sin45°\cos30°+\cos45°\sin30° \\ = \frac{\sqrt{2}}{2}\cdot\frac{\sqrt{3}}{2}+\frac{\sqrt{2}}{2}\cdot\frac{1}{2} = \frac{\sqrt{6}+\sqrt{2}}{4}"),

    dict(subject="math_ext1", topic="Trigonometric functions", difficulty=1, marks=2,
         marking_guidelines="1 mark correct intercepts and period, 1 mark correct max/min",
         latex=r"\text{Sketch } y=\sin x \text{ for } 0\le x\le 2\pi.",
         answer_latex=r"\text{Zeros at } x=0,\pi,2\pi. \quad \text{Maximum } 1 \text{ at } x=\tfrac{\pi}{2}. \quad \text{Minimum } -1 \text{ at } x=\tfrac{3\pi}{2}."),
]


def run():
    with app.app_context():
        # Create or fetch seed user
        user = User.query.filter_by(username=SEED_USER).first()
        if not user:
            user = User(username=SEED_USER, credits=10_000)
            user.set_password(SEED_PASS)
            db.session.add(user)
            db.session.commit()
            print(f"Created user '{SEED_USER}'.")

        # Collect existing latex strings by this author to skip duplicates
        existing = {q.latex for q in Question.query.filter_by(author_id=user.id).all()}

        added = 0
        for q in QUESTIONS:
            if q["latex"] in existing:
                continue
            question = Question(
                author_id=user.id,
                subject=q["subject"],
                topic=q["topic"],
                difficulty=q["difficulty"],
                latex=q["latex"],
                answer_latex=q["answer_latex"],
                marks=q.get("marks"),
                marking_guidelines=q.get("marking_guidelines"),
            )
            db.session.add(question)
            added += 1

        db.session.commit()
        print(f"Inserted {added} questions ({len(QUESTIONS) - added} already present).")


if __name__ == "__main__":
    run()
