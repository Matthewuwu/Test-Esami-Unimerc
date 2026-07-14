#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scarica_dispense.py — Scarica le dispense PDF da Unimercatorum (o portali simili)
riusando la TUA sessione autenticata (login fatto una volta in un browser vero).

Come funziona
-------------
1. Apre un Chromium (Playwright) con un profilo salvato in locale.
2. Alla prima esecuzione fai il LOGIN a mano nella finestra che si apre;
   la sessione resta memorizzata (le volte successive non serve rifarlo).
3. Per ogni pagina che gli indichi (pagine dei corsi / lezioni), espande le
   sezioni "Dispense" e scarica tutti i PDF che trova nella cartella di destinazione.

Uso tipico
----------
    # prima volta: fai il login nella finestra, poi ENTER nel terminale
    python3 scarica_dispense.py "https://.../pagina-del-corso"

    # più pagine insieme
    python3 scarica_dispense.py URL1 URL2 URL3

    # oppure metti gli URL (uno per riga) in dispense_urls.txt e lancia:
    python3 scarica_dispense.py

    # senza finestra (dopo il primo login):  --headless
    # per capire cosa trova senza scaricare:  --debug

Requisiti
---------
    pip install playwright
    playwright install chromium
"""

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("❌ Manca Playwright.  Installa con:\n"
             "   pip install playwright\n"
             "   playwright install chromium")

# ============================================================
# CONFIGURAZIONE  (modifica qui se serve)
# ============================================================
CARTELLA_DESTINAZIONE = "/home/mattia/kDrive/Universita/Management per l'impresa"

# Dominio del portale: usato per capire cosa è "interno" e per il login.
DOMINIO = "unimercatorum.it"

# Cartella dove viene salvata la sessione del browser (login persistente).
PROFILO = str(Path.home() / ".config" / "scarica-dispense" / "profilo")

# Parole che identificano un link/sezione "dispensa".
PAROLE_DISPENSA = ["dispens", "materiale", "slide", "pdf", "download", "scarica"]


# ============================================================
# UTILITÀ
# ============================================================
def pulisci_nome(nome: str) -> str:
    """Rende un testo utilizzabile come nome file."""
    nome = unquote(nome).strip()
    nome = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome[:150] or "dispensa"


def nome_da_url(url: str) -> str:
    base = os.path.basename(urlparse(url).path)
    return pulisci_nome(base) if base else ""


def e_pdf(headers: dict) -> bool:
    ct = (headers or {}).get("content-type", "").lower()
    return "application/pdf" in ct


def nome_da_disposition(headers: dict):
    cd = (headers or {}).get("content-disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^"\r\n;]+)', cd, re.I)
    return pulisci_nome(m.group(1)) if m else None


# ============================================================
# SCARICAMENTO
# ============================================================
def salva_pdf(context, url: str, cartella: Path, nome_suggerito: str, debug: bool) -> bool:
    """Scarica un PDF usando la sessione autenticata del browser."""
    try:
        resp = context.request.get(url)
    except Exception as e:
        print(f"   ⚠️  errore rete {url}: {e}")
        return False
    if not resp.ok:
        if debug:
            print(f"   ⚠️  {resp.status} su {url}")
        return False

    headers = resp.headers
    if not e_pdf(headers):
        if debug:
            print(f"   ↷  non è un PDF ({headers.get('content-type','?')}): {url}")
        return False

    nome = nome_da_disposition(headers) or nome_da_url(url) or pulisci_nome(nome_suggerito)
    if not nome.lower().endswith(".pdf"):
        nome += ".pdf"

    cartella.mkdir(parents=True, exist_ok=True)
    dest = cartella / nome
    if dest.exists() and dest.stat().st_size > 0:
        print(f"   ⏭️  già presente: {nome}")
        return False

    dest.write_bytes(resp.body())
    print(f"   ✅ scaricato: {nome}  ({dest.stat().st_size // 1024} KB)")
    return True


def trova_url_pdf_nella_pagina(page):
    """Se la pagina corrente È un PDF o ne incorpora uno, restituisce l'URL."""
    # 1) la pagina stessa è un PDF (l'URL finisce in .pdf)
    if urlparse(page.url).path.lower().endswith(".pdf"):
        return page.url
    # 2) PDF incorporato via iframe / embed / object
    for sel in ["iframe", "embed", "object"]:
        for el in page.query_selector_all(sel):
            src = el.get_attribute("src") or el.get_attribute("data") or ""
            if src and (".pdf" in src.lower()):
                return urljoin(page.url, src)
    # 3) un link diretto al pdf nella pagina
    for a in page.query_selector_all("a[href]"):
        href = a.get_attribute("href") or ""
        if href.lower().split("?")[0].endswith(".pdf"):
            return urljoin(page.url, href)
    return None


def espandi_sezioni_dispense(page):
    """Clicca elementi che sembrano toggle/accordion di 'Dispense' per rivelarne i link."""
    provati = 0
    for parola in ["Dispens", "Dispense", "Materiale", "Materiali"]:
        for el in page.query_selector_all(f"text=/{parola}/i"):
            try:
                if el.is_visible():
                    el.click(timeout=1500)
                    page.wait_for_timeout(400)
                    provati += 1
            except Exception:
                pass
        if provati:
            break
    if provati:
        page.wait_for_timeout(600)


def raccogli_link_candidati(page):
    """Ritorna [(url, testo)] dei link che sembrano dispense/PDF."""
    candidati = []
    for a in page.query_selector_all("a[href]"):
        href = a.get_attribute("href") or ""
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = urljoin(page.url, href)
        testo = (a.inner_text() or "").strip()
        low = (href + " " + testo).lower()
        pare_pdf = href.lower().split("?")[0].endswith(".pdf")
        pare_dispensa = any(p in low for p in PAROLE_DISPENSA)
        if pare_pdf or pare_dispensa:
            candidati.append((url, testo or nome_da_url(url) or "dispensa"))
    # dedup mantenendo l'ordine
    visti, out = set(), []
    for url, testo in candidati:
        if url not in visti:
            visti.add(url)
            out.append((url, testo))
    return out


def elabora_pagina(context, url_pagina: str, cartella_base: Path, debug: bool) -> int:
    page = context.new_page()
    scaricati = 0
    try:
        print(f"\n🌐 Apro: {url_pagina}")
        page.goto(url_pagina, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)
        espandi_sezioni_dispense(page)

        # nome cartella del corso = titolo pagina
        titolo = pulisci_nome(page.title() or "corso")
        cartella = cartella_base / titolo if titolo else cartella_base

        candidati = raccogli_link_candidati(page)
        print(f"   🔎 trovati {len(candidati)} link candidati")
        if debug:
            for u, t in candidati:
                print(f"      • {t[:60]!r} -> {u}")

        for url, testo in candidati:
            # prova a scaricarlo direttamente
            if salva_pdf(context, url, cartella, testo, debug):
                scaricati += 1
                continue
            # altrimenti apre la pagina: potrebbe ESSERE il pdf o incorporarlo
            try:
                p2 = context.new_page()
                p2.goto(url, wait_until="domcontentloaded", timeout=45000)
                p2.wait_for_timeout(800)
                url_pdf = trova_url_pdf_nella_pagina(p2)
                p2.close()
                if url_pdf and salva_pdf(context, url_pdf, cartella, testo, debug):
                    scaricati += 1
            except Exception as e:
                if debug:
                    print(f"   ⚠️  {url}: {e}")
    finally:
        page.close()
    return scaricati


# ============================================================
# LOGIN
# ============================================================
def assicura_login(context, headless: bool):
    page = context.new_page()
    page.goto(f"https://www.{DOMINIO}/", wait_until="domcontentloaded", timeout=45000)
    # euristica: se troviamo un campo password, probabilmente non siamo loggati
    serve_login = page.query_selector("input[type='password']") is not None
    page.close()

    if serve_login:
        if headless:
            sys.exit("🔒 Non risulti loggato ma sei in --headless.\n"
                     "   Lancia una prima volta SENZA --headless per fare il login.")
        print("\n🔐 Fai il LOGIN a Unimercatorum nella finestra che si è aperta.")
        print("   Quando sei dentro e vedi la tua area studenti, torna qui e premi INVIO.")
        input("   ▶️  Premi INVIO per continuare...  ")
    else:
        print("✅ Sessione già attiva (login non necessario).")


# ============================================================
# MAIN
# ============================================================
def leggi_urls(args_urls):
    if args_urls:
        return args_urls
    f = Path(__file__).with_name("dispense_urls.txt")
    if f.exists():
        return [r.strip() for r in f.read_text(encoding="utf-8").splitlines()
                if r.strip() and not r.strip().startswith("#")]
    return []


def main():
    ap = argparse.ArgumentParser(description="Scarica le dispense PDF da Unimercatorum.")
    ap.add_argument("urls", nargs="*", help="URL delle pagine corso/lezione con le dispense")
    ap.add_argument("--headless", action="store_true", help="Senza finestra (solo dopo il primo login)")
    ap.add_argument("--debug", action="store_true", help="Mostra cosa trova senza scaricare a vuoto")
    ap.add_argument("--out", default=CARTELLA_DESTINAZIONE, help="Cartella di destinazione")
    args = ap.parse_args()

    urls = leggi_urls(args.urls)
    if not urls:
        sys.exit("⚠️  Nessun URL.  Passa gli URL come argomenti, oppure mettili "
                 "(uno per riga) nel file 'dispense_urls.txt' accanto allo script.")

    cartella_base = Path(args.out).expanduser()
    print(f"📁 Destinazione: {cartella_base}")
    Path(PROFILO).mkdir(parents=True, exist_ok=True)

    totale = 0
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            PROFILO,
            headless=args.headless,
            accept_downloads=True,
            viewport={"width": 1280, "height": 900},
        )
        try:
            assicura_login(context, args.headless)
            for url in urls:
                totale += elabora_pagina(context, url, cartella_base, args.debug)
        finally:
            context.close()

    print(f"\n🏁 Fatto. PDF scaricati in questa sessione: {totale}")
    print(f"   Cartella: {cartella_base}")


if __name__ == "__main__":
    main()
