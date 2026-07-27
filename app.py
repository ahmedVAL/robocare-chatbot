"""
INTERFACE DE TEST - Streamlit
Interface de chat pour le chatbot RoboCare.

Necessite que le serveur FastAPI tourne en parallele :
    uvicorn chatbot:app --reload

Lancement de cette interface (dans un AUTRE terminal) :
    streamlit run app.py

Logo attendu dans : assets/logo.png (telechargez-le depuis le site RoboCare
si ce n'est pas deja fait - voir instructions fournies a part).
"""

import os
from pathlib import Path

import requests
import streamlit as st

# En local : http://127.0.0.1:8000/chat (valeur par defaut)
# Sur Streamlit Cloud : definissez API_URL dans les "Secrets" de l'app
# (Settings > Secrets) avec l'URL Render, ex:
#   API_URL = "https://robocare-chatbot.onrender.com/chat"
API_URL = st.secrets.get("API_URL", os.environ.get("API_URL", "http://127.0.0.1:8000/chat"))

LOGO_PATH = Path(__file__).parent / "Robocare.png"
LOGO_EXISTS = LOGO_PATH.exists()

# Coordonnees de l'entreprise (deja verifiees via le scraping) - affichees
# directement dans la sidebar pour un acces rapide, sans passer par le chat.
COMPANY = {
    "phone": "+216 53 140 011",
    "email": "contact@robocare.tn",
    "address": "Rue Hedi Nouira, Immeuble Fourat, 3éme étage, Bab El Jebli, Sfax médina, 3047",
    "hours": "Lundi – Vendredi : 9h00 – 17h00",
    "maps_url": (
        "https://www.google.com/maps/place/Robocare/@34.7381327,10.7543985,17.28z/"
        "data=!4m6!3m5!1s0x1301d3007ad67c77:0x4fd73589ed9dbb82!8m2!3d34.7387795!4d10.7563845"
        "!16s%2Fg%2F11x8lvz36n?entry=ttu&g_ep=EgoyMDI2MDcyMC4wIKXMDSoASAFQAw%3D%3D"
    ),
}

st.set_page_config(
    page_title="RoboCare Assistant",
    page_icon=str(LOGO_PATH) if LOGO_EXISTS else "🛰️",
    layout="centered",
)

# --------------------------------------------------------------------------
# IDENTITE VISUELLE - palette inspiree du terrain : vert foret (agronomie),
# terre/sable (Sfax, sol), bleu satellite (le coeur technique du produit).
# Signature : une fine ligne de "scan" animee sous l'en-tete, clin d'oeil au
# scan satellite/drone qui est au centre du produit RoboCare.
# --------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700&family=Inter:wght@400;500;600&display=swap');

:root {
    --rc-forest: #1B4332;
    --rc-forest-light: #2D6A4F;
    --rc-leaf: #52B788;
    --rc-sage-bg: #F3F7F4;
    --rc-soil: #7A5230;
    --rc-sky: #2D6A8F;
    --rc-ink: #1A2E23;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: var(--rc-sage-bg);
}

/* Bandeau d'en-tete */
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

/* Signature : ligne de scan satellite animee */
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
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# EN-TETE
# --------------------------------------------------------------------------
logo_html = f'<img src="data:image/png;base64,{__import__("base64").b64encode(LOGO_PATH.read_bytes()).decode()}">' if LOGO_EXISTS else ""

st.markdown(f"""
<div class="rc-header">
    {logo_html}
    <div class="rc-header-text">
        <h1>Assistant RoboCare</h1>
        <p>We Tech-Care Of Your Land — posez vos questions sur nos services</p>
    </div>
</div>
<div class="rc-scanline"></div>
""", unsafe_allow_html=True)

if not LOGO_EXISTS:
    st.info(
        "💡 Logo non trouvé (`assets/logo.png`). Téléchargez-le depuis le site RoboCare "
        "et placez-le à cet emplacement pour qu'il s'affiche ici.",
        icon="🖼️",
    )

# --------------------------------------------------------------------------
# SIDEBAR - carte de contact rapide + reinitialisation
# --------------------------------------------------------------------------
with st.sidebar:
    if LOGO_EXISTS:
        st.image(str(LOGO_PATH), use_container_width=True)
    st.markdown("### 📍 Nous contacter")
    st.markdown(f"""
<div class="rc-contact-card">
📞 <a href="tel:{COMPANY['phone'].replace(' ', '')}">{COMPANY['phone']}</a><br>
✉️ <a href="mailto:{COMPANY['email']}">{COMPANY['email']}</a><br>
🕐 {COMPANY['hours']}<br>
📌 {COMPANY['address']}<br>
<a href="{COMPANY['maps_url']}" target="_blank">Voir sur Google Maps →</a>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")
    if st.session_state.get("messages"):
        if st.button("🔄 Nouvelle conversation", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

# --------------------------------------------------------------------------
# ZONE DE CHAT
# --------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("Sources utilisées"):
                for src in msg["sources"]:
                    st.markdown(f"- {src}")

question = st.chat_input("Posez votre question sur RoboCare...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Recherche en cours... (le premier message peut prendre jusqu'à 1 min si le serveur était en veille)"):
            try:
                resp = requests.post(API_URL, json={"message": question}, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    reponse = data.get("reponse", "")
                    sources = data.get("sources", [])
                    st.markdown(reponse)
                    if sources:
                        with st.expander("Sources utilisées"):
                            for src in sources:
                                st.markdown(f"- {src}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": reponse,
                        "sources": sources
                    })
                else:
                    error_msg = f"Erreur {resp.status_code} : {resp.text}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
            except requests.exceptions.ConnectionError:
                error_msg = (
                    "Impossible de contacter le serveur. "
                    "Vérifiez que 'uvicorn chatbot:app --reload' tourne bien "
                    "dans un autre terminal (ou que le service Render est en ligne)."
                )
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            except requests.exceptions.ReadTimeout:
                error_msg = (
                    "Le serveur met trop de temps à répondre. S'il était en veille "
                    "(hébergement gratuit), réessayez dans quelques instants."
                )
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})





