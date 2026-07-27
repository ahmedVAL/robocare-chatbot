"""
MAILER - envoi d'emails, avec DEUX methodes selon l'environnement :

  1. SMTP classique (Gmail...) - fonctionne en local, mais BLOQUE sur les
     services cloud gratuits comme Render (voir leur changelog : "Free web
     services will no longer allow outbound traffic to SMTP ports").
  2. API HTTP SendGrid - passe par HTTPS (port 443, jamais bloque), donc
     fonctionne sur Render gratuit. Necessite un "Single Sender" verifie
     (aucun acces DNS requis - juste confirmer un email de verification sur
     sendgrid.com). Limite gratuite : 100 emails/jour.

La methode utilisee est choisie automatiquement par chatbot.py selon les
variables presentes dans .env :
  - SENDGRID_API_KEY + SENDGRID_FROM_EMAIL definis -> SendGrid (priorite,
    utilise en production sur Render)
  - sinon SMTP_HOST + SMTP_USER + SMTP_PASSWORD + SMTP_FROM definis -> SMTP
    (utilise en local, ou vous n'avez besoin que d'un compte Gmail)

Ainsi le meme code tourne en local (avec vos identifiants SMTP deja testes)
et sur Render (avec SendGrid), sans rien changer dans le code lui-meme -
seule la config .env differe selon l'environnement.

ATTENTION SECURITE (inchange, s'applique aux deux methodes) :
Ce module permet a un visiteur (via le chatbot) de faire envoyer un email a
une adresse de son choix. C'est un vecteur d'abus classique (spam, phishing,
harcelement) si aucune limite n'est mise. Les protections ci-dessous sont un
MINIMUM pour un usage de test / petite echelle :
  - limite de debit par IP (RATE_LIMIT_MAX_EMAILS par RATE_LIMIT_WINDOW_SECONDS)
  - validation stricte du format d'email
  - objet toujours prefixe pour distinguer ces envois du reste de la boite mail
  - log de chaque tentative (data/email_log.jsonl) pour audit / detection d'abus

Pour une mise en production reelle : rate-limiter partage (Redis), captcha
cote frontend, verification de domaine complete (SPF/DKIM) plutot que Single
Sender, des que vous aurez acces aux DNS de robocare.tn.
"""

import json
import re
import smtplib
import time
from collections import defaultdict
from email.mime.text import MIMEText
from pathlib import Path
from threading import Lock

import requests

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

RATE_LIMIT_MAX_EMAILS = 3
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 heure

SUBJECT_PREFIX = "[Chatbot RoboCare] "
LOG_FILE = Path("data/email_log.jsonl")
SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"

_rate_limit_lock = Lock()
_send_history = defaultdict(list)  # ip -> [timestamps des envois recents]


class EmailSendError(Exception):
    """Erreur explicite renvoyee au chatbot (et donc a l'utilisateur) en cas
    d'echec, pour que le modele puisse expliquer clairement ce qui s'est passe."""
    pass


def _check_rate_limit(sender_ip: str):
    now = time.time()
    with _rate_limit_lock:
        history = _send_history[sender_ip]
        history[:] = [t for t in history if now - t < RATE_LIMIT_WINDOW_SECONDS]
        if len(history) >= RATE_LIMIT_MAX_EMAILS:
            raise EmailSendError(
                f"Limite atteinte : maximum {RATE_LIMIT_MAX_EMAILS} emails "
                f"par heure par visiteur. Reessayez plus tard."
            )
        history.append(now)


def _log_attempt(sender_ip, to_address, subject, success, error=None, method=None):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "sender_ip": sender_ip,
        "to": to_address,
        "subject": subject,
        "method": method,
        "success": success,
        "error": error,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _send_via_smtp(config: dict, to_address: str, full_subject: str, body: str):
    """config attendu : {"host", "port", "user", "password", "from_addr"}"""
    msg = MIMEText(body or "", "plain", "utf-8")
    msg["Subject"] = full_subject
    msg["From"] = config["from_addr"]
    msg["To"] = to_address

    with smtplib.SMTP(config["host"], int(config["port"]), timeout=15) as server:
        server.starttls()
        server.login(config["user"], config["password"])
        server.sendmail(config["from_addr"], [to_address], msg.as_string())


def _send_via_sendgrid(config: dict, to_address: str, full_subject: str, body: str):
    """config attendu : {"api_key", "sender_email"}"""
    payload = {
        "personalizations": [{"to": [{"email": to_address}]}],
        "from": {"email": config["sender_email"]},
        "subject": full_subject,
        "content": [{"type": "text/plain", "value": body or ""}],
    }
    resp = requests.post(
        SENDGRID_API_URL,
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    # SendGrid renvoie 202 Accepted en cas de succes (pas 200)
    if resp.status_code not in (200, 202):
        raise EmailSendError(
            f"SendGrid a refuse l'envoi (code {resp.status_code}) : {resp.text[:200]}"
        )


def send_email(email_config: dict, to_address: str, subject: str, body: str, sender_ip: str = "unknown"):
    """
    email_config attendu, selon la methode :
        SMTP     : {"method": "smtp", "host", "port", "user", "password", "from_addr"}
        SendGrid : {"method": "sendgrid", "api_key", "sender_email"}

    Leve EmailSendError (message clair, prevu pour etre lu par le modele puis
    reformule a l'utilisateur) en cas de probleme : limite atteinte, adresse
    invalide, ou echec technique de l'envoi.
    """
    method = email_config.get("method")
    to_address = (to_address or "").strip()

    if not EMAIL_REGEX.match(to_address):
        _log_attempt(sender_ip, to_address, subject, False, "adresse invalide", method)
        raise EmailSendError(f"L'adresse '{to_address}' n'est pas une adresse email valide.")

    _check_rate_limit(sender_ip)  # leve EmailSendError si depasse (deja logue dedans)

    full_subject = SUBJECT_PREFIX + (subject.strip() if subject else "Message du chatbot")

    try:
        if method == "sendgrid":
            _send_via_sendgrid(email_config, to_address, full_subject, body)
        elif method == "smtp":
            _send_via_smtp(email_config, to_address, full_subject, body)
        else:
            raise EmailSendError("Aucune methode d'envoi d'email configuree.")
    except EmailSendError as e:
        _log_attempt(sender_ip, to_address, subject, False, str(e), method)
        raise
    except Exception as e:
        _log_attempt(sender_ip, to_address, subject, False, str(e), method)
        raise EmailSendError(f"Echec technique de l'envoi ({method}) : {e}")

    _log_attempt(sender_ip, to_address, subject, True, method=method)
    return True
