"""
ETAPE 3 - CLEANER
Nettoie le texte brut extrait par scraper.py :
- supprime les lignes trop courtes / repetitives (menus, mentions legales...)
- normalise les espaces et retours a la ligne
- deduplique les lignes qui apparaissent sur presque toutes les pages
  (ex: "Accueil | Contact | Mentions legales" present partout)

IMPORTANT : les lignes contenant des infos utiles (email, telephone, horaires,
adresse) sont TOUJOURS conservees, meme si elles se repetent sur toutes les
pages (ex: footer avec coordonnees present partout) - sinon elles seraient
supprimees comme "bruit recurrent" et perdues meme sur la page contact.

MISE A JOUR : sur un petit site (peu de pages), la detection statistique de
"bruit recurrent" (BOILERPLATE_THRESHOLD) n'est plus fiable - un vrai
paragraphe de contenu qui apparait par coincidence sur 2-3 pages d'un site de
5 pages peut depasser le seuil et etre supprime a tort. On desactive donc
cette detection en dessous de MIN_PAGES_FOR_BOILERPLATE_DETECTION pages, et
MIN_LINE_LENGTH est abaisse pour ne plus couper des lignes courtes mais
utiles (ex: un nom de produit, une specification breve).

Met a jour chaque fichier data/pages/*.json en ajoutant une cle "clean_text".
"""

import json
import re
from collections import Counter
from pathlib import Path

PAGES_DIR = Path("data/pages")
MIN_LINE_LENGTH = 8           # abaisse de 20 a 8 : evite de couper des lignes
                               # courtes mais informatives (specs, labels...)
BOILERPLATE_THRESHOLD = 0.75  # releve de 0.6 a 0.75 : moins agressif
MIN_PAGES_FOR_BOILERPLATE_DETECTION = 6  # en dessous, la detection est
                                          # statistiquement peu fiable

# Motifs d'informations importantes a ne JAMAIS supprimer, meme repetees
IMPORTANT_PATTERNS = [
    re.compile(r"[\w.\-+]+@[\w\-]+\.[a-zA-Z]{2,}"),          # email
    re.compile(r"(\+?\d[\d\s().\-]{6,}\d)"),                  # telephone
    re.compile(r"\b\d{1,2}\s*[hH:]\s*\d{0,2}\b"),              # horaires type 8h-17h / 8:00
    re.compile(
        r"\b(lun(di)?|mar(di)?|mer(credi)?|jeu(di)?|ven(dredi)?|"
        r"sam(edi)?|dim(anche)?|monday|tuesday|wednesday|thursday|"
        r"friday|saturday|sunday)\b",
        re.IGNORECASE,
    ),  # jours de la semaine (souvent associes aux horaires)
]

IMPORTANT_KEYWORDS = [
    "horaire", "heures d'ouverture", "ouvert", "ferme", "contact",
    "téléphone", "telephone", "adresse", "email", "e-mail",
    "rue", "avenue", "immeuble", "sfax", "maps",
]


def is_important_line(line):
    """Renvoie True si la ligne contient une info a ne jamais supprimer."""
    lower = line.lower()
    if any(keyword in lower for keyword in IMPORTANT_KEYWORDS):
        return True
    if any(pattern.search(line) for pattern in IMPORTANT_PATTERNS):
        return True
    return False


def load_all_pages():
    pages = []
    for json_file in PAGES_DIR.glob("*.json"):
        if json_file.name == "urls.json":
            continue
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["_file"] = json_file
            pages.append(data)
    return pages


def find_boilerplate_lines(pages):
    """Identifie les lignes qui reviennent sur la majorite des pages (menus,
    footers...). Exclut les lignes importantes de cette detection. Desactivee
    entierement si le site a trop peu de pages pour que ce soit fiable."""
    if len(pages) < MIN_PAGES_FOR_BOILERPLATE_DETECTION:
        print(
            f"  (site de {len(pages)} page(s) < {MIN_PAGES_FOR_BOILERPLATE_DETECTION} : "
            f"detection de boilerplate desactivee, trop peu de donnees pour etre fiable)"
        )
        return set()

    line_counter = Counter()
    for page in pages:
        lines = set(page["raw_text"].split("\n"))
        for line in lines:
            stripped = line.strip()
            if is_important_line(stripped):
                continue
            line_counter[stripped] += 1

    total_pages = len(pages)
    boilerplate = {
        line for line, count in line_counter.items()
        if total_pages > 0 and (count / total_pages) >= BOILERPLATE_THRESHOLD
    }
    return boilerplate


def clean_text(raw_text, boilerplate_lines):
    lines = raw_text.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        line = re.sub(r"\s+", " ", line)

        if not line:
            continue

        if is_important_line(line):
            cleaned_lines.append(line)
            continue

        if line in boilerplate_lines:
            continue
        if len(line) < MIN_LINE_LENGTH and not line.endswith((".", "!", "?", ":")):
            continue

        cleaned_lines.append(line)

    final_lines = []
    for line in cleaned_lines:
        if not final_lines or final_lines[-1] != line:
            final_lines.append(line)

    return "\n".join(final_lines)


def main():
    pages = load_all_pages()
    if not pages:
        print("Aucune page trouvee dans data/pages/. Lance d'abord scraper.py")
        return

    boilerplate_lines = find_boilerplate_lines(pages)
    print(f"{len(boilerplate_lines)} lignes recurrentes (menus/footers) detectees et exclues.")

    for page in pages:
        cleaned = clean_text(page["raw_text"], boilerplate_lines)
        page["clean_text"] = cleaned

        output_path = page.pop("_file")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(page, f, ensure_ascii=False, indent=2)

        print(f"Nettoye : {page['url']} ({len(cleaned)} caracteres utiles)")

    print(f"\nTermine : {len(pages)} pages nettoyees.")


if __name__ == "__main__":
    main()