# Test Esami Unimerc

Due strumenti per gli esami all'Università Mercatorum:

| Strumento | A cosa serve | Come si usa |
|---|---|---|
| **App di studio** (`index.html`) | Banca dati domande/risposte, flashcard, quiz con AI | La apri nel browser (PC e telefono) |
| **Scarica dispense** (`dispense.sh`) | Scarica i PDF delle lezioni dal portale LMS nella tua cartella kDrive | Un solo comando nel terminale |

---

## 🚀 Installazione (UNA volta sola)

```bash
git clone -b claude/youthful-volta-gvi4kz https://github.com/Matthewuwu/Test-Esami-Unimerc.git ~/Test-Esami-Unimerc
cd ~/Test-Esami-Unimerc
chmod +x dispense.sh
```

Da qui in poi **non servono altri comandi di installazione o aggiornamento**:
`dispense.sh` si aggiorna e si prepara da solo a ogni avvio.

---

## 📥 Scaricare le dispense

```bash
cd ~/Test-Esami-Unimerc

# basta UN link a una lezione qualsiasi del corso: lo script scopre da solo
# tutte le altre lezioni dello stesso corso e scarica le dispense di ognuna
./dispense.sh "https://lms.mercatorum.multiversity.click/videolezioni/0142509SECSP08I/52"

# con --debug vedi passo passo cosa trova (utile la prima volta su un corso nuovo)
./dispense.sh "https://lms.mercatorum.multiversity.click/videolezioni/0142509SECSP08I/52" --debug

# per scaricare SOLO quella lezione, senza scoprire il resto del corso
./dispense.sh "https://lms.mercatorum.multiversity.click/videolezioni/0142509SECSP08I/52" --solo-queste-lezioni

# più corsi in una volta: mettili (uno o più URL per riga) in scraper/dispense_urls.txt e poi
./dispense.sh
```

- Alla **prima esecuzione** si apre un browser: fai il **login** al portale e premi INVIO nel terminale. Il login resta memorizzato.
- I PDF finiscono in `/home/mattia/kDrive/Universita/Management per l'impresa` (una sottocartella per lezione). Cambi destinazione con `--out "/altro/percorso"`.
- I file già scaricati vengono **saltati**: puoi rilanciare quando vuoi.
- La **scoperta automatica** (verificata e funzionante) apre il pannello "Contenuti del Corso" e clicca ogni riga di lezione per scoprirne l'URL: basta un solo link di partenza per scaricare l'intero corso.

---

## 🎓 App di studio

Apri `index.html` (doppio clic) dalla cartella del progetto — dopo un
aggiornamento è già la versione nuova, perché `dispense.sh` fa anche il `git pull`.

Se il repo è **pubblico** puoi attivare GitHub Pages
(**Settings → Pages → Deploy from a branch → `claude/youthful-volta-gvi4kz` → `/ (root)`**)
e l'app diventa un sito, sempre aggiornato, raggiungibile anche dal telefono:

> `https://matthewuwu.github.io/Test-Esami-Unimerc/`

Dentro l'app:
- **📥 Importa in blocco** — incolla 40-50 coppie `D:`/`R:` alla volta (anche generate con Gemini: c'è il prompt pronto).
- **📖 Studia** — flashcard. **✍️ Quiz** — rispondi e l'AI ti valuta. **🔍 Verifica** — l'AI controlla le risposte salvate (a lotti).
- **💾 Dati** — backup/ripristino in `.json` (i dati vivono nel browser: esporta ogni tanto!).

---

## 🔄 Aggiornamenti

Niente da fare: **ogni `./dispense.sh` si auto-aggiorna**. Per aggiornare solo
l'app senza lanciare lo scraper: `git pull`.

## Struttura del repo

```
index.html                  → l'app di studio (un solo file)
dispense.sh                 → UNICO comando per lo scraper (auto-update + auto-setup)
scraper/
  scarica_dispense.py       → lo scraper vero e proprio
  dispense_urls.txt         → elenco lezioni da scaricare in blocco
  requirements.txt          → dipendenze Python
```
