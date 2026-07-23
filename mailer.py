"""
MAILER - envoi d'emails via SMTP, avec garde-fous anti-abus.

ATTENTION SECURITE :
Ce module permet a un visiteur (via le chatbot) de faire envoyer un email a
une adresse de son choix. C'est un vecteur d'abus classique (spam, phishing,
harcelement) si aucune limite n'est mise. Les protections ci-dessous sont un
MINIMUM pour un usage de test / petite echelle :
  - limite de debit par IP (RATE_LIMIT_MAX_EMAILS par RATE_LIMIT_WINDOW_SECONDS)
  - validation stricte du format d'email
  - objet toujours prefixe pour distinguer ces envois du reste de la boite mail
  - log de chaque tentative (data/email_log.jsonl) pour audit / detection d'abus

Pour une mise en production reelle, il faudra en plus :
  - remplacer le rate-limiter en memoire par un systeme partage (Redis), car
    celui-ci se reinitialise a chaque redemarrage du serveur et ne fonctionne
    pas si vous avez plusieurs processus/serveurs
  - ajouter un captcha cote frontend (Streamlit/site) avant meme d'atteindre
    ce module
  - envisager une confirmation humaine avant l'envoi reel pour les destinataires
    hors domaine de l'entreprise
"""

import json
import re
import smtplib
import time
from collections import defaultdict
from email.mime.text import MIMEText
from pathlib import Path
from threading import Lock

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

RATE_LIMIT_MAX_EMAILS = 3
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 heure

SUBJECT_PREFIX = "[Chatbot RoboCare] "
LOG_FILE = Path("data/email_log.jsonl")

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


def _log_attempt(sender_ip, to_address, subject, success, error=None):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "sender_ip": sender_ip,
        "to": to_address,
        "subject": subject,
        "success": success,
        "error": error,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def send_email(smtp_config: dict, to_address: str, subject: str, body: str, sender_ip: str = "unknown"):
    """
    smtp_config attendu :
        {"host": ..., "port": ..., "user": ..., "password": ..., "from_addr": ...}

    Leve EmailSendError (avec un message clair, prevu pour etre lu par le
    modele puis reformule a l'utilisateur) en cas de probleme : limite
    atteinte, adresse invalide, ou echec technique de l'envoi.
    """
    to_address = (to_address or "").strip()
    if not EMAIL_REGEX.match(to_address):
        _log_attempt(sender_ip, to_address, subject, False, "adresse invalide")
        raise EmailSendError(f"L'adresse '{to_address}' n'est pas une adresse email valide.")

    _check_rate_limit(sender_ip)  # leve EmailSendError si depasse (deja logue dedans)

    full_subject = SUBJECT_PREFIX + (subject.strip() if subject else "Message du chatbot")
    msg = MIMEText(body or "", "plain", "utf-8")
    msg["Subject"] = full_subject
    msg["From"] = smtp_config["from_addr"]
    msg["To"] = to_address

    try:
        with smtplib.SMTP(smtp_config["host"], int(smtp_config["port"]), timeout=15) as server:
            server.starttls()
            server.login(smtp_config["user"], smtp_config["password"])
            server.sendmail(smtp_config["from_addr"], [to_address], msg.as_string())
    except Exception as e:
        _log_attempt(sender_ip, to_address, subject, False, str(e))
        raise EmailSendError(f"Echec technique de l'envoi : {e}")

    _log_attempt(sender_ip, to_address, subject, True)
    return True