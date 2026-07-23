"""
ETAPE 2 - SCRAPER
Prend la liste d'URLs generee par crawler.py et extrait le contenu brut
(titre + texte) de chaque page. Sauvegarde un fichier JSON par page dans
data/pages/

MISE A JOUR : en plus de l'extraction JSON-LD + regex email/telephone, on
detecte maintenant une ligne d'adresse postale par heuristique (mots-cles +
code postal) quand elle n'est pas dans le JSON-LD, et on construit un lien
Google Maps cliquable directement depuis cette adresse texte. Pas besoin de
scraper une carte integree (souvent chargee en JS/lazy-load de toute facon) :
Google Maps sait tres bien localiser une adresse a partir du texte seul via
son URL de recherche officielle.
"""

import json
import re
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

INPUT_FILE = "data/pages/urls.json"
OUTPUT_DIR = Path("data/pages")
DELAY_SECONDS = 0.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ChatbotScraper/1.0)"
}

# Regex volontairement larges : mieux vaut capturer un faux positif de temps
# en temps (filtrable plus tard) que rater le vrai numero/email de contact.
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}")

# Heuristique pour reperer une ligne d'adresse dans le texte brut, quand elle
# n'est pas disponible en JSON-LD structure.
ADDRESS_KEYWORDS = re.compile(
    r"\b(rue|avenue|boulevard|immeuble|residence|route|street|rd\.?|blvd\.?|"
    r"building|floor|etage|zone industrielle|sfax|tunis|tunisie)\b",
    re.IGNORECASE,
)
POSTAL_CODE_REGEX = re.compile(r"\b\d{4,5}\b")

# Lien Google Maps verifie manuellement (avec Place ID) - plus precis que la
# recherche par adresse texte generee automatiquement. Prioritaire quand defini.
MANUAL_MAPS_URL = (
    "https://www.google.com/maps/place/Robocare/@34.7381327,10.7543985,17.28z/"
    "data=!4m6!3m5!1s0x1301d3007ad67c77:0x4fd73589ed9dbb82!8m2!3d34.7387795!4d10.7563845"
    "!16s%2Fg%2F11x8lvz36n?entry=ttu&g_ep=EgoyMDI2MDcyMC4wIKXMDSoASAFQAw%3D%3D"
)

# Balises a supprimer avant extraction (bruit non pertinent).
# NOTE : on ne supprime PAS <footer> ni <header> car ils contiennent souvent
# les coordonnees de l'entreprise (adresse, telephone, email) repetees sur
# toutes les pages - exactement l'info qu'on veut capturer pour le chatbot.
TAGS_TO_REMOVE = ["script", "style", "nav", "noscript", "iframe", "svg"]


def url_to_filename(url):
    """Transforme une URL en nom de fichier sûr et lisible.
    Inclut la query string (ex: ?page_id=9) pour eviter que plusieurs URLs
    differentes n'ecrasent le meme fichier."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_") or "accueil"

    if parsed.query:
        query_part = re.sub(r"[^a-zA-Z0-9_-]", "-", parsed.query)
        path = f"{path}_{query_part}" if path != "accueil" else query_part

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", path)
    return f"{safe_name}.json"


def extract_json_ld(soup):
    """Recupere les blocs de donnees structurees JSON-LD presents sur la page."""
    blocks = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            blocks.append(json.loads(script.string))
        except (json.JSONDecodeError, TypeError):
            continue
    return blocks


def find_address_line(raw_text):
    """Cherche une ligne de texte qui ressemble a une adresse postale :
    contient un mot-cle d'adresse ET un code postal-like."""
    for line in raw_text.split("\n"):
        line = line.strip()
        if len(line) < 10 or len(line) > 200:
            continue
        if ADDRESS_KEYWORDS.search(line) and POSTAL_CODE_REGEX.search(line):
            return line
    for line in raw_text.split("\n"):
        line = line.strip()
        if 10 <= len(line) <= 150 and ADDRESS_KEYWORDS.search(line):
            return line
    return None


def format_json_ld_address(address_obj):
    """L'adresse JSON-LD est un objet structure. On la transforme en une
    seule ligne lisible."""
    if isinstance(address_obj, str):
        return address_obj
    if isinstance(address_obj, dict):
        parts = [
            address_obj.get("streetAddress"),
            address_obj.get("addressLocality"),
            address_obj.get("postalCode"),
            address_obj.get("addressCountry"),
        ]
        return ", ".join(p for p in parts if p)
    return None


def build_maps_url(address_text):
    """Construit un lien Google Maps direct et cliquable a partir d'une
    adresse texte (URL de recherche officielle Google Maps)."""
    if not address_text:
        return None
    return f"https://www.google.com/maps/search/?api=1&query={quote(address_text)}"


def extract_contact_info(raw_text, json_ld_blocks):
    """Extrait emails/telephones/adresse par regex + JSON-LD, et construit
    un lien Google Maps si une adresse est trouvee."""
    emails = set(EMAIL_REGEX.findall(raw_text))
    phones = set(m.strip() for m in PHONE_REGEX.findall(raw_text) if len(m.strip()) >= 8)
    address = None

    def walk(node):
        nonlocal address
        items = node if isinstance(node, list) else [node]
        for item in items:
            if not isinstance(item, dict):
                continue
            if "address" in item and not address:
                address = format_json_ld_address(item["address"])
            if item.get("telephone"):
                phones.add(item["telephone"])
            if item.get("email"):
                emails.add(item["email"])

    for block in json_ld_blocks:
        walk(block)

    if not address:
        address = find_address_line(raw_text)

    return {
        "emails": sorted(emails),
        "phones": sorted(phones)[:5],
        "address": address,
        "maps_url": MANUAL_MAPS_URL or build_maps_url(address),
    }


def extract_page_content(url):
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()

    soup_full = BeautifulSoup(resp.text, "html.parser")
    json_ld_blocks = extract_json_ld(soup_full)

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag_name in TAGS_TO_REMOVE:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(strip=True) if h1_tag else ""

    body = soup.find("body")
    raw_text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)

    contact_info = extract_contact_info(raw_text, json_ld_blocks)

    return {
        "url": url,
        "title": title,
        "h1": h1,
        "raw_text": raw_text,
        "contact_info": contact_info,
        "json_ld": json_ld_blocks,
    }


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        urls = json.load(f)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    success_count = 0

    for i, url in enumerate(urls, start=1):
        try:
            page_data = extract_page_content(url)
            filename = url_to_filename(url)
            output_path = OUTPUT_DIR / filename

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(page_data, f, ensure_ascii=False, indent=2)

            success_count += 1
            n_emails = len(page_data["contact_info"]["emails"])
            n_phones = len(page_data["contact_info"]["phones"])
            has_addr = "adresse+maps" if page_data["contact_info"]["maps_url"] else ""
            extra_bits = [b for b in [
                f"{n_emails} email(s)" if n_emails else "",
                f"{n_phones} tel(s)" if n_phones else "",
                has_addr,
            ] if b]
            extra = f" [{', '.join(extra_bits)}]" if extra_bits else ""
            print(f"[{i}/{len(urls)}] Extrait : {url} -> {filename}{extra}")

        except requests.RequestException as e:
            print(f"[{i}/{len(urls)}] Erreur sur {url}: {e}")

        time.sleep(DELAY_SECONDS)

    print(f"\nTermine : {success_count}/{len(urls)} pages extraites dans {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()