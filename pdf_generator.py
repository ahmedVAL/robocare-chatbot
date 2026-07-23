"""
ETAPE 4 - PDF GENERATOR
Assemble le contenu nettoye de toutes les pages (data/pages/*.json) en un
seul PDF d'archive : data/pdf/site_content.pdf

Chaque page du site devient une section du PDF, avec son URL et son titre
en en-tete. C'est important : cela permet a indexer.py (etape suivante) de
retrouver l'URL d'origine de chaque passage indexe, et donc au chatbot de
citer ses sources.

MISE A JOUR : quand contact_info (ajoute par scraper.py) contient des
emails/telephones/adresse/lien Maps, un paragraphe "FICHE CONTACT" court et
explicite est insere en tete de section, incluant desormais le lien Google
Maps direct quand une adresse a ete detectee.
"""

import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak
)

PAGES_DIR = Path("data/pages")
OUTPUT_PDF = Path("data/pdf/site_content.pdf")


def load_cleaned_pages():
    pages = []
    for json_file in PAGES_DIR.glob("*.json"):
        if json_file.name == "urls.json":
            continue
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("clean_text"):
                pages.append(data)
    return pages


def build_contact_paragraph(contact_info):
    """Construit une ligne de texte dense et explicite a partir de
    contact_info, incluant le lien Google Maps si disponible. Renvoie None
    si rien d'exploitable n'a ete trouve."""
    if not contact_info:
        return None

    pieces = []
    if contact_info.get("emails"):
        pieces.append("Email: " + ", ".join(contact_info["emails"]))
    if contact_info.get("phones"):
        pieces.append("Telephone: " + ", ".join(contact_info["phones"]))
    if contact_info.get("address"):
        pieces.append("Adresse: " + contact_info["address"])
    if contact_info.get("maps_url"):
        pieces.append("Lien Google Maps: " + contact_info["maps_url"])

    if not pieces:
        return None
    return "FICHE CONTACT - " + " | ".join(pieces)


def build_pdf(pages, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    source_style = ParagraphStyle(
        "SourceStyle",
        parent=styles["Normal"],
        fontSize=8,
        textColor="#666666",
        spaceAfter=4,
    )
    title_style = styles["Heading1"]
    contact_style = ParagraphStyle(
        "ContactStyle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=10,
        textColor="#1a5c1a",
        backColor="#eef7ee",
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
    )

    story = []

    for i, page in enumerate(pages):
        story.append(Paragraph(f"SOURCE: {page['url']}", source_style))
        title = page.get("h1") or page.get("title") or "Sans titre"
        story.append(Paragraph(title, title_style))

        contact_paragraph = build_contact_paragraph(page.get("contact_info"))
        if contact_paragraph:
            safe_contact = (
                contact_paragraph.replace("&", "&amp;")
                                 .replace("<", "&lt;")
                                 .replace(">", "&gt;")
            )
            story.append(Paragraph(safe_contact, contact_style))

        story.append(Spacer(1, 6))

        for line in page["clean_text"].split("\n"):
            if line.strip():
                safe_line = (
                    line.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                )
                story.append(Paragraph(safe_line, body_style))

        if i < len(pages) - 1:
            story.append(PageBreak())

    doc.build(story)


def main():
    pages = load_cleaned_pages()
    if not pages:
        print("Aucune page nettoyee trouvee. Lance d'abord cleaner.py")
        return

    build_pdf(pages, OUTPUT_PDF)
    print(f"PDF genere : {OUTPUT_PDF} ({len(pages)} pages du site incluses)")


if __name__ == "__main__":
    main()