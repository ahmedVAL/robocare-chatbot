"""
DIAGNOSTIC - verifie a quelle etape l'information (ex: horaires, contact)
est presente ou absente, pour trouver ou elle se perd dans le pipeline.
"""

import json
import re
from pathlib import Path

import chromadb

PAGES_DIR = Path("data/pages")
VECTOR_DB_DIR = "data/vector_db"
COLLECTION_NAME = "site_content"

# Mots-cles a rechercher (adapte selon ce qui te manque)
KEYWORDS = ["horaire", "heures", "ouvert", "contact", "telephone", "email", "adresse"]


def check_step_0_contact_info():
    """Etape 0 : le champ contact_info dedie (ajoute par scraper.py) est-il
    rempli sur au moins une page ?"""
    print("\n=== ETAPE 0 : champ contact_info dedie (scraper.py) ===")
    found_any = False
    for json_file in PAGES_DIR.glob("*.json"):
        if json_file.name == "urls.json":
            continue
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        contact = data.get("contact_info")
        if contact and (contact.get("emails") or contact.get("phones") or contact.get("address")):
            print(f"  ✅ {data['url']}")
            if contact.get("emails"):
                print(f"      emails : {contact['emails']}")
            if contact.get("phones"):
                print(f"      telephones : {contact['phones']}")
            if contact.get("address"):
                print(f"      adresse : {contact['address']}")
            found_any = True
    if not found_any:
        print("  ❌ Aucun contact_info trouve.")
        print("     -> Verifie que tu utilises bien la version a jour de scraper.py")
        print("        (celle avec extract_contact_info / extract_json_ld), et relance-le.")


def check_step_1_raw_pages():
    """Etape 1 : le mot-cle est-il present dans le texte BRUT scrape ?"""
    print("\n=== ETAPE 1 : contenu brut scrape (data/pages/*.json) ===")
    found_any = False
    for json_file in PAGES_DIR.glob("*.json"):
        if json_file.name == "urls.json":
            continue
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw_text = data.get("raw_text", "").lower()
        for kw in KEYWORDS:
            if kw in raw_text:
                print(f"  ✅ '{kw}' trouve dans {data['url']}")
                found_any = True
    if not found_any:
        print("  ❌ AUCUN mot-cle trouve dans le texte brut scrape.")
        print("     -> Le probleme vient du SCRAPING : la page contenant ces infos")
        print("        n'a peut-etre pas ete crawlee, ou le contenu est charge en JS")
        print("        (non visible par 'requests'), ou dans une image/un widget.")


def check_step_2_cleaned_pages():
    """Etape 2 : le mot-cle survit-il au nettoyage ?"""
    print("\n=== ETAPE 2 : contenu nettoye (clean_text) ===")
    found_any = False
    for json_file in PAGES_DIR.glob("*.json"):
        if json_file.name == "urls.json":
            continue
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        clean_text = data.get("clean_text", "").lower()
        for kw in KEYWORDS:
            if kw in clean_text:
                print(f"  ✅ '{kw}' trouve (nettoye) dans {data['url']}")
                found_any = True
    if not found_any:
        print("  ❌ Le mot-cle a disparu apres nettoyage (cleaner.py).")
        print("     -> cleaner.py est peut-etre trop agressif (MIN_LINE_LENGTH")
        print("        peut supprimer une ligne courte du type 'Lun-Ven 8h-17h').")


def check_step_3_vector_db():
    """Etape 3 : le mot-cle est-il retrouve par la recherche vectorielle ?"""
    print("\n=== ETAPE 3 : recherche dans la base vectorielle ===")
    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        print("  ❌ Collection introuvable. Lance indexer.py d'abord.")
        return

    total_docs = collection.count()
    print(f"  Total de chunks indexes : {total_docs}")

    for kw in KEYWORDS:
        results = collection.query(query_texts=[kw], n_results=2)
        docs = results["documents"][0] if results["documents"] else []
        metas = results["metadatas"][0] if results["metadatas"] else []
        print(f"\n  Recherche pour '{kw}' :")
        for doc, meta in zip(docs, metas):
            contains_kw = kw in doc.lower()
            marker = "✅" if contains_kw else "⚠️ "
            print(f"    {marker} [{meta['url']}] {doc[:150]}...")


def main():
    check_step_0_contact_info()
    check_step_1_raw_pages()
    check_step_2_cleaned_pages()
    check_step_3_vector_db()


if __name__ == "__main__":
    main()