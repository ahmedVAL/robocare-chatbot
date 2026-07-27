import json
import os
import re
import smtplib
import ssl
import time
from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

load_dotenv()

# ==========================
# Configuration SMTP
# ==========================

SMTP_SERVER = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("EMAIL_FROM", SMTP_USERNAME)

# ==========================
# Vérification
# ==========================

if not SMTP_USER:
    raise RuntimeError("SMTP_USERNAME est introuvable.")

if not SMTP_PASSWORD:
    raise RuntimeError("SMTP_PASSWORD est introuvable.")

# ==========================
# Sécurité
# ==========================

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

RATE_LIMIT_MAX_EMAILS = 3
RATE_LIMIT_WINDOW_SECONDS = 3600

SUBJECT_PREFIX = "[Chatbot RoboCare] "

LOG_FILE = Path("data/email_log.jsonl")
LOG_FILE.parent.mkdir(exist_ok=True)

_rate_limit_lock = Lock()
_rate_limit = defaultdict(list)
