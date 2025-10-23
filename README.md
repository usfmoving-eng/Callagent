USF Moving Company AI Voice Assistant

Overview

This is a Flask-based Twilio Voice/SMS assistant that collects moving job details, estimates pricing, books jobs into Google Sheets, and emails the manager upon booking. It also supports outbound calls for website leads.

Features

- IVR with Twilio Voice (press 0 to transfer to manager)
- Collects ZIPs, rooms, stairs, date/time, confirms time before proceeding
- Estimates price using distance and job details
- Saves bookings/leads to Google Sheets
- Emails manager on confirmed bookings (no post-booking SMS collection)
- SMS endpoint to update addresses (optional)

Quick start (local)

1) Install Python 3.10+ and pip.
2) Install dependencies:

	pip install -r requirements.txt

3) Create a .env file (see Environment variables below).
4) Run the app:

	python app.py

5) Expose locally via ngrok (for Twilio webhooks):

	ngrok http 5000

6) Configure your Twilio number webhooks:
	- Voice: https://<ngrok>/voice/inbound (HTTP POST)
	- Messaging: https://<ngrok>/sms/incoming (HTTP POST)
	- Status callback (optional): https://<ngrok>/voice/status

Environment variables (.env)

- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_PHONE_NUMBER
- GOOGLE_MAPS_API_KEY
- BOOKING_SHEET_ID
- GOOGLE_SHEETS_CREDS (entire service-account JSON on one line)
- EMAIL_ADDRESS
- EMAIL_PASSWORD (Gmail app password recommended; no spaces)
- SMTP_SERVER=smtp.gmail.com
- SMTP_PORT=587
- MANAGER_EMAIL
- Optional: FLASK_ENV=production, ENABLE_EMAIL_NOTIFICATIONS=True, ENABLE_SMS_NOTIFICATIONS=True, PORT=5000

Production deploy (Render)

1) Push to GitHub (see section below).
2) Create a new Web Service on Render, connect the repo.
3) Environment: Python 3.x
4) Build command: pip install -r requirements.txt
5) Start command: gunicorn app:app --bind 0.0.0.0:$PORT
6) Add the same environment variables in Render.
7) Point your Twilio webhooks to https://<your-service>.onrender.com/voice/inbound and /sms/incoming.

Pushing to GitHub (PowerShell)

If this folder is not a git repo yet:

1) Initialize and create initial commit:

	git init
	git add .
	git commit -m "Initial commit: USF Moving AI Assistant"
	git branch -M main

2) Create a new empty repo on GitHub (via web UI), e.g. https://github.com/<your-user>/<repo>

3) Add the remote and push:

	git remote add origin https://github.com/<your-user>/<repo>.git
	git push -u origin main

If the repo is already initialized:

- Check remotes:

	git remote -v

- Update origin if needed:

	git remote set-url origin https://github.com/<your-user>/<repo>.git

- Commit and push changes:

	git add .
	git commit -m "Update"
	git push

Security notes

- .gitignore already excludes .env, logs/, __pycache__/ and other local artifacts. Never commit .env contents.
- Share your Google Sheet with the service-account email from GOOGLE_SHEETS_CREDS.
- For Gmail SMTP, use an app password and keep it out of the repo.

