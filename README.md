# Banca Dati Esami — Unimerc

App per studiare gli esami universitari: inserisci tutte le **domande e risposte**
della tua banca dati e usa Claude per **controllare che le risposte siano corrette**
(anti-allucinazioni) e per **valutare le tue risposte** durante il ripasso.

È una singola pagina HTML: funziona su **PC e telefono**, senza installare nulla.

## Come si usa

1. Apri **`index.html`** (doppio clic) oppure pubblicalo su GitHub Pages per averlo come sito.
2. Crea le tue **materie/esami** (pulsante `＋ Materia`).
3. Aggiungi **domande e risposte** nella banca dati.
4. Usa i pulsanti in alto:
   - **📖 Studia** — flashcard: leggi la domanda e riveli la risposta.
   - **✍️ Quiz** — scrivi la tua risposta e Claude la valuta con un voto.
   - **🔍 Verifica** — Claude controlla che le risposte salvate siano corrette.
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
