"""
MAILER — Envoi d'emails via SMTP avec garde-fous anti-abus.
Ce module tourne côté BACKEND (Render). Les credentials SMTP ne doivent
JAMAIS être exposés côté frontend (Streamlit Cloud).
"""

from __future__ import annotations

import json
import os
import re
import smtplib
import time
from collections import defaultdict
from email.mime.text import MIMEText
from pathlib import Path
from threading import Lock
from typing import Any

# --------------------------------------------------------------------------
# CONSTANTES
# --------------------------------------------------------------------------
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

RATE_LIMIT_MAX_EMAILS = 3
RATE_LIMIT_WINDOW_SECONDS = 3600
SUBJECT_PREFIX = "[Chatbot RoboCare] "

# Chemin absolu (Render utilise /opt/render/project/...)
LOG_FILE = Path(__file__).parent / "data" / "email_log.jsonl"

# --------------------------------------------------------------------------
# RATE LIMITER (en mémoire — remplacer par Redis en production multi-instance)
# --------------------------------------------------------------------------
_rate_limit_lock = Lock()
_send_history: defaultdict[str, list[float]] = defaultdict(list)


class EmailSendError(Exception):
    """Exception métier renvoyée au chatbot pour feedback utilisateur."""
    pass


def _sanitize_header(value: str) -> str:
    """Supprime les caractères d'injection d'en-têtes (CR, LF, NULL)."""
    return value.replace("\r", "").replace("\n", "").replace("\0", "")


def _check_rate_limit(sender_ip: str) -> None:
    now = time.time()
    with _rate_limit_lock:
        history = _send_history[sender_ip]
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        history[:] = [t for t in history if t > cutoff]

        if len(history) >= RATE_LIMIT_MAX_EMAILS:
            _log_attempt(sender_ip, "", "", False, "rate_limit_exceeded")
            raise EmailSendError(
                f"Limite atteinte : maximum {RATE_LIMIT_MAX_EMAILS} emails "
                f"par heure par visiteur. Réessayez plus tard."
            )
        history.append(now)


def _log_attempt(
    sender_ip: str,
    to_address: str,
    subject: str,
    success: bool,
    error: str | None = None,
) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {
            "timestamp": time.time(),
            "sender_ip": sender_ip,
            "to": to_address,
            "subject": subject,
            "success": success,
            "error": error,
        }
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        import logging
        logging.getLogger("robocare.mailer").warning(f"Impossible d'écrire le log : {exc}")


def _validate_smtp_config(cfg: dict[str, Any]) -> dict[str, Any]:
    required = {"host", "port", "user", "password", "from_addr"}
    missing = required - set(cfg.keys())
    if missing:
        raise EmailSendError(f"Configuration SMTP incomplète : {missing}")

    # Vérifier qu'aucun champ critique n'est vide
    for key in required:
        if not str(cfg.get(key, "")).strip():
            raise EmailSendError(f"Configuration SMTP invalide : '{key}' est vide.")

    return {
        "host": str(cfg["host"]).strip(),
        "port": int(cfg["port"]),
        "user": str(cfg["user"]).strip(),
        "password": str(cfg["password"]),
        "from_addr": str(cfg["from_addr"]).strip(),
    }


def get_smtp_config() -> dict[str, Any]:
    """
    Charge la configuration SMTP depuis les variables d'environnement (Render).
    
    Variables attendues dans Render Dashboard → Environment :
        SMTP_HOST=smtp.gmail.com
        SMTP_PORT=587
        SMTP_USER=jarraya616@gmail.com
        SMTP_PASSWORD=votre_mot_de_passe_app_gmail
        SMTP_FROM=jarraya616@gmail.com
    """
    return {
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("SMTP_PORT", 587)),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_addr": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
    }


def send_email(
    to_address: str,
    subject: str,
    body: str,
    sender_ip: str = "unknown",
    smtp_config: dict[str, Any] | None = None,
) -> bool:
    """
    Envoie un email via SMTP.

    Args:
        to_address: destinataire
        subject: objet (préfixé automatiquement)
        body: corps du message
        sender_ip: IP du visiteur pour le rate limiting
        smtp_config: config SMTP (charge depuis l'env par défaut)

    Returns:
        True si succès.

    Raises:
        EmailSendError: adresse invalide, rate limit, ou échec SMTP.
    """
    # Charger la config si non fournie
    cfg = _validate_smtp_config(smtp_config or get_smtp_config())

    # Validation destinataire
    to_address = (to_address or "").strip()
    if not EMAIL_REGEX.match(to_address):
        _log_attempt(sender_ip, to_address, subject, False, "adresse invalide")
        raise EmailSendError(f"L'adresse '{to_address}' n'est pas une adresse email valide.")

    # Rate limit
    _check_rate_limit(sender_ip)

    # Construction du message
    clean_subject = _sanitize_header(subject.strip() if subject else "Message du chatbot")
    full_subject = SUBJECT_PREFIX + clean_subject

    msg = MIMEText(body or "", "plain", "utf-8")
    msg["Subject"] = full_subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = to_address

    # Envoi SMTP
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["from_addr"], [to_address], msg.as_string())

    except smtplib.SMTPAuthenticationError:
        _log_attempt(sender_ip, to_address, full_subject, False, "auth_error")
        raise EmailSendError(
            "Échec d'authentification SMTP. Vérifiez le mot de passe (mot de passe d'application Gmail requis)."
        )

    except smtplib.SMTPConnectError:
        _log_attempt(sender_ip, to_address, full_subject, False, "connexion_error")
        raise EmailSendError(f"Impossible de se connecter au serveur SMTP ({cfg['host']}).")

    except smtplib.SMTPRecipientsRefused:
        _log_attempt(sender_ip, to_address, full_subject, False, "recipient_refused")
        raise EmailSendError(f"Le serveur a refusé le destinataire '{to_address}'.")

    except smtplib.SMTPException as exc:
        _log_attempt(sender_ip, to_address, full_subject, False, f"smtp_error: {exc}")
        raise EmailSendError(f"Erreur SMTP : {exc}")

    except Exception as exc:
        _log_attempt(sender_ip, to_address, full_subject, False, f"unexpected: {exc}")
        raise EmailSendError(f"Échec technique de l'envoi : {exc}")

    _log_attempt(sender_ip, to_address, full_subject, True)
    return True
