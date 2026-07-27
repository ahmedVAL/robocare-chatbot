"""
Interface de chat RoboCare — Version professionnelle Streamlit.

Nécessite que le serveur FastAPI tourne en parallèle :
    uvicorn chatbot:app --reload

Lancement de cette interface (dans un AUTRE terminal) :
    streamlit run app.py

Logo attendu dans : assets/robocare.png
"""

from __future__ import annotations

import base64
import logging
import os
import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st

# --------------------------------------------------------------------------
# CONFIGURATION & LOGGING
# --------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("robocare_ui")


# --------------------------------------------------------------------------
# CONSTANTES
# --------------------------------------------------------------------------
class Config:
    """Configuration centralisée de l'application."""

    # Répertoire racine du script
    BASE_DIR: Path = Path(__file__).parent.resolve()

    # Chemin du logo (priorité : assets/robocare.png, fallback robocare.png)
    LOGO_PATH: Path = BASE_DIR / "robocare.png"
    if not LOGO_PATH.exists():
        LOGO_PATH = BASE_DIR / "robocare.png"

    # URL de l'API (priorité : secrets Streamlit > variable d'env > localhost)
    API_URL: str = st.secrets.get(
        "API_URL",
        os.environ.get("API_URL", "http://127.0.0.1:8000/chat"),
    )

    # Timeout pour les requêtes API (secondes)
    TIMEOUT: int = 60

    # Coordonnées entreprise (vérifiées via scraping)
    COMPANY: dict[str, str] = {
        "phone": "+216 53 140 011",
        "email": "contact@robocare.tn",
        "address": "Rue Hedi Nouira, Immeuble Fourat, 3éme étage, Bab El Jebli, Sfax médina, 3047",
        "hours": "Lundi – Vendredi : 9h00 – 17h00",
        "maps_url": (
            "https://www.google.com/maps/place/Robocare/"
            "@34.7381327,10.7543985,17.28z/"
            "data=!4m6!3m5!1s0x1301d3007ad67c77:0x4fd73589ed9dbb82!"
            "8m2!3d34.7387795!4d10.7563845!16s%2Fg%2F11x8lvz36n?entry=ttu"
        ),
    }


# --------------------------------------------------------------------------
# UTILITAIRES
# --------------------------------------------------------------------------
def load_logo_base64(path: Path) -> str | None:
    """
    Charge une image et la retourne en base64 pour intégration HTML.
    Retourne None si le fichier n'existe pas.
    """
    if not path.exists():
        logger.warning(f"Logo introuvable : {path}")
        return None
    try:
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception as exc:
        logger.error(f"Erreur lecture logo : {exc}")
        return None


def validate_api_url(url: str) -> bool:
    """Vérifie que l'URL de l'API est valide (non vide et format correct)."""
    if not url or not url.strip():
        return False
    return url.startswith(("http://", "https://"))


def call_chatbot_api(question: str, api_url: str, timeout: int) -> dict[str, Any]:
    """
    Envoie une question à l'API FastAPI et retourne la réponse structurée.
    Lève une exception en cas d'erreur réseau ou HTTP.
    """
    payload = {"message": question}
    response = requests.post(api_url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


# --------------------------------------------------------------------------
# STYLES CSS PERSONNALISÉS
# --------------------------------------------------------------------------
def inject_custom_css() -> None:
    """Injecte les styles CSS de l'identité visuelle RoboCare."""
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700&family=Inter:wght@400;500;600&display=swap');

    :root {
        --rc-forest: #1B4332;
        --rc-forest-light: #2D6A4F;
        --rc-leaf: #52B788;
        --rc-sage-bg: #F3F7F4;
        --rc-soil: #7A5230;
        --rc-sky: #2D6A8F;
        --rc-ink: #1A2E23;
        --rc-error: #C0392B;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: var(--rc-sage-bg);
    }

    /* Bandeau d'en-tête */
    .rc-header {
        background: linear-gradient(135deg, var(--rc-forest) 0%, var(--rc-forest-light) 100%);
        border-radius: 14px;
        padding: 1.75rem 2rem;
        margin-bottom: 0.4rem;
        display: flex;
        align-items: center;
        gap: 1.1rem;
        box-shadow: 0 4px 18px rgba(27, 67, 50, 0.18);
    }
    .rc-header img {
        height: 46px;
        border-radius: 6px;
        background: white;
        padding: 4px 8px;
    }
    .rc-header-text h1 {
        font-family: 'Sora', sans-serif;
        color: white;
        font-size: 1.35rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.01em;
    }
    .rc-header-text p {
        color: #CDE7D8;
        font-size: 0.85rem;
        margin: 0.15rem 0 0 0;
    }

    /* Ligne de scan satellite animée */
    .rc-scanline {
        height: 3px;
        margin-bottom: 1.5rem;
        border-radius: 2px;
        background: linear-gradient(90deg, var(--rc-leaf) 0%, var(--rc-sky) 50%, var(--rc-soil) 100%);
        background-size: 200% 100%;
        animation: rc-scan 6s ease-in-out infinite;
    }
    @keyframes rc-scan {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    @media (prefers-reduced-motion: reduce) {
        .rc-scanline { animation: none; }
    }

    /* Bulles de chat */
    [data-testid="stChatMessage"] {
        border-radius: 12px;
        border: 1px solid rgba(27, 67, 50, 0.08);
    }

    /* Boutons */
    .stButton > button {
        background: var(--rc-forest);
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background: var(--rc-leaf);
        color: var(--rc-forest);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: white;
        border-right: 1px solid rgba(27, 67, 50, 0.08);
    }
    .rc-contact-card {
        background: var(--rc-sage-bg);
        border-radius: 10px;
        padding: 1rem;
        font-size: 0.85rem;
        line-height: 1.6;
        color: var(--rc-ink);
    }
    .rc-contact-card a {
        color: var(--rc-sky);
        text-decoration: none;
        font-weight: 500;
    }
    .rc-contact-card a:hover {
        text-decoration: underline;
    }

    /* Alertes personnalisées */
    .rc-alert {
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 1rem;
    }
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# COMPOSANTS UI
# --------------------------------------------------------------------------
def render_header(logo_b64: str | None) -> None:
    """Affiche l'en-tête avec logo et tagline."""
    logo_html = ""
    if logo_b64:
        logo_html = (
            f'<img src="data:image/png;base64,{logo_b64}" '
            f'alt="Logo RoboCare" title="RoboCare">'
        )

    st.markdown(
        f"""
        <div class="rc-header">
            {logo_html}
            <div class="rc-header-text">
                <h1>Assistant RoboCare</h1>
                <p>We Tech-Care Of Your Land — posez vos questions sur nos services</p>
            </div>
        </div>
        <div class="rc-scanline"></div>
        """,
        unsafe_allow_html=True,
    )

    if not logo_b64:
        st.info(
            "💡 Logo non trouvé (`assets/robocare.png` ou `robocare.png`). "
            "Placez votre logo à l'un de ces emplacements pour qu'il s'affiche.",
            icon="🖼️",
        )


def render_sidebar(config: Config) -> None:
    """Affiche la sidebar avec contact et contrôles."""
    with st.sidebar:
        # Logo dans la sidebar
        if config.LOGO_PATH.exists():
            st.image(str(config.LOGO_PATH), use_container_width=True)

        # Carte de contact
        st.markdown("### 📍 Nous contacter")
        phone_clean = config.COMPANY["phone"].replace(" ", "")
        st.markdown(
            f"""
            <div class="rc-contact-card">
            📞 <a href="tel:{phone_clean}">{config.COMPANY['phone']}</a><br>
            ✉️ <a href="mailto:{config.COMPANY['email']}">{config.COMPANY['email']}</a><br>
            🕐 {config.COMPANY['hours']}<br>
            📌 {config.COMPANY['address']}<br>
            <a href="{config.COMPANY['maps_url']}" target="_blank" rel="noopener noreferrer">
                Voir sur Google Maps →
            </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # Statut API
        st.markdown("### 🔌 Statut")
        if validate_api_url(config.API_URL):
            st.success(f"API : `{config.API_URL}`")
        else:
            st.error("⚠️ URL API invalide")

        st.markdown("---")

        # Réinitialisation conversation
        if st.button("🔄 Nouvelle conversation", use_container_width=True):
            st.session_state.messages = []
            st.rerun()


def render_chat_history() -> None:
    """Affiche l'historique des messages."""
    messages: list[dict] = st.session_state.get("messages", [])
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("📚 Sources utilisées"):
                    for src in msg["sources"]:
                        st.markdown(f"- {src}")


def handle_user_input(config: Config) -> None:
    """Gère la saisie utilisateur et l'appel API."""
    question = st.chat_input("Posez votre question sur RoboCare...")

    if not question:
        return

    # Ajout message utilisateur
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Réponse du chatbot
    with st.chat_message("assistant"):
        with st.spinner(
            "Recherche en cours... "
            "(le premier message peut prendre jusqu'à 1 min si le serveur était en veille)"
        ):
            try:
                if not validate_api_url(config.API_URL):
                    raise ValueError("URL de l'API non configurée ou invalide.")

                data = call_chatbot_api(
                    question=question,
                    api_url=config.API_URL,
                    timeout=config.TIMEOUT,
                )

                reponse = data.get("reponse", "")
                sources = data.get("sources", [])

                st.markdown(reponse)

                if sources:
                    with st.expander("📚 Sources utilisées"):
                        for src in sources:
                            st.markdown(f"- {src}")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reponse,
                    "sources": sources,
                })

            except requests.exceptions.ConnectionError as exc:
                logger.error(f"Erreur de connexion : {exc}")
                error_msg = (
                    "❌ **Impossible de contacter le serveur.**\n\n"
                    "Vérifiez que le serveur FastAPI est bien lancé :\n"
                    "```bash\nuvicorn chatbot:app --reload\n```\n"
                    "Si vous utilisez Render, assurez-vous que le service est en ligne."
                )
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })

            except requests.exceptions.ReadTimeout as exc:
                logger.error(f"Timeout : {exc}")
                error_msg = (
                    "⏱️ **Le serveur met trop de temps à répondre.**\n\n"
                    "S'il était en veille (hébergement gratuit), réessayez dans quelques instants."
                )
                st.warning(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })

            except requests.exceptions.HTTPError as exc:
                logger.error(f"Erreur HTTP : {exc}")
                error_msg = f"⚠️ **Erreur serveur** : {exc.response.status_code}\n\n```\n{exc.response.text}\n```"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })

            except Exception as exc:
                logger.exception("Erreur inattendue")
                error_msg = f"🚨 **Erreur inattendue** : `{type(exc).__name__}`\n\n{str(exc)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })


# --------------------------------------------------------------------------
# POINT D'ENTRÉE PRINCIPAL
# --------------------------------------------------------------------------
def main() -> None:
    """Fonction principale de l'application Streamlit."""
    # Configuration de la page (DOIT être le premier appel Streamlit)
    config = Config()

    page_icon = str(config.LOGO_PATH) if config.LOGO_PATH.exists() else "🛰️"
    st.set_page_config(
        page_title="RoboCare Assistant",
        page_icon=page_icon,
        layout="centered",
        initial_sidebar_state="expanded",
    )

    # Injection CSS
    inject_custom_css()

    # Chargement du logo
    logo_b64 = load_logo_base64(config.LOGO_PATH)

    # En-tête
    render_header(logo_b64)

    # Sidebar
    render_sidebar(config)

    # Initialisation de l'historique
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Message de bienvenue (première visite)
    if not st.session_state.messages:
        welcome_msg = (
            "👋 Bienvenue ! Je suis l'assistant virtuel de **RoboCare**. "
            "Je peux répondre à vos questions sur nos services d'agriculture de précision, "
            "de télédétection et d'analyse de sol. Comment puis-je vous aider ?"
        )
        st.session_state.messages.append({
            "role": "assistant",
            "content": welcome_msg,
            "sources": [],
        })

    # Affichage de l'historique
    render_chat_history()

    # Gestion de la saisie
    handle_user_input(config)


if __name__ == "__main__":
    main()
