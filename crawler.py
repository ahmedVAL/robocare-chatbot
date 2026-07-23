"""
ETAPE 1 - CRAWLER
Parcourt le site a partir d'une URL de depart et recense toutes les pages
internes trouvees. Sauvegarde la liste des URLs dans data/pages/urls.json

MISE A JOUR : combine deux sources de decouverte au lieu d'une seule :
  1. sitemap.xml - souvent plus complet que le simple suivi de liens, car il
     inclut des pages qui ne sont pas forcement accessibles depuis le menu
     (pages orphelines, anciennes pages encore indexees, etc.)
  2. crawl recursif des liens - complement indispensable, car toutes les
     sites n'ont pas un sitemap.xml a jour, et certaines pages recentes n'y
     sont pas encore.
Les deux listes sont fusionnees et deduppliquees.

Fonctionne pour les sites statiques (HTML classique). Si le site est en JS
(React/Vue), voir la note en bas du fichier pour basculer sur Playwright.
"""

import json
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---- Configuration ----
START_URL = "https://robocare.tn/"   # <-- a remplacer par le vrai site
MAX_PAGES = 200
DELAY_SECONDS = 0.5   # pause entre 2 requetes, pour ne pas surcharger le site
OUTPUT_FILE = "data/pages/urls.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ChatbotCrawler/1.0)"
}

# Extensions a ignorer (fichiers non-HTML)
IGNORED_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".zip", ".doc", ".docx", ".xls", ".xlsx", ".css", ".js",
    ".mp4", ".mp3", ".ico"
)


def normalize_url(url):
    """Normalise une URL pour la deduplication : retire l'ancre et le slash
    final (garde la query string, importante pour les sites WordPress qui
    utilisent ?page_id=X)."""
    return url.split("#")[0].rstrip("/")


def is_valid_page(url, base_domain):
    """Verifie que l'URL appartient au meme domaine et n'est pas un fichier binaire."""
    parsed = urlparse(url)
    if parsed.netloc != base_domain:
        return False
    if url.lower().endswith(IGNORED_EXTENSIONS):
        return False
    return True


def discover_from_sitemap(start_url):
    """Recupere toutes les URLs listees dans sitemap.xml (et sitemaps imbriques,
    frequent avec Yoast SEO / RankMath sur WordPress qui splittent par type
    de contenu : sitemap-pages.xml, sitemap-posts.xml, etc.)."""
    urls = set()
    candidates = deque([urljoin(start_url, "/sitemap.xml"), urljoin(start_url, "/sitemap_index.xml")])
    seen_sitemaps = set()

    while candidates:
        sitemap_url = candidates.popleft()
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)

        try:
            resp = requests.get(sitemap_url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.content, "xml")

            # Sitemap index -> pointe vers d'autres sitemaps
            for sm in soup.find_all("sitemap"):
                loc = sm.find("loc")
                if loc and loc.text.strip() not in seen_sitemaps:
                    candidates.append(loc.text.strip())

            # URLs de pages
            for url_tag in soup.find_all("url"):
                loc = url_tag.find("loc")
                if loc:
                    urls.add(normalize_url(loc.text.strip()))
        except Exception as e:
            print(f"  (sitemap ignore : {sitemap_url} -> {e})")
            continue

    return urls


def crawl_site(start_url, max_pages=MAX_PAGES):
    """Crawl recursif classique des liens internes, en complement du sitemap."""
    base_domain = urlparse(start_url).netloc
    visited = set()
    to_visit = deque([start_url])
    found_urls = []

    while to_visit and len(visited) < max_pages:
        url = to_visit.popleft()
        norm_url = normalize_url(url)
        if norm_url in visited:
            continue
        visited.add(norm_url)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            found_urls.append(norm_url)
            print(f"[crawl {len(found_urls)}] Trouve : {norm_url}")

            for link in soup.find_all("a", href=True):
                full_url = normalize_url(urljoin(url, link["href"]))
                if is_valid_page(full_url, base_domain) and full_url not in visited:
                    to_visit.append(full_url)

        except requests.RequestException as e:
            print(f"Erreur sur {url}: {e}")

        time.sleep(DELAY_SECONDS)

    return found_urls


def check_if_js_site(url):
    """Alerte simple : si tres peu de texte est trouve dans le HTML brut,
    le site est probablement rendu en JavaScript cote client."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        text_length = len(soup.get_text(strip=True))
        if text_length < 200:
            print(
                "\n⚠️  ATTENTION : tres peu de texte detecte dans le HTML brut.\n"
                "   Ce site est probablement construit en JavaScript (React/Vue/etc.).\n"
                "   Ce crawler risque de manquer du contenu.\n"
                "   Remplace 'requests' par Playwright pour un rendu complet.\n"
            )
    except requests.RequestException:
        pass


def main():
    check_if_js_site(START_URL)
    base_domain = urlparse(START_URL).netloc

    print("Recherche d'un sitemap.xml...")
    sitemap_urls = discover_from_sitemap(START_URL)
    sitemap_urls = {u for u in sitemap_urls if is_valid_page(u, base_domain)}
    print(f"  {len(sitemap_urls)} URLs trouvees via sitemap.")

    print("\nCrawl recursif des liens (complement)...")
    crawled_urls = set(crawl_site(START_URL))
    print(f"  {len(crawled_urls)} URLs trouvees via crawl de liens.")

    all_urls = sorted(sitemap_urls | crawled_urls)[:MAX_PAGES]
    only_in_sitemap = sitemap_urls - crawled_urls
    if only_in_sitemap:
        print(f"\n💡 {len(only_in_sitemap)} URL(s) trouvee(s) SEULEMENT via le sitemap "
              f"(probablement des pages non reliees depuis le menu) :")
        for u in sorted(only_in_sitemap)[:10]:
            print(f"   - {u}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_urls, f, ensure_ascii=False, indent=2)

    print(f"\nTermine : {len(all_urls)} pages au total. Liste sauvegardee dans {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# NOTE - Si le site est en JavaScript (React/Vue) :
# Remplace la fonction crawl_site par une version utilisant Playwright :
#
#   from playwright.sync_api import sync_playwright
#
#   with sync_playwright() as p:
#       browser = p.chromium.launch()
#       page = browser.new_page()
#       page.goto(url)
#       html = page.content()   # HTML apres execution du JS
#       browser.close()
#
# Le reste du parsing (BeautifulSoup) reste identique.
# ---------------------------------------------------------------------------