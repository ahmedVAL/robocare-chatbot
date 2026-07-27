"""
MAILER - envoi d'emails via l'API HTTP de SendGrid (pas de SMTP).

POURQUOI L'API HTTP ET NON SMTP :
Beaucoup d'hebergeurs cloud gratuits (Render inclus, depuis fin 2025) bloquent
le trafic sortant vers les ports SMTP (25, 465, 587) pour limiter les abus
(voir https://render.com/changelog - "Free web services will no longer allow
outbound traffic to SMTP ports"). L'API SendGrid passe par HTTPS (port 443,
jamais bloque), donc ca fonctionne sur les plans gratuits.

SendGrid necessite un "Single Sender" verifie : une adresse email dont vous
confirmez la propriete via un lien recu par email (sur sendgrid.com :
Settings > Sender Authentication > Single Sender Verification). Ca ne
necessite AUCUN acces DNS - contrairement a la verification de domaine
complete, qui est recommandee plus tard pour une meilleure delivrabilite
mais pas obligatoire pour demarrer. Limite gratuite : 100 emails/jour.

ATTENTION SECURITE (inchange depuis la version SMTP) :
Ce module permet a un visiteur (via le chatbot) de faire envoyer un email a
une adresse de son choix. C'est un vecteur d'abus classique (spam, phishing,
harcelement) si aucune limite n'est mise. Les protections ci-dessous sont un
MINIMUM pour un usage de test / petite echelle :
  - limite de debit par IP (RATE_LIMIT_MAX_EMAILS par RATE_LIMIT_WINDOW_SECONDS)
  - validation stricte du format d'email
  - objet toujours prefixe pour distinguer ces envois du reste de la boite mail
  - log de chaque tentative (data/email_log.jsonl) pour audit / detection d'abus

Pour une mise en production reelle, il faudra en plus :
  - remplacer le rate-limiter en memoire par un systeme partage (Redis)
  - ajouter un captcha cote frontend avant meme d'atteindre ce module
  - passer a une verification de domaine complete (SPF/DKIM) pour la
    delivrabilite, une fois que vous aurez acces aux DNS de robocare.tn
"""

import json
import re
import time
from collections import defaultdict
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


def send_email(email_config: dict, to_address: str, subject: str, body: str, sender_ip: str = "unknown"):
    """
    email_config attendu :
        {"api_key": "SG.xxxx", "sender_email": "verified@robocare.tn"}
    (sender_email doit etre l'adresse verifiee via Single Sender Verification
    sur le dashboard SendGrid)

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

    payload = {
        "personalizations": [{"to": [{"email": to_address}]}],
        "from": {"email": email_config["sender_email"]},
        "subject": full_subject,
        "content": [{"type": "text/plain", "value": body or ""}],
    }

    try:
        resp = requests.post(
            SENDGRID_API_URL,
            headers={
                "Authorization": f"Bearer {email_config['api_key']}",
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
    except requests.RequestException as e:
        _log_attempt(sender_ip, to_address, subject, False, str(e))
        raise EmailSendError(f"Echec technique de l'envoi : {e}")
    except EmailSendError as e:
        _log_attempt(sender_ip, to_address, subject, False, str(e))
        raise

    _log_attempt(sender_ip, to_address, subject, True)
    return True
