# Banca Dati Esami — Unimerc

App per studiare gli esami universitari: inserisci tutte le **domande e risposte**
della tua banca dati e usa Claude per **controllare che le risposte siano corrette**
(anti-allucinazioni) e per **valutare le tue risposte** durante il ripasso.

È una singola pagina HTML: funziona su **PC e telefono**, senza installare nulla.

## Come si usa

1. Apri **`index.html`** (doppio clic) oppure pubblicalo su GitHub Pages per averlo come sito.
2. Crea le tue **materie/esami** (pulsante `＋ Materia`).
3. Aggiungi **domande e risposte** nella banca dati:
   - una alla volta col modulo, **oppure**
   - **📥 Importa in blocco**: incolla anche 40-50 coppie alla volta (formato
     `D:` / `R:`, o JSON). Se hai solo le domande, l'app ti dà un **prompt pronto
     per Gemini**: lo incolli in Gemini con le domande, e la sua risposta entra
     nell'app senza ritocchi.
4. Usa i pulsanti in alto:
   - **📖 Studia** — flashcard: leggi la domanda e riveli la risposta.
   - **✍️ Quiz** — scrivi la tua risposta e Claude la valuta con un voto.
   - **🔍 Verifica** — Claude controlla che le risposte salvate siano corrette.
     Le banche dati grandi (**500-600 domande**) vengono controllate **a lotti**
     (es. 20 per volta), saltando quelle già verificate: puoi fermarti e
     riprendere quando vuoi. In modalità API i lotti scorrono in automatico.
   - **💾 Dati** — backup (esporta/importa `.json`) e copia della banca dati.

I dati sono salvati nel **browser** (localStorage). Usa **💾 Dati → Esporta backup**
per non perderli o per spostarli su un altro dispositivo.

## Controllo AI: due modalità (⚙️ Impostazioni)

- **Abbonamento Claude (consigliata, gratis)** — l'app prepara un prompt già pronto:
  lo **copi in Claude Code** (o nell'app Claude / Claude.ai), incolli indietro la
  risposta e l'app la interpreta da sola. Usa l'abbonamento che hai già, **senza
  consumare token a pagamento**.
- **Chiave API (automatica)** — controllo con un clic, ma consuma token API.
  Inserisci la tua chiave (`console.anthropic.com`); resta solo nel tuo browser.

## Pubblicare come sito (opzionale)

GitHub → **Settings → Pages → Branch: main → /(root)**. L'app sarà raggiungibile
da qualsiasi dispositivo via browser.

---

## Scaricare le dispense PDF (script locale) — `scarica_dispense.py`

Strumento **separato** dall'app (uno script Python che gira sul tuo PC Linux):
scarica le dispense PDF da **Unimercatorum** riusando la tua sessione di login,
e le salva in `/home/mattia/kDrive/Universita/Management per l'impresa`.

> ⚠️ L'app HTML nel browser **non può** fare questo (blocco CORS + impossibile
> scrivere in cartelle arbitrarie). Per lo scraping con login serve un programma
> locale: ecco perché è uno script a parte.

### Installazione (una volta)

```bash
pip install -r requirements.txt
playwright install chromium
```

### Uso

```bash
# 1ª volta: si apre una finestra, fai il LOGIN a Unimercatorum, poi premi INVIO
python3 scarica_dispense.py "https://www.unimercatorum.it/.../pagina-del-corso"

# più pagine insieme
python3 scarica_dispense.py URL1 URL2 URL3

# oppure metti gli URL (uno per riga) in dispense_urls.txt e lancia senza argomenti
python3 scarica_dispense.py

# per vedere cosa trova SENZA scaricare (utile per tarare)
python3 scarica_dispense.py "URL" --debug

# dopo il primo login, puoi girare senza finestra
python3 scarica_dispense.py --headless
```

Il login viene chiesto **una sola volta**: la sessione resta salvata in
`~/.config/scarica-dispense/profilo`. I file già scaricati vengono saltati.
La cartella di destinazione si cambia in cima allo script (`CARTELLA_DESTINAZIONE`)
o con `--out`.

