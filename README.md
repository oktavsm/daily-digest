# daily-digest

A Python script that runs daily via cron, generates a tech digest using AI, commits the output to this repo, and updates a live `/todays` page — keeping the GitHub contribution graph green with meaningful content every day.

**What it generates each day:**
- Top 5 Hacker News stories with AI summaries (Gemini)
- Networking concept of the day with explanation, ASCII diagram & Cisco CLI example
- SVG card for embedding in GitHub profile README
- A full HTML `/todays` page served on your personal site

## 🗓️ Daily Digest
[![Daily Digest](https://oktaavsm.bccdev.id/todays/digest.svg)](https://oktaavsm.bccdev.id/todays)

---

## How It Works

```
cron (daily 23:00)
    └── daily_digest.py
            ├── fetch top 5 HN stories
            ├── Gemini: summarize stories + generate networking concept
            ├── generate SVG card
            ├── generate HTML /todays page → write to web frontend
            ├── generate Markdown file → git commit & push (the streak magic ✅)
            └── notify via Discord / Email
```

Each run creates a `data/YYYY/MM/YYYY-MM-DD.md` file and commits it — that's what keeps the contribution graph green every day.

---

## Requirements

- Python 3.10+
- A Linux server / VM with cron
- A web server serving static files (optional, for the `/todays` page)
- Free API keys: [Google Gemini](https://aistudio.google.com/) (required), [RapidAPI](https://rapidapi.com/) (optional)

---

## Setup

### 1. Clone & install dependencies

```bash
git clone https://github.com/YOUR_USERNAME/daily-digest.git ~/projects/daily-digest
cd ~/projects/daily-digest/script
pip3 install -r requirements.txt --break-system-packages
```

### 2. Configure environment

```bash
cp script/.env.example script/.env
nano script/.env
```

Key variables:

| Variable | Required | Description |
|---|---|---|
| `GEMINI_KEY` | ✅ | Google AI Studio API key |
| `GITHUB_USERNAME` | ✅ | Your GitHub username |
| `GITHUB_TOKEN` | ✅ | Personal access token with `repo` scope |
| `DIGEST_REPO_DIR` | ✅ | Absolute path to this repo on your machine |
| `WEB_FRONTEND_DIR` | optional | Path to your web frontend folder (for `/todays` page) |
| `BASE_URL` | optional | Your domain, e.g. `https://yoursite.com` |
| `DISCORD_WEBHOOK` | optional | Discord webhook URL for daily notifications |
| `EMAIL_FROM` / `EMAIL_TO` / `EMAIL_PASS` | optional | Gmail SMTP credentials |

**GitHub token:** go to github.com → Settings → Developer settings → Personal access tokens → and generate one with `repo` scope.

**Gmail App Password:** Google Account → Security → 2-Step Verification ON → App Passwords → create one.

### 3. Set GitHub remote with token (for push without password prompt)

```bash
cd ~/projects/daily-digest
git remote set-url origin https://YOUR_USERNAME:YOUR_TOKEN@github.com/YOUR_USERNAME/daily-digest.git
```

### 4. Test run

```bash
python3 ~/projects/daily-digest/script/daily_digest.py
```

### 5. Set up cron (runs daily at 23:00)

```bash
mkdir -p ~/projects/daily-digest/logs
crontab -e
```

Add this line:
```
0 23 * * * /usr/bin/python3 /home/YOUR_USER/projects/daily-digest/script/daily_digest.py >> /home/YOUR_USER/projects/daily-digest/logs/cron.log 2>&1
```

### 6. Embed the SVG card in your GitHub profile README

Open `github.com/YOUR_USERNAME/YOUR_USERNAME` → edit `README.md` → add:

```markdown
![Daily Digest](https://YOUR_DOMAIN/todays/digest.svg)
```

---

## Project Structure

```
daily-digest/
├── script/
│   ├── daily_digest.py     ← main script
│   ├── requirements.txt
│   └── .env.example
├── data/
│   └── YYYY/
│       └── MM/
│           └── YYYY-MM-DD.md   ← committed daily (the streak magic)
├── svg/
│   └── latest.svg              ← always overwritten, for GitHub profile
├── logs/                       ← cron output
└── README.md
```

---

## Stack

- **Python 3.12** — no framework, stdlib + `python-dotenv` only
- **Gemini 2.5 Flash** — HN summaries & networking concept generation
- **Hacker News Firebase API** — free, no key needed
- **Discord Webhook** — optional daily notifications
- **Gmail SMTP** — optional email log
- Runs on a VM via **cron job**

---

*Auto-committed daily. Made by [@oktavsm](https://github.com/oktavsm)*
