#!/usr/bin/env python3
"""
daily_digest.py
Auto-generates daily tech digest: Hacker News + Networking Concept
Commits to GitHub, updates /todays page, sends Discord/Email notification.
"""

import os, json, datetime, subprocess, smtplib, textwrap, re, sys
import urllib.request, urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ─── Config ───────────────────────────────────────────────────────────────────
GEMINI_KEY       = os.getenv("GEMINI_KEY")
DISCORD_WEBHOOK  = os.getenv("DISCORD_WEBHOOK")
EMAIL_FROM       = os.getenv("EMAIL_FROM")
EMAIL_TO         = os.getenv("EMAIL_TO")
EMAIL_PASS       = os.getenv("EMAIL_PASS")        # Gmail App Password
SMTP_HOST        = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT        = int(os.getenv("SMTP_PORT", "587"))
GITHUB_USERNAME  = os.getenv("GITHUB_USERNAME", "oktavsm")
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN")
DIGEST_REPO_DIR  = os.getenv("DIGEST_REPO_DIR")  # path to daily-digest repo
WEB_FRONTEND_DIR = os.getenv("WEB_FRONTEND_DIR")  # path to okta-profile/frontend
BASE_URL         = os.getenv("BASE_URL", "https://oktaavsm.bccdev.id")

TODAY    = datetime.date.today()
DATE_STR = TODAY.strftime("%Y-%m-%d")
DATE_NICE= TODAY.strftime("%A, %d %B %Y")

LOGS: list[str] = []

def log(msg: str):
    print(msg)
    LOGS.append(msg)


# ─── HTTP Helper ───────────────────────────────────────────────────────────────
def fetch_json(url: str, headers: dict = {}, data: bytes | None = None) -> dict | list:
    req = urllib.request.Request(url, headers=headers, data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


# ─── 1. Hacker News ──────────────────────────────────────────────────────────
def fetch_hn_stories(n: int = 5) -> list[dict]:
    log("📰 Fetching Hacker News top stories...")
    ids = fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")[:20]
    stories = []
    for sid in ids:
        try:
            item = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
            if item.get("url") and item.get("title"):
                stories.append({
                    "title": item["title"],
                    "url":   item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                    "score": item.get("score", 0),
                    "by":    item.get("by", "unknown"),
                    "comments": item.get("descendants", 0),
                })
                if len(stories) == n:
                    break
        except Exception:
            continue
    log(f"   ✓ Got {len(stories)} stories")
    return stories


# ─── 2. Gemini ────────────────────────────────────────────────────────────────
def call_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    resp = fetch_json(url, headers={"Content-Type": "application/json"}, data=body)
    return resp["candidates"][0]["content"]["parts"][0]["text"].strip()


def generate_hn_summaries(stories: list[dict]) -> list[dict]:
    log("🤖 Gemini: summarizing HN stories...")
    titles = "\n".join(f"{i+1}. {s['title']} — {s['url']}" for i, s in enumerate(stories))
    prompt = f"""Kamu adalah tech writer yang menulis untuk developer Indonesia.
Berikan ringkasan singkat (2-3 kalimat Bahasa Indonesia) untuk masing-masing artikel berikut.
Format output: JSON array, masing-masing objek punya key "index" (int, 1-based) dan "summary" (string).
HANYA output JSON, tanpa markdown backtick.

Artikel:
{titles}"""
    raw = call_gemini(prompt)
    summaries = json.loads(raw)
    for item in summaries:
        idx = item["index"] - 1
        if idx < len(stories):
            stories[idx]["summary"] = item["summary"]
    log("   ✓ Summaries done")
    return stories


def generate_networking_concept() -> dict:
    log("🌐 Gemini: generating networking concept...")
    prompt = f"""Kamu adalah dosen jaringan komputer yang mengajar menggunakan Cisco Packet Tracer.
Hari ini tanggal {DATE_STR}. Generate SATU konsep jaringan komputer untuk dipelajari hari ini.

Output dalam format JSON dengan struktur berikut (HANYA JSON, tanpa markdown backtick):
{{
  "title": "nama konsep (singkat, max 6 kata)",
  "category": "salah satu dari: Routing | Switching | Security | Protocol | Wireless | IoT | SDN",
  "tldr": "penjelasan 1 kalimat yang sangat ringkas",
  "explanation": "penjelasan 3-4 paragraf dalam Bahasa Indonesia, teknikal tapi mudah dipahami",
  "ascii_diagram": "diagram ASCII yang relevan (max 10 baris), atau kosong string jika tidak relevan",
  "cisco_command": "contoh 1 perintah CLI Cisco yang paling relevan, atau kosong string jika tidak ada",
  "fun_fact": "1 fakta menarik seputar konsep ini (1-2 kalimat)"
}}"""
    raw = call_gemini(prompt)
    concept = json.loads(raw)
    log(f"   ✓ Concept: {concept['title']}")
    return concept


# ─── 3. Generate SVG ─────────────────────────────────────────────────────────
def generate_svg(stories: list[dict], concept: dict) -> str:
    def trunc(s: str, n: int) -> str:
        s = s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')
        return s if len(s) <= n else s[:n-1] + "…"

    story_rows = ""
    for i, s in enumerate(stories[:4]):
        y_title = 104 + i * 38
        y_meta  = y_title + 15
        story_rows += f'''
  <text x="32" y="{y_title}" class="st">{trunc(s['title'], 60)}</text>
  <text x="32" y="{y_meta}" class="sm">▲ {s['score']}  💬 {s['comments']}  by {trunc(s['by'], 16)}</text>'''

    divider_y   = 252
    net_label_y = divider_y + 24
    badge_y     = net_label_y + 14
    title_y     = badge_y + 30
    tldr_y      = title_y + 20
    cmd_y       = tldr_y + 28

    concept_title = trunc(concept["title"], 46)
    concept_tldr  = trunc(concept["tldr"], 70)
    concept_cat   = concept["category"]
    badge_w       = max(len(concept_cat) * 7 + 20, 60)

    cmd = trunc(concept.get("cisco_command", ""), 54)
    cmd_block = ""
    if cmd:
        cmd_block = f'''
  <rect x="20" y="{cmd_y}" width="560" height="26" rx="5" fill="#1c2128"/>
  <text x="32" y="{cmd_y+17}" class="ct">$ {cmd}</text>'''
        fun_y = cmd_y + 44
    else:
        fun_y = cmd_y + 10

    import textwrap
    fun_lines = textwrap.fill(concept.get("fun_fact",""), 78).split("\n")[:2]
    fun_text = ""
    for line in fun_lines:
        fun_text += f'\n  <text x="32" y="{fun_y}" class="ff">{trunc(line,80)}</text>'
        fun_y += 16

    total_h  = fun_y + 36
    footer_y = total_h - 28
    import os, datetime
    DATE_STR = datetime.date.today().strftime("%Y-%m-%d")
    GITHUB_USERNAME = os.getenv("GITHUB_USERNAME","oktavsm")
    BASE_URL = os.getenv("BASE_URL","https://oktaavsm.bccdev.id")

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="{total_h}" viewBox="0 0 600 {total_h}">
  <defs><style>
    .bg{{fill:#0d1117}}.lb{{font:700 9px monospace;fill:#484f58;letter-spacing:1.5px}}
    .st{{font:500 11px monospace;fill:#cdd9e5}}.sm{{font:400 9px monospace;fill:#484f58}}
    .ct{{font:700 11px monospace;fill:#39d353}}.ff{{font:400 10px monospace;fill:#6e7681;font-style:italic}}
    .dt{{font:700 10px monospace;fill:#484f58}}.cttl{{font:700 14px monospace;fill:#39d353}}
    .ctldr{{font:400 10px monospace;fill:#8b949e}}.cbadge{{font:700 9px monospace;fill:#0d1117}}
  </style></defs>
  <rect width="600" height="{total_h}" class="bg"/>
  <rect width="600" height="46" fill="#161b22"/>
  <rect y="46" width="600" height="1" fill="#30363d"/>
  <circle cx="18" cy="23" r="5" fill="#ff5f56"/>
  <circle cx="34" cy="23" r="5" fill="#ffbd2e"/>
  <circle cx="50" cy="23" r="5" fill="#27c93f"/>
  <text x="70" y="28" class="dt">daily-digest // {DATE_STR}</text>
  <text x="590" y="28" class="dt" text-anchor="end">@{GITHUB_USERNAME}</text>
  <text x="32" y="74" class="lb">// HACKER NEWS TOP STORIES</text>
  <rect x="20" y="82" width="2" height="148" fill="#39d353" opacity="0.5"/>
  {story_rows}
  <rect x="0" y="{divider_y}" width="600" height="1" fill="#21262d"/>
  <text x="32" y="{net_label_y}" class="lb">// NETWORKING CONCEPT OF THE DAY</text>
  <rect x="20" y="{badge_y}" width="{badge_w}" height="17" rx="8" fill="#2ea043"/>
  <text x="{20+badge_w//2}" y="{badge_y+12}" class="cbadge" text-anchor="middle">{concept_cat}</text>
  <text x="20" y="{title_y}" class="cttl">{concept_title}</text>
  <text x="20" y="{tldr_y}" class="ctldr">{concept_tldr}</text>
  {cmd_block}
  {fun_text}
  <rect y="{footer_y-1}" width="600" height="1" fill="#21262d"/>
  <rect y="{footer_y}" width="600" height="28" fill="#161b22"/>
  <text x="20" y="{footer_y+18}" class="dt">auto-generated by daily-digest</text>
  <text x="590" y="{footer_y+18}" class="dt" text-anchor="end">{BASE_URL}/todays</text>
</svg>'''

# ─── 4. Generate HTML /todays ─────────────────────────────────────────────────
def generate_html(stories: list[dict], concept: dict) -> str:
    story_cards = ""
    for s in stories:
        summary = s.get("summary", "")
        story_cards += f"""
        <article class="story-card">
          <a href="{s['url']}" target="_blank" rel="noopener" class="story-link">
            <h3>{s['title']}</h3>
          </a>
          <div class="story-meta">
            <span class="score">▲ {s['score']}</span>
            <span class="sep">·</span>
            <span>💬 {s['comments']} comments</span>
            <span class="sep">·</span>
            <span>by {s['by']}</span>
          </div>
          {f'<p class="summary">{summary}</p>' if summary else ''}
        </article>"""

    ascii_block = ""
    if concept.get("ascii_diagram"):
        ascii_block = f'<pre class="ascii">{concept["ascii_diagram"]}</pre>'

    cmd_block = ""
    if concept.get("cisco_command"):
        cmd_block = f'<div class="cmd-block"><span class="prompt">$</span> {concept["cisco_command"]}</div>'

    explanation_html = "".join(
        f"<p>{p.strip()}</p>"
        for p in concept["explanation"].split("\n")
        if p.strip()
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Today's Digest · {DATE_STR}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@700;800&display=swap"/>
  <style>
    :root {{
      --bg: #0d1117;
      --surface: #161b22;
      --surface2: #1c2128;
      --border: #30363d;
      --text: #e6edf3;
      --text-muted: #8b949e;
      --text-dim: #484f58;
      --green: #39d353;
      --green-dim: #2ea043;
      --orange: #d29922;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: 'JetBrains Mono', monospace;
      min-height: 100vh;
      padding: 0 16px 80px;
    }}

    /* Top bar */
    .topbar {{
      position: sticky; top: 0; z-index: 10;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 14px 24px;
      display: flex; align-items: center; justify-content: space-between;
    }}
    .topbar-dots {{ display: flex; gap: 8px; }}
    .dot {{ width: 12px; height: 12px; border-radius: 50%; }}
    .dot.red {{ background: #ff5f56; }}
    .dot.yellow {{ background: #ffbd2e; }}
    .dot.green {{ background: #27c93f; }}
    .topbar-title {{ font: 700 13px 'JetBrains Mono', monospace; color: var(--text-dim); }}
    .topbar-date {{ font: 500 12px 'JetBrains Mono', monospace; color: var(--green); }}

    /* Layout */
    .container {{ max-width: 860px; margin: 0 auto; padding-top: 48px; }}

    /* Hero */
    .hero {{ margin-bottom: 56px; }}
    .hero-label {{
      font: 700 11px 'JetBrains Mono', monospace;
      color: var(--green);
      letter-spacing: 3px;
      text-transform: uppercase;
      margin-bottom: 12px;
    }}
    .hero-title {{
      font: 800 48px 'Syne', sans-serif;
      line-height: 1.05;
      color: var(--text);
    }}
    .hero-title span {{ color: var(--green); }}
    .hero-sub {{
      margin-top: 16px;
      font: 400 13px 'JetBrains Mono', monospace;
      color: var(--text-muted);
      line-height: 1.8;
    }}

    /* Section header */
    .section-header {{
      display: flex; align-items: center; gap: 12px;
      margin-bottom: 24px;
    }}
    .section-label {{
      font: 700 10px 'JetBrains Mono', monospace;
      color: var(--text-dim);
      letter-spacing: 2px;
      text-transform: uppercase;
    }}
    .section-line {{ flex: 1; height: 1px; background: var(--border); }}

    /* Story cards */
    .stories {{ display: flex; flex-direction: column; gap: 2px; margin-bottom: 64px; }}
    .story-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px 24px;
      transition: border-color .2s, background .2s;
      position: relative;
    }}
    .story-card:hover {{ border-color: var(--green-dim); background: var(--surface2); }}
    .story-card::before {{
      content: '';
      position: absolute; left: 0; top: 0; bottom: 0;
      width: 3px;
      background: var(--green);
      border-radius: 8px 0 0 8px;
      opacity: 0;
      transition: opacity .2s;
    }}
    .story-card:hover::before {{ opacity: 1; }}
    .story-link {{ text-decoration: none; }}
    .story-link h3 {{
      font: 700 14px 'Syne', sans-serif;
      color: var(--text);
      line-height: 1.5;
      transition: color .2s;
    }}
    .story-link:hover h3 {{ color: var(--green); }}
    .story-meta {{
      margin-top: 8px;
      font: 400 11px 'JetBrains Mono', monospace;
      color: var(--text-dim);
      display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
    }}
    .score {{ color: var(--orange); }}
    .sep {{ color: var(--border); }}
    .summary {{
      margin-top: 12px;
      font: 400 12px 'JetBrains Mono', monospace;
      color: var(--text-muted);
      line-height: 1.8;
      border-left: 2px solid var(--border);
      padding-left: 12px;
    }}

    /* Concept section */
    .concept-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      margin-bottom: 64px;
    }}
    .concept-header {{
      background: var(--surface2);
      border-bottom: 1px solid var(--border);
      padding: 20px 24px;
      display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
    }}
    .concept-title-wrap {{ display: flex; flex-direction: column; gap: 4px; }}
    .badge {{
      display: inline-block;
      background: var(--green-dim);
      color: #0d1117;
      font: 700 9px 'JetBrains Mono', monospace;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      padding: 3px 10px;
      border-radius: 99px;
      margin-bottom: 6px;
    }}
    .concept-title-text {{
      font: 800 22px 'Syne', sans-serif;
      color: var(--green);
      line-height: 1.2;
    }}
    .concept-tldr-text {{
      font: 400 12px 'JetBrains Mono', monospace;
      color: var(--text-muted);
      max-width: 500px;
    }}
    .concept-body {{ padding: 28px 24px; display: flex; flex-direction: column; gap: 20px; }}
    .concept-body p {{
      font: 400 13px 'JetBrains Mono', monospace;
      color: var(--text-muted);
      line-height: 2;
    }}
    .ascii {{
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px 20px;
      font: 400 12px 'JetBrains Mono', monospace;
      color: var(--green);
      overflow-x: auto;
      line-height: 1.6;
    }}
    .cmd-block {{
      background: var(--bg);
      border: 1px solid var(--green-dim);
      border-radius: 8px;
      padding: 14px 20px;
      font: 700 13px 'JetBrains Mono', monospace;
      color: var(--green);
    }}
    .prompt {{ color: var(--text-dim); margin-right: 10px; }}
    .fun-fact-block {{
      border-top: 1px solid var(--border);
      padding-top: 20px;
      font: 400 12px 'JetBrains Mono', monospace;
      color: var(--text-dim);
      font-style: italic;
      line-height: 1.8;
    }}
    .fun-fact-block::before {{ content: '💡 '; font-style: normal; }}

    /* SVG embed section */
    .svg-section {{ margin-bottom: 64px; }}
    .svg-preview {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      text-align: center;
    }}
    .svg-preview img {{ max-width: 100%; border-radius: 8px; }}
    .svg-copy {{
      margin-top: 16px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 16px;
      font: 400 12px 'JetBrains Mono', monospace;
      color: var(--text-muted);
      text-align: left;
      cursor: pointer;
      transition: border-color .2s;
    }}
    .svg-copy:hover {{ border-color: var(--green); color: var(--text); }}

    /* Footer */
    footer {{
      border-top: 1px solid var(--border);
      padding: 32px 0;
      font: 400 11px 'JetBrains Mono', monospace;
      color: var(--text-dim);
      display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;
    }}

    @media (max-width: 600px) {{
      .hero-title {{ font-size: 32px; }}
      .topbar-date {{ display: none; }}
    }}
  </style>
</head>
<body>

<nav class="topbar">
  <div class="topbar-dots">
    <div class="dot red"></div>
    <div class="dot yellow"></div>
    <div class="dot green"></div>
  </div>
  <div class="topbar-title">daily-digest // {DATE_STR}</div>
  <div class="topbar-date">@{GITHUB_USERNAME}</div>
</nav>

<div class="container">

  <header class="hero">
    <div class="hero-label">// daily digest</div>
    <h1 class="hero-title">Today's<br/><span>Tech Brief.</span></h1>
    <p class="hero-sub">
      {DATE_NICE}<br/>
      Auto-generated · Hacker News + Networking Concept · Powered by Gemini
    </p>
  </header>

  <!-- HN Stories -->
  <section>
    <div class="section-header">
      <span class="section-label">// hacker news</span>
      <div class="section-line"></div>
    </div>
    <div class="stories">
      {story_cards}
    </div>
  </section>

  <!-- Networking Concept -->
  <section>
    <div class="section-header">
      <span class="section-label">// networking concept of the day</span>
      <div class="section-line"></div>
    </div>
    <div class="concept-card">
      <div class="concept-header">
        <div class="concept-title-wrap">
          <span class="badge">{concept['category']}</span>
          <div class="concept-title-text">{concept['title']}</div>
        </div>
        <div class="concept-tldr-text">{concept['tldr']}</div>
      </div>
      <div class="concept-body">
        {explanation_html}
        {ascii_block}
        {cmd_block}
        <div class="fun-fact-block">{concept.get('fun_fact','')}</div>
      </div>
    </div>
  </section>

  <!-- SVG Card -->
  <section class="svg-section">
    <div class="section-header">
      <span class="section-label">// github profile card</span>
      <div class="section-line"></div>
    </div>
    <div class="svg-preview">
      <img src="{BASE_URL}/todays/digest.svg?v={int(datetime.date.today().strftime("%Y%m%d"))}" alt="Daily Digest Card"/>
      <div class="svg-copy" onclick="navigator.clipboard.writeText(this.dataset.md).then(()=>this.textContent='✓ Copied!');" 
           data-md="![Daily Digest]({BASE_URL}/todays/digest.svg)">
        ![Daily Digest]({BASE_URL}/todays/digest.svg) &nbsp;← click to copy markdown
      </div>
    </div>
  </section>

</div>

<footer>
  <span>auto-generated by daily-digest · <a href="https://github.com/{GITHUB_USERNAME}/daily-digest" style="color:var(--green);text-decoration:none">github.com/{GITHUB_USERNAME}/daily-digest</a></span>
  <span>data: hacker-news api + gemini</span>
</footer>

</body>
</html>"""


# ─── 5. Generate Markdown (for git commit) ───────────────────────────────────
def generate_markdown(stories: list[dict], concept: dict) -> str:
    stories_md = ""
    for i, s in enumerate(stories, 1):
        summary = s.get("summary", "")
        stories_md += f"""
### {i}. [{s['title']}]({s['url']})
**▲ {s['score']} · 💬 {s['comments']} comments · by {s['by']}**
{summary}
"""

    ascii_block = ""
    if concept.get("ascii_diagram"):
        ascii_block = f"```\n{concept['ascii_diagram']}\n```"

    cmd_block = ""
    if concept.get("cisco_command"):
        cmd_block = f"```\n{concept['cisco_command']}\n```"

    return f"""# Daily Digest — {DATE_NICE}

> Auto-generated by [daily-digest](https://github.com/{GITHUB_USERNAME}/daily-digest)

---

## 📰 Hacker News Top Stories
{stories_md}

---

## 🌐 Networking Concept: {concept['title']}

**Category:** {concept['category']}
**TL;DR:** {concept['tldr']}

{concept['explanation']}

{ascii_block}

{f"**Cisco CLI:**{chr(10)}{cmd_block}" if cmd_block else ""}

💡 **Fun Fact:** {concept.get('fun_fact','')}
"""


# ─── 6. Git commit & push ─────────────────────────────────────────────────────
def git_commit_push(repo_dir: str, md_content: str, svg_content: str):
    log("📦 Committing to daily-digest repo...")
    repo = Path(repo_dir)

    # Write markdown
    date_dir = repo / "data" / str(TODAY.year) / f"{TODAY.month:02d}"
    date_dir.mkdir(parents=True, exist_ok=True)
    md_file = date_dir / f"{DATE_STR}.md"
    md_file.write_text(md_content)

    # Write SVG
    svg_dir = repo / "svg"
    svg_dir.mkdir(exist_ok=True)
    (svg_dir / "latest.svg").write_text(svg_content)

    def git(*args):
        result = subprocess.run(
            ["git", "-C", str(repo)] + list(args),
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout.strip()

    git("add", "-A")
    git("commit", "-m", f"feat: daily digest {DATE_STR} 🌿")
    git("push")
    log(f"   ✓ Committed: {md_file.name}")


# ─── 7. Write frontend /todays ───────────────────────────────────────────────
def write_frontend(html: str, svg: str):
    if not WEB_FRONTEND_DIR:
        log("⚠️  WEB_FRONTEND_DIR not set, skipping frontend update")
        return
    todays = Path(WEB_FRONTEND_DIR) / "todays"
    todays.mkdir(exist_ok=True)
    (todays / "index.html").write_text(html)
    (todays / "digest.svg").write_text(svg)
    log(f"   ✓ Frontend updated: {todays}")


# ─── 8. Discord Notification ─────────────────────────────────────────────────
def notify_discord(stories: list[dict], concept: dict, success: bool):
    if not DISCORD_WEBHOOK:
        return
    status = "✅ Success" if success else "❌ Failed"
    top_story = stories[0]['title'] if stories else "—"
    payload = {
        "embeds": [{
            "title": f"{status} · Daily Digest {DATE_STR}",
            "color": 0x39d353 if success else 0xff5f56,
            "fields": [
                {"name": "🌐 Concept", "value": concept.get('title','—'), "inline": True},
                {"name": "📰 Top Story", "value": top_story[:100], "inline": False},
                {"name": "🔗 View", "value": f"{BASE_URL}/todays", "inline": False},
            ],
            "footer": {"text": "daily-digest auto-commit"},
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }]
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(DISCORD_WEBHOOK, data=data, headers={"Content-Type": "application/json", "User-Agent": "DiscordBot (daily-digest, 1.0)"})
    urllib.request.urlopen(req, timeout=10)
    log("   ✓ Discord notified")


# ─── 9. Email Notification ────────────────────────────────────────────────────
def notify_email(stories: list[dict], concept: dict, success: bool):
    if not all([EMAIL_FROM, EMAIL_TO, EMAIL_PASS]):
        return
    status = "✅ Success" if success else "❌ Failed"
    subject = f"[Daily Digest] {status} · {DATE_STR}"
    log_text = "\n".join(LOGS)
    body = f"Daily Digest — {DATE_STR}\n\nStatus: {status}\nConcept: {concept.get('title','—')}\n\nLog:\n{log_text}\n\nView: {BASE_URL}/todays"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(EMAIL_FROM, EMAIL_PASS)
        s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    log("   ✓ Email sent")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    log(f"🚀 Daily Digest starting — {DATE_STR}")
    success = False
    stories, concept = [], {}
    try:
        stories = fetch_hn_stories(5)
        stories = generate_hn_summaries(stories)
        concept = generate_networking_concept()

        svg  = generate_svg(stories, concept)
        html = generate_html(stories, concept)
        md   = generate_markdown(stories, concept)

        write_frontend(html, svg)

        if DIGEST_REPO_DIR:
            git_commit_push(DIGEST_REPO_DIR, md, svg)
        else:
            log("⚠️  DIGEST_REPO_DIR not set, skipping git commit")

        success = True
        log("✅ All done!")
    except Exception as e:
        log(f"❌ Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        try: notify_discord(stories, concept, success)
        except Exception as e: log(f"⚠️  Discord notify failed: {e}")
        try: notify_email(stories, concept, success)
        except Exception as e: log(f"⚠️  Email notify failed: {e}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()