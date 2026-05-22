# ANSWERS.md

## 1. How to run

Requires Python 3.10+ and Node 18+.

**Backend** (terminal 1):

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend** (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). The frontend
uploads log files to the backend at `http://127.0.0.1:8000/api/analyze`.

**Generate test data** (optional):

```bash
python scripts/generate_logs.py --lines 5000 --hours 24 --output logs/test.log
```

---

## 2. Stack choice

**Why FastAPI + React/Vite:**
The task is a file-upload-driven analysis tool that needs to return structured
JSON and render it as a dashboard. FastAPI handles multipart uploads cleanly,
returns typed JSON with minimal boilerplate, and starts with a single command.
React/Vite gives a fast dev loop for building the dashboard UI without a
heavy build pipeline. The combination meant I could move quickly between
parser work and frontend iteration without context-switching between very
different toolchains.

**What would have been worse:**
A monolithic server-rendered approach (e.g. Flask + Jinja2 templates) would
have made the dashboard interactivity harder — every re-render requires a
round trip. On the other end, a full Next.js or Django setup would have added
significant boilerplate for a task that has no database, no auth, and no
persistent state. The stateless file-upload-to-JSON pattern is exactly what a
lightweight API + SPA handles best.

---

## 3. One real edge case

The parser handles stack-trace continuation inside `parse_log_file()` in
`backend/parser.py`. Lines beginning with whitespace or `at ` are attached to
the preceding parsed entry rather than counted independently. Without this, a
three-line stack trace would inflate the malformed count by 3 instead of 1,
and the samples panel would show context-free fragments.

The continuation branch is at line [384](backend/parser.py#L384) and the final
malformed count is assigned at line [449](backend/parser.py#L449).

---

## 4. AI usage

I used AI assistance in two main areas:

**Parser and analyzer logic (GitHub Copilot + chat assistant):**
I used the chat assistant to inspect the parser and analyzer, then draft
updates to the anomaly detection and bucketing logic. The assistant initially
suggested flagging any bare numeric token in a log line as an "alt response
time format" anomaly. I changed this because that approach was overcounting —
it caught numeric path segments, status codes, and port numbers, not just
response times. I rewrote the classifier to only inspect the specific token
position where a response time is expected, which brought the anomaly count
from nearly every line down to the realistic ~5–10% the format variation
actually represents.

**Traffic chart rendering (chat assistant):**
The chart was rendering as a compressed shape in the center of its frame. The
assistant diagnosed this as an aspect ratio problem and suggested changing the
SVG `preserveAspectRatio` attribute to `xMidYMid meet`. I applied it and the
chart got worse — `meet` letterboxes the content to preserve its aspect ratio,
which is correct for images but wrong for a data chart that must fill its
container. I reverted to `preserveAspectRatio="none"` and instead widened the
SVG coordinate space from 100 to 1000 units, giving each of the 60+ data
points enough horizontal resolution for smooth rendering. The assistant was
reasoning from general SVG rules; I knew from seeing the output which
behavior was actually needed.

---

## 5. Honest gap

The parser is heuristic-based and has no automated regression suite. I
improved it iteratively against my own generated logs and a handful of
hand-crafted edge cases, but I cannot prove its behavior across a broad
corpus of real-world log files I have never seen.

With another day, I would write fixture-based tests covering the specific
deviations the spec calls out — quoted user-agent strings with spaces,
mid-file JSON blobs, stack traces of varying depth, bare numeric response
times following a missing status field — and run the parser against each one
with an assertion on the parsed output and anomaly counts. That would give me
confidence that a format combination I didn't think of doesn't silently
produce wrong numbers rather than a visible parse failure.