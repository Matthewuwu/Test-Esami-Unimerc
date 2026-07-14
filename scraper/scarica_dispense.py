#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scarica_dispense.py — Scarica le dispense PDF dal portale LMS Mercatorum (o portali simili)
riusando la TUA sessione autenticata (login fatto una volta in un browser vero).

Come funziona
-------------
1. Apre un Chromium (Playwright) con un profilo salvato in locale.
2. Alla prima esecuzione fai il LOGIN a mano nella finestra che si apre;
   la sessione resta memorizzata (le volte successive non serve rifarlo).
3. Dato UN SOLO URL di lezione, scopre da solo tutte le ALTRE lezioni dello
   stesso corso (pattern .../videolezioni/CODICE/NUMERO nel menù laterale),
   ed espande/scarica le dispense PDF di ognuna nella cartella di destinazione.

Uso tipico
----------
    # basta UNA lezione: trova da sola tutte le altre lezioni dello stesso corso
    python3 scarica_dispense.py "https://.../videolezioni/CODICE/NUMERO"

    # più corsi insieme (ognuno scoperto ed elaborato per intero)
    python3 scarica_dispense.py URL_CORSO_1 URL_CORSO_2

    # oppure metti gli URL (uno per riga) in dispense_urls.txt e lancia:
    python3 scarica_dispense.py

    # per scaricare SOLO gli URL indicati, senza scoprire il resto del corso:
    #   --solo-queste-lezioni
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
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.exit("❌ Manca Playwright.  Installa con:\n"
             "   pip install playwright\n"
             "   playwright install chromium")

# ============================================================
# CONFIGURAZIONE  (modifica qui se serve)
# ============================================================
CARTELLA_DESTINAZIONE = "/home/mattia/kDrive/Universita/Management per l'impresa"

# Dominio del portale (LMS): usato per il controllo del login.
DOMINIO = "lms.mercatorum.multiversity.click"

# Cartella dove viene salvata la sessione del browser (login persistente).
PROFILO = str(Path.home() / ".config" / "scarica-dispense" / "profilo")

# Parole che identificano un link/sezione "dispensa" (ricerca testuale di riserva).
PAROLE_DISPENSA = ["dispens", "materiale", "slide", "pdf", "download", "scarica"]

# ------------------------------------------------------------
# Classi CSS reali del portale (Tailwind), fornite osservando la pagina.
# NOTA: sono classi di STILE, non dicono se l'elemento è un link <a> o un
# div/button cliccabile via JavaScript — lo script gestisce entrambi i casi.
# ------------------------------------------------------------
# Toggle/tab da aprire per rivelare le dispense (es. la voce "Dispense" del menù)
TOGGLE_CLASSI = "align-left flex items-center h-full leading-normal font-medium"
# Riga di ogni singola dispensa, una volta rivelata
DISPENSA_CLASSI = "flex items-center justify-between pr-3 py-3 text-base border-t font-normal hover:bg-platform-hover-light"


def selettore_da_classi(classi: str) -> str:
    """Converte 'a b c:d' (attributo class) in un selettore CSS '.a.b.c\\:d'."""
    return "".join("." + tok.replace(":", r"\:") for tok in classi.split())


TOGGLE_SELECTOR = selettore_da_classi(TOGGLE_CLASSI)
DISPENSA_SELECTOR = selettore_da_classi(DISPENSA_CLASSI)


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


def tutti_i_frame(page):
    """Pagina principale + eventuali iframe annidati (le SPA con visualizzatori
    PDF spesso incorporano il contenuto in un iframe, invisibile alle ricerche
    normali su 'page')."""
    try:
        return list(page.frames)
    except Exception:
        return [page.main_frame]


def diagnosi_pagina(page, debug):
    """Stampa informazioni diagnostiche e (in --debug) salva l'HTML completo
    su file, per capire perché una pagina risulta 'vuota' alle ricerche."""
    if not debug:
        return
    frames = tutti_i_frame(page)
    tot_link = 0
    print(f"   🧭 URL effettivo: {page.url}")
    print(f"   🧭 Titolo: {page.title()!r}")
    print(f"   🧭 Frame nella pagina: {len(frames)}"
          + (f" (di cui {len(frames)-1} iframe)" if len(frames) > 1 else ""))
    for fr in frames:
        try:
            n = len(fr.query_selector_all("a[href]"))
            tot_link += n
            if fr != page.main_frame:
                print(f"      • iframe: {fr.url}  ({n} link <a>)")
        except Exception:
            pass
    print(f"   🧭 Link <a> totali (tutti i frame): {tot_link}")

    try:
        cartella_debug = Path(__file__).with_name("debug_output")
        cartella_debug.mkdir(exist_ok=True)
        dump = cartella_debug / "ultima_pagina.html"
        dump.write_text(page.content(), encoding="utf-8")
        print(f"   💾 HTML completo salvato in: {dump}")
        print(f"      (utile per cercare a mano: grep -io -C2 'dispens' \"{dump}\")")
    except Exception:
        pass


_ATTRIBUTO_TOGGLE_FATTO = "data-sd-toggle-fatto"

# JS: scorre in avanti QUALSIASI contenitore scrollabile della pagina (non solo
# quello delle lezioni), per far comparire righe di eventuali liste
# virtualizzate (accordion con tante sotto-sezioni, dispense, ecc.).
# Ritorna True se ha effettivamente scrollato qualcosa.
_JS_SCORRI_QUALSIASI_CONTENITORE = r"""
() => {
    const contenitori = [...document.querySelectorAll('*')].filter(e => {
        if (e.scrollHeight <= e.clientHeight + 4) return false;
        const overflowY = getComputedStyle(e).overflowY;
        return overflowY === 'auto' || overflowY === 'scroll';
    });
    let scrollato = false;
    for (const el of contenitori) {
        const inFondo = el.scrollTop + el.clientHeight >= el.scrollHeight - 2;
        if (!inFondo) {
            el.scrollTop = Math.min(el.scrollTop + el.clientHeight * 0.7, el.scrollHeight);
            scrollato = true;
        }
    }
    return scrollato;
}
"""


def _icona_toggle(el):
    """Ritorna 'aperto'/'chiuso'/None leggendo l'icona a freccia (chevron)
    vicina all'elemento (sale fino a qualche livello di antenati). Serve per
    NON ricliccare (e quindi richiudere) un toggle già aperto."""
    try:
        html = el.evaluate(
            """(node) => {
                let p = node;
                for (let i = 0; i < 5 && p; i++) {
                    const svg = p.querySelector('svg');
                    if (svg) return svg.outerHTML || '';
                    p = p.parentElement;
                }
                return '';
            }"""
        )
    except Exception:
        return None
    if not html:
        return None
    if "chevron-up" in html:
        return "aperto"
    if "chevron-down" in html:
        return "chiuso"
    return None


def espandi_sezioni_dispense(page, debug=False):
    """Espande TUTTI i pannelli/toggle della pagina (Dispense e qualunque
    accordion annidato, es. i singoli argomenti del corso), scorrendo i
    contenitori per far comparire anche righe di liste virtualizzate.
    Marca ogni elemento nel DOM una volta esaminato (non si basa sul testo,
    che può ripetersi identico in più sezioni, es. tante voci "Dispense").
    Evita di cliccare toggle già aperti (controllo icona chevron). Ritorna
    quanti ne ha effettivamente aperti."""
    selettore_da_fare = TOGGLE_SELECTOR + f":not([{_ATTRIBUTO_TOGGLE_FATTO}])"
    aperti = 0
    esaminati = 0
    giri_senza_novita = 0
    for _ in range(400):  # limite di sicurezza anti-loop-infinito
        trovato_qualcosa = False
        for frame in tutti_i_frame(page):
            try:
                toggles = frame.query_selector_all(selettore_da_fare)
            except Exception:
                continue
            for t in toggles:
                try:
                    t.evaluate(f"el => el.setAttribute('{_ATTRIBUTO_TOGGLE_FATTO}', '1')")
                except Exception:
                    pass
                esaminati += 1
                trovato_qualcosa = True
                stato = _icona_toggle(t)
                if stato == "aperto":
                    continue  # già aperto: non toccarlo o lo richiuderemmo
                try:
                    if t.is_visible():
                        t.click(timeout=1500)
                        page.wait_for_timeout(350)
                        aperti += 1
                except Exception:
                    pass
        if trovato_qualcosa:
            giri_senza_novita = 0
            continue
        # Nessun toggle nuovo in questo giro: prova a scorrere per farne
        # comparire altri (liste virtualizzate).
        try:
            scrollato = page.evaluate(_JS_SCORRI_QUALSIASI_CONTENITORE)
        except Exception:
            scrollato = False
        if scrollato:
            page.wait_for_timeout(350)
            giri_senza_novita = 0
            continue
        giri_senza_novita += 1
        if giri_senza_novita >= 2:
            break

    if debug:
        print(f"   🔧 toggle esaminati (con scroll): {esaminati}, aperti: {aperti}")

    if esaminati == 0:
        # Fallback: ricerca testuale, nel caso la classe sia cambiata o non trovata.
        for frame in tutti_i_frame(page):
            for parola in ["Dispens", "Materiale", "Materiali"]:
                try:
                    elementi = frame.query_selector_all(f"text=/{parola}/i")
                except Exception:
                    continue
                for el in elementi:
                    try:
                        if el.is_visible():
                            el.click(timeout=1500)
                            page.wait_for_timeout(400)
                            aperti += 1
                    except Exception:
                        pass
                if aperti:
                    break
            if aperti:
                break

    if aperti:
        page.wait_for_timeout(500)
    return aperti


def gestisci_click_dispensa(context, page, elemento, cartella, testo, debug):
    """Clicca una riga 'dispensa' senza href e scarica il PDF risultante,
    sia che apra una NUOVA scheda sia che navighi la pagina corrente."""
    url_prima = page.url
    try:
        with context.expect_page(timeout=3000) as info:
            elemento.click(timeout=3000)
        nuova = info.value
        nuova.wait_for_load_state("domcontentloaded", timeout=15000)
        nuova.wait_for_timeout(500)
        url_pdf = trova_url_pdf_nella_pagina(nuova)
        ok = salva_pdf(context, url_pdf, cartella, testo, debug) if url_pdf else False
        if not url_pdf and debug:
            print(f"   ↷  nuova scheda ma nessun PDF individuato: {nuova.url}")
        nuova.close()
        return ok
    except PWTimeout:
        # Nessuna nuova scheda: probabilmente ha navigato la pagina corrente.
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(600)
        ok = False
        if page.url != url_prima:
            url_pdf = trova_url_pdf_nella_pagina(page)
            if url_pdf:
                ok = salva_pdf(context, url_pdf, cartella, testo, debug)
            elif debug:
                print(f"   ↷  pagina navigata ma nessun PDF individuato: {page.url}")
            try:
                page.go_back(wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(500)
            except Exception:
                pass
        elif debug:
            print("   ↷  il click non ha aperto nulla di rilevabile")
        return ok
    except Exception as e:
        if debug:
            print(f"   ⚠️  errore sul click: {e}")
        return False


def _tutte_le_righe_dispensa(page):
    """Ritorna [(frame, elemento)] per ogni riga dispensa in qualsiasi frame."""
    righe = []
    for frame in tutti_i_frame(page):
        try:
            for el in frame.query_selector_all(DISPENSA_SELECTOR):
                righe.append((frame, el))
        except Exception:
            pass
    return righe


_ATTRIBUTO_DISPENSA_FATTA = "data-sd-dispensa-fatta"


def raccogli_ed_estrai_dispense(context, page, cartella, debug):
    """Trova le righe 'dispensa' (classe dedicata, in qualsiasi frame) e scarica
    ciò che trovano, sia link diretti (<a href>) sia righe cliccabili via JS.
    Loop unico: prova a processare una riga nuova; se non ce ne sono, prova ad
    aprire altri toggle (potrebbero rivelarne altre, es. dentro un argomento
    del corso appena espanso) e a scorrere eventuali contenitori virtualizzati.
    Si ferma solo quando nessuna delle tre cose produce più niente di nuovo."""
    scaricati = 0
    prima_volta = True
    giri_senza_novita = 0
    for _ in range(2000):  # limite di sicurezza anti-loop-infinito
        righe = _tutte_le_righe_dispensa(page)
        if prima_volta:
            if debug:
                print(f"   📚 righe dispensa individuate (tutti i frame): {len(righe)}")
            prima_volta = False

        riga_da_fare = None
        for frame, el in righe:
            try:
                gia_fatta = el.get_attribute(_ATTRIBUTO_DISPENSA_FATTA)
            except Exception:
                gia_fatta = None
            if not gia_fatta:
                riga_da_fare = (frame, el)
                break

        if riga_da_fare is not None:
            frame, el = riga_da_fare
            try:
                el.evaluate(f"el => el.setAttribute('{_ATTRIBUTO_DISPENSA_FATTA}', '1')")
            except Exception:
                pass
            testo = (el.inner_text() or "").strip() or "dispensa"
            href = el.get_attribute("href")
            if not href:
                figlio = el.query_selector("a[href]")
                href = figlio.get_attribute("href") if figlio else None

            ok = False
            if href:
                url = urljoin(frame.url, href)
                ok = salva_pdf(context, url, cartella, testo, debug)
                if not ok:
                    try:
                        tmp = context.new_page()
                        tmp.goto(url, wait_until="domcontentloaded", timeout=30000)
                        tmp.wait_for_timeout(600)
                        url_pdf = trova_url_pdf_nella_pagina(tmp)
                        tmp.close()
                        if url_pdf:
                            ok = salva_pdf(context, url_pdf, cartella, testo, debug)
                    except Exception as e:
                        if debug:
                            print(f"   ⚠️  {url}: {e}")
            else:
                ok = gestisci_click_dispensa(context, page, el, cartella, testo, debug)

            if ok:
                scaricati += 1
            giri_senza_novita = 0
            continue

        # Nessuna riga dispensa nuova: forse aprendo altri toggle (es. un
        # argomento del corso non ancora esaminato) ne comparirebbero altre.
        aperti = espandi_sezioni_dispense(page, debug=False)
        if aperti:
            page.wait_for_timeout(400)
            giri_senza_novita = 0
            continue

        # Ancora nulla: prova a scorrere eventuali contenitori virtualizzati.
        try:
            scrollato = page.evaluate(_JS_SCORRI_QUALSIASI_CONTENITORE)
        except Exception:
            scrollato = False
        if scrollato:
            page.wait_for_timeout(400)
            giri_senza_novita = 0
            continue

        giri_senza_novita += 1
        if giri_senza_novita >= 2:
            break

    return scaricati


def raccogli_link_candidati(page):
    """Ritorna [(url, testo)] dei link che sembrano dispense/PDF (in qualsiasi frame)."""
    candidati = []
    for frame in tutti_i_frame(page):
        try:
            links = frame.query_selector_all("a[href]")
        except Exception:
            continue
        for a in links:
            href = a.get_attribute("href") or ""
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            url = urljoin(frame.url, href)
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
        # Le web-app moderne (React/Vue) montano i contenuti DOPO il
        # caricamento del documento: aspettiamo anche la rete "a riposo",
        # ma senza bloccarci se la pagina fa polling continuo (es. notifiche).
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except PWTimeout:
            pass
        page.wait_for_timeout(2000)

        diagnosi_pagina(page, debug)

        # nome cartella del corso = titolo pagina
        titolo = pulisci_nome(page.title() or "corso")
        cartella = cartella_base / titolo if titolo else cartella_base

        aperti = espandi_sezioni_dispense(page, debug)
        if debug:
            print(f"   🔧 sezioni aperte: {aperti}")

        # Via principale: righe 'dispensa' con la classe dedicata del portale.
        n = raccogli_ed_estrai_dispense(context, page, cartella, debug)
        print(f"   📄 dispense scaricate (righe dedicate): {n}")
        scaricati += n

        # Rete di sicurezza: scansione generica di link, nel caso qualche PDF
        # non sia dentro le righe con la classe dedicata.
        candidati = raccogli_link_candidati(page)
        print(f"   🔎 trovati {len(candidati)} link candidati aggiuntivi")
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
# SCOPERTA AUTOMATICA DELLE ALTRE LEZIONI DELLO STESSO CORSO
# ============================================================
def estrai_codice_corso(url):
    """Da '.../videolezioni/CODICE/NUMERO' estrae CODICE."""
    m = re.search(r"/videolezioni/([^/?#]+)/\d+", url)
    return m.group(1) if m else None


"""
NOTA sulla scoperta (analisi HTML reale del 2026-07-14)
--------------------------------------------------------
Il pannello "Contenuti del Corso" NON usa link <a href> per le lezioni: sono
<div> cliccabili gestiti via JS/router (stessa app Vue/Tailwind delle
dispense). Le righe di lezione hanno la STESSA classe del toggle
(TOGGLE_SELECTOR / TOGGLE_CLASSI) e testo tipo "1 - Le risorse nel sistema
impresa", "2 - Le competenze", ecc. Non c'è quindi nulla da "espandere" via
aria-expanded (quell'attributo non compare nell'HTML del portale): bisogna
invece CLICCARE ogni riga numerata e leggere l'URL a cui porta.
"""

PATTERN_RIGA_LEZIONE = re.compile(r"^\s*(\d+)\s*-\s*.+")


def _righe_lezione_candidate(page):
    """Ritorna [(elemento, testo)] delle righe che sembrano lezioni del corso
    (stessa classe dei toggle, testo del tipo 'N - Titolo')."""
    righe = []
    for frame in tutti_i_frame(page):
        try:
            elementi = frame.query_selector_all(TOGGLE_SELECTOR)
        except Exception:
            continue
        for el in elementi:
            try:
                testo = (el.inner_text() or "").strip()
            except Exception:
                continue
            if PATTERN_RIGA_LEZIONE.match(testo):
                righe.append((el, testo))
    return righe


def _espandi_pannello_lezioni(page, debug=False):
    """Clicca il toggle di livello superiore (testo esatto 'lezioni') del
    pannello 'Contenuti del Corso', se presente e non già aperto."""
    aperti = 0
    for frame in tutti_i_frame(page):
        try:
            elementi = frame.query_selector_all(TOGGLE_SELECTOR)
        except Exception:
            continue
        for el in elementi:
            try:
                testo = (el.inner_text() or "").strip().lower()
            except Exception:
                continue
            if testo == "lezioni":
                try:
                    if el.is_visible():
                        el.click(timeout=1500)
                        page.wait_for_timeout(400)
                        aperti += 1
                except Exception:
                    pass
    if debug:
        print(f"   📂 pannello 'lezioni' aperto: {aperti}")
    if aperti:
        page.wait_for_timeout(500)
    return aperti


# JS: la lista delle lezioni può essere "virtualizzata" (l'app monta nel DOM
# solo le righe vicine alla posizione di scroll, per non appesantire il
# rendering di corsi con tante lezioni). Bisogna quindi scorrere il
# contenitore per far comparire via via tutte le righe, non basta espandere
# una volta sola. Trova il contenitore scrollabile risalendo dagli antenati
# della prima riga "N - Titolo" trovata.
_JS_SCORRI_CONTENITORE_LEZIONI = r"""
() => {
    const righe = [...document.querySelectorAll('div')].filter(e =>
        e.children.length === 0 &&
        /^\s*\d+\s*-\s*.+/.test((e.textContent || '').trim())
    );
    if (!righe.length) return null;
    let el = righe[0];
    while (el && el.scrollHeight <= el.clientHeight + 2 && el.parentElement) {
        el = el.parentElement;
    }
    if (!el) return null;
    const prima = el.scrollTop;
    const inFondo = el.scrollTop + el.clientHeight >= el.scrollHeight - 2;
    if (!inFondo) {
        el.scrollTop = Math.min(el.scrollTop + el.clientHeight * 0.7, el.scrollHeight);
    }
    return {prima, dopo: el.scrollTop, inFondo};
}
"""


def _scorri_pannello_lezioni(page):
    """Scorre in avanti il contenitore della lista lezioni. Ritorna True se ha
    effettivamente scrollato (cioè non era già arrivato in fondo)."""
    try:
        risultato = page.evaluate(_JS_SCORRI_CONTENITORE_LEZIONI)
    except Exception:
        return False
    if not risultato:
        return False
    if risultato.get("inFondo"):
        return False
    return risultato.get("dopo") != risultato.get("prima")


def scopri_lezioni_corso(context, url_iniziale, debug):
    """Apre la pagina di partenza, apre il pannello 'Contenuti del Corso' e
    clicca ogni riga di lezione (scorrendo la lista, che può essere
    virtualizzata) per scoprire l'URL a cui porta.
    Ritorna {numero_lezione: url}."""
    codice = estrai_codice_corso(url_iniziale)
    if not codice:
        if debug:
            print(f"   ⚠️  URL non riconosciuto come lezione del portale: {url_iniziale}")
        return {}

    pattern_url = re.compile(r"/videolezioni/" + re.escape(codice) + r"/(\d+)")
    # La lezione di partenza è comunque nota.
    m0 = pattern_url.search(url_iniziale)
    trovate = {m0.group(1): url_iniziale} if m0 else {}

    page = context.new_page()
    try:
        page.goto(url_iniziale, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except PWTimeout:
            pass
        page.wait_for_timeout(1500)

        righe = _righe_lezione_candidate(page)
        if not righe:
            _espandi_pannello_lezioni(page, debug)
            righe = _righe_lezione_candidate(page)

        if debug:
            print(f"   📚 righe lezione individuate all'apertura: {len(righe)} (la lista potrebbe essere virtualizzata: proseguo scorrendo)")

        testi_elaborati = set()
        giri_senza_novita = 0
        MAX_GIRI = 300  # sicurezza anti-loop-infinito (corsi con centinaia di lezioni)

        for _ in range(MAX_GIRI):
            righe_correnti = _righe_lezione_candidate(page)
            if not righe_correnti:
                _espandi_pannello_lezioni(page, debug=False)
                righe_correnti = _righe_lezione_candidate(page)

            riga_da_cliccare = None
            for el, testo in righe_correnti:
                if testo not in testi_elaborati:
                    riga_da_cliccare = (el, testo)
                    break

            if riga_da_cliccare is None:
                # Nessuna riga nuova visibile: prova a scorrere la lista.
                if _scorri_pannello_lezioni(page):
                    page.wait_for_timeout(400)
                    giri_senza_novita = 0
                    continue
                giri_senza_novita += 1
                if giri_senza_novita >= 3:
                    break
                page.wait_for_timeout(300)
                continue

            giri_senza_novita = 0
            el, testo = riga_da_cliccare
            testi_elaborati.add(testo)  # marcato SUBITO: evita loop infiniti se il click fallisce
            url_prima = page.url
            try:
                if el.is_visible():
                    el.click(timeout=2000)
                    page.wait_for_timeout(700)
                    m = pattern_url.search(page.url)
                    if m:
                        nuovo = m.group(1) not in trovate
                        trovate[m.group(1)] = page.url
                        if debug:
                            segno = "➕" if nuovo else "="
                            print(f"      {segno} {testo!r} -> lezione {m.group(1)}: {page.url}")
                    elif debug:
                        print(f"      ↷ {testo!r}: URL non riconosciuto dopo il click ({page.url})")
                    if page.url != url_prima:
                        page.go_back(wait_until="domcontentloaded", timeout=15000)
                        try:
                            page.wait_for_load_state("networkidle", timeout=8000)
                        except PWTimeout:
                            pass
                        page.wait_for_timeout(700)
                        if not _righe_lezione_candidate(page):
                            _espandi_pannello_lezioni(page, debug=False)
                elif debug:
                    print(f"      ↷ riga non visibile: {testo!r}")
            except Exception as e:
                if debug:
                    print(f"      ⚠️  errore sulla riga {testo!r}: {e}")
        else:
            if debug:
                print(f"   ⚠️  raggiunto il limite di sicurezza ({MAX_GIRI} giri): mi fermo qui")
    except Exception as e:
        if debug:
            print(f"   ⚠️  scoperta lezioni fallita: {e}")
    finally:
        page.close()
    return trovate


def espandi_con_scoperta_corso(context, urls_iniziali, debug):
    """Per ogni URL iniziale, scopre automaticamente le altre lezioni dello
    stesso corso e le aggiunge all'elenco da elaborare (senza duplicati)."""
    risultato = list(dict.fromkeys(urls_iniziali))  # dedup, mantiene l'ordine
    corsi_gia_scoperti = set()

    for url in urls_iniziali:
        codice = estrai_codice_corso(url)
        if not codice or codice in corsi_gia_scoperti:
            continue
        corsi_gia_scoperti.add(codice)
        print(f"\n🔎 Scoperta automatica delle lezioni del corso «{codice}»...")
        trovate = scopri_lezioni_corso(context, url, debug)
        nuove = [u for u in trovate.values() if u not in risultato]
        if trovate and nuove:
            print(f"   ➕ {len(trovate)} lezioni individuate nel corso, {len(nuove)} nuove aggiunte")
            risultato.extend(nuove)
        elif trovate:
            print(f"   ✅ {len(trovate)} lezioni individuate, già tutte nell'elenco")
        else:
            print("   ⚠️  nessuna lezione aggiuntiva trovata: userò solo l'URL indicato")

    return risultato


# ============================================================
# LOGIN
# ============================================================
def assicura_login(context, headless: bool, url_prova: str = None):
    page = context.new_page()
    # Usa una pagina reale del portale (più affidabile della home per capire
    # se siamo autenticati): quella passata da riga di comando, o il dominio base.
    target = url_prova or f"https://{DOMINIO}/"
    page.goto(target, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1000)
    # euristica: se troviamo un campo password, o veniamo rimandati a una
    # pagina di login, probabilmente non siamo autenticati.
    ha_campo_password = page.query_selector("input[type='password']") is not None
    sembra_login = bool(re.search(r"login|accedi|sign[-_]?in", page.url, re.I))
    serve_login = ha_campo_password or sembra_login

    if serve_login:
        if headless:
            page.close()
            sys.exit("🔒 Non risulti loggato ma sei in --headless.\n"
                     "   Lancia una prima volta SENZA --headless per fare il login.")
        # IMPORTANTE: la pagina resta aperta apposta — è quella su cui fai il login.
        # Chiuderla adesso (come faceva una versione precedente) la fa sparire
        # e appare "about:blank" prima ancora che tu possa accedere.
        print("\n🔐 Fai il LOGIN al portale nella finestra che si è aperta.")
        print("   Quando sei dentro e vedi la tua area studenti, torna qui e premi INVIO.")
        input("   ▶️  Premi INVIO per continuare...  ")
    else:
        print("✅ Sessione già attiva (login non necessario).")

    page.close()


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
    ap = argparse.ArgumentParser(description="Scarica le dispense PDF dal portale LMS Mercatorum.")
    ap.add_argument("urls", nargs="*", help="URL delle pagine corso/lezione con le dispense")
    ap.add_argument("--headless", action="store_true", help="Senza finestra (solo dopo il primo login)")
    ap.add_argument("--debug", action="store_true", help="Mostra cosa trova senza scaricare a vuoto")
    ap.add_argument("--out", default=CARTELLA_DESTINAZIONE, help="Cartella di destinazione")
    ap.add_argument("--solo-queste-lezioni", action="store_true",
                     help="Scarica SOLO gli URL indicati, senza scoprire "
                          "automaticamente le altre lezioni dello stesso corso")
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
            assicura_login(context, args.headless, url_prova=urls[0])

            if args.solo_queste_lezioni:
                urls_da_elaborare = urls
            else:
                urls_da_elaborare = espandi_con_scoperta_corso(context, urls, args.debug)

            print(f"\n📋 Lezioni totali da elaborare: {len(urls_da_elaborare)}")
            for url in urls_da_elaborare:
                totale += elabora_pagina(context, url, cartella_base, args.debug)
        finally:
            context.close()

    print(f"\n🏁 Fatto. PDF scaricati in questa sessione: {totale}")
    print(f"   Cartella: {cartella_base}")


if __name__ == "__main__":
    main()
