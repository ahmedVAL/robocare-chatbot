"""
INTERFACE DE TEST - Streamlit
Interface de chat simple pour tester le chatbot, sans passer par curl/PowerShell.

Necessite que le serveur FastAPI tourne en parallele :
    uvicorn chatbot:app --reload

Lancement de cette interface (dans un AUTRE terminal) :
    streamlit run streamlit_app.py
"""

import os

import requests
import streamlit as st

# En local : http://127.0.0.1:8000/chat (valeur par defaut)
# Sur Streamlit Cloud : definissez API_URL dans les "Secrets" de l'app
# (Settings > Secrets) avec l'URL Render, ex:
#   API_URL = "https://robocare-chatbot.onrender.com/chat"
API_URL = st.secrets.get("API_URL", os.environ.get("API_URL", "http://127.0.0.1:8000/chat"))

st.set_page_config(page_title="Chatbot RoboCare - Test", page_icon="🤖")
st.title("🤖 Chatbot RoboCare - Interface de test")
st.caption("Interface de test locale, connectee a l'API FastAPI sur " + API_URL)

# Initialise l'historique de conversation
if "messages" not in st.session_state:
    st.session_state.messages = []

# Affiche l'historique
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("Sources utilisees"):
                for src in msg["sources"]:
                    st.markdown(f"- {src}")

# Zone de saisie
question = st.chat_input("Pose ta question sur RoboCare...")

if question:
    # Affiche la question de l'utilisateur
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Appelle l'API et affiche la reponse
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
                        with st.expander("Sources utilisees"):
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
                    "Verifie que 'uvicorn chatbot:app --reload' tourne bien "
                    "dans un autre terminal."
                )
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Bouton pour reinitialiser la conversation
if st.session_state.messages:
    if st.button("🔄 Nouvelle conversation"):
        st.session_state.messages = []
        st.rerun()






