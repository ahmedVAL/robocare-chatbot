"""
ETAPE 5 - INDEXER
Lit le PDF genere par pdf_generator.py, retrouve l'URL source de chaque
section (grace aux lignes "SOURCE: ..." inserees dans le PDF), decoupe le
texte en chunks, et les indexe dans une base vectorielle ChromaDB.
"""

import re
from pathlib import Path

import chromadb
import pdfplumber

PDF_PATH = Path("data/pdf/site_content.pdf")
VECTOR_DB_DIR = "data/vector_db"
COLLECTION_NAME = "site_content"

CHUNK_SIZE = 400      # nombre de mots par chunk
CHUNK_OVERLAP = 50    # chevauchement entre chunks pour garder le contexte

SOURCE_PATTERN = re.compile(r"^SOURCE:\s*(\S+)")


def extract_sections_from_pdf(pdf_path):
    """Parcourt le PDF et regroupe le texte par section (= par page du site),
    en utilisant les lignes 'SOURCE: url' comme delimiteurs."""
    sections = []
    current_source = None
    current_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                match = SOURCE_PATTERN.match(line.strip())
                if match:
                    # nouvelle section : on sauvegarde la precedente
                    if current_source and current_text:
                        sections.append({
                            "url": current_source,
                            "text": " ".join(current_text)
                        })
                    current_source = match.group(1)
                    current_text = []
                else:
                    if line.strip():
                        current_text.append(line.strip())

    # ne pas oublier la derniere section
    if current_source and current_text:
        sections.append({
            "url": current_source,
            "text": " ".join(current_text)
        })

    return sections


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def index_sections(sections, collection):
    total_chunks = 0

    for section in sections:
        chunks = chunk_text(section["text"])
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{section['url']}_{idx}"
            collection.add(
                documents=[chunk],
                metadatas=[{"url": section["url"]}],
                ids=[chunk_id]
            )
            total_chunks += 1

    return total_chunks


def main():
    if not PDF_PATH.exists():
        print(f"PDF introuvable : {PDF_PATH}. Lance d'abord pdf_generator.py")
        return

    print("Lecture du PDF...")
    sections = extract_sections_from_pdf(PDF_PATH)
    print(f"{len(sections)} sections (pages du site) retrouvees dans le PDF.")

    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    # reset de la collection a chaque reindexation complete
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME)

    total_chunks = index_sections(sections, collection)
    print(f"\nTermine : {total_chunks} chunks indexes dans {VECTOR_DB_DIR}/")


if __name__ == "__main__":
    main()