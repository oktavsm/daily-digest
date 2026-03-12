# 🌿 daily-digest

Auto-generates a daily tech digest committed to this repo every night.
- **Hacker News** top stories + AI summary (Gemini)
- **Networking Concept** of the day (Gemini)
- **SVG card** for GitHub profile README
- Live at: [oktaavsm.bccdev.id/todays](https://oktaavsm.bccdev.id/todays)

![Daily Digest](https://oktaavsm.bccdev.id/todays/digest.svg)

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/daily-digest.git ~/projects/daily-digest
cd ~/projects/daily-digest/script
pip3 install -r requirements.txt --break-system-packages
```

### 2. Configure

```bash
cp .env.example .env
nano .env   # isi semua variable
```

**GitHub token** perlu scope: `repo` (untuk push).

**Gmail App Password**: Google Account → Security → 2FA ON → App Passwords → buat baru.

### 3. Setup GitHub remote (HTTPS + token)

```bash
cd ~/projects/daily-digest
git remote set-url origin https://YOUR_USERNAME:YOUR_TOKEN@github.com/YOUR_USERNAME/daily-digest.git
```

### 4. Test manual

```bash
python3 ~/projects/daily-digest/script/daily_digest.py
```

### 5. Setup cron (auto tiap hari jam 23:00)

```bash
crontab -e
```

Tambahkan:
```
0 23 * * * /usr/bin/python3 /home/dev/projects/daily-digest/script/daily_digest.py >> /home/dev/projects/daily-digest/logs/cron.log 2>&1
```

Buat folder log:
```bash
mkdir -p ~/projects/daily-digest/logs
```

### 6. Embed di GitHub Profile README

```markdown
![Daily Digest](https://oktaavsm.bccdev.id/todays/digest.svg)
```

---

## Embed ke GitHub Profile Readme kamu

Buka `github.com/YOUR_USERNAME/YOUR_USERNAME` → edit `README.md` → tambahkan badge di atas.

---

## Project Structure

```
daily-digest/
├── script/
│   ├── daily_digest.py   ← main script
│   ├── requirements.txt
│   └── .env.example
├── data/
│   └── YYYY/MM/
│       └── YYYY-MM-DD.md ← generated daily (ini yang bikin streak!)
├── svg/
│   └── latest.svg        ← selalu overwrite, untuk GitHub profile
├── logs/                 ← cron output logs
└── README.md
```

---

## Stack

- **Python 3.12** — no framework, stdlib only + `python-dotenv`
- **Gemini 2.0 Flash** — content generation
- **Hacker News Firebase API** — gratis, no key needed
- **Discord Webhook** — notifikasi harian
- **Gmail SMTP** — email log
- Berjalan di VM via **cron job**

---

*Auto-committed daily. Made with 🌿 by [@oktavsm](https://github.com/oktavsm)*
