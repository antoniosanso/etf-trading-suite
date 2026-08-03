# ETF Trading Suite — Operating Context

Ultimo aggiornamento: 2026-08-03

## Scopo

Questi file conservano il contesto operativo della piattaforma di trading e devono essere letti prima di analisi, modifiche al codice o indicazioni su operazioni reali:

- `README_OPS.md`: stato, principi e confini operativi;
- `DECISIONS.md`: decisioni consolidate e correzioni metodologiche;
- `RUNBOOK.md`: controlli obbligatori e sequenza di lavoro.

Non sostituiscono il `README.md` tecnico dei repository e non devono duplicarne comandi, dipendenze o istruzioni di installazione.

## Repository e responsabilità

Il progetto è diviso logicamente in due componenti:

1. **ETF datalake**
   - mantiene anagrafica e storico OHLCV degli ETF;
   - include almeno `SEME.MI`, `XAIX` e `TNOW`;
   - aggiorna i prezzi con frequenza giornaliera;
   - deve segnalare data/ora dell'ultimo dato e anomalie di qualità.

2. **Trading suite**
   - legge i dati validati dal datalake;
   - calcola segnali, livelli, rischio e report operativi;
   - esegue backtest e confronti tra strategie;
   - non deve presentare una stima come certezza o un backtest come garanzia.

Repository:

- Trading Suite: `antoniosanso/etf-trading-suite`
- Datalake: `antoniosanso/etf-datalake`

## Architettura e workflow attuali

- Il datalake esegue ingestion, normalizzazione e quality gate e pubblica i dataset validati.
- Il quality gate scrive `latest/quality-report.json`; il flusso operativo deve fermarsi se freschezza, validità o completezza non superano le soglie.
- La suite legge il datalake in sola lettura ed esegue sanity check, backtest, walk-forward, guardrail, segnali e report.
- Workflow datalake: `Update validated ETF universe` nei giorni feriali.
- Workflow suite: `Trading suite from validated datalake`, dopo il completamento del datalake.
- Output principali: `outputs/signals/entries_today.csv`, `watchlist_today.csv`, `summary.md`, `outputs/operational_report.md`, KPI ed equity curve.

Le soglie di guardrail attualmente implementate sono Sharpe >= 0,30, Profit Factor >= 1,10, max drawdown assoluto <= 35% e walk-forward Calmar CoV <= 30% con `wf_trim: 1`. Sono filtri di qualità del backtest, non autorizzazioni automatiche a operare: borderline o dati incompleti devono produrre `YELLOW`, violazioni nette `RED`.

I nomi, i percorsi e i comandi effettivi devono essere ricavati dal contenuto reale dei repository. Non vanno inventati se il repository non è disponibile.

## Universo operativo

Priorità attuale:

1. `SEME.MI` — iShares MSCI Global Semiconductors UCITS ETF;
2. `XAIX`;
3. `TNOW`.

La strategia va prima progettata e validata su un singolo ETF. Solo dopo controlli out-of-sample e di robustezza può essere verificata sugli altri strumenti. Non ottimizzare contemporaneamente l'intero universo per ottenere artificialmente un risultato migliore.

## Obiettivo e vincoli

- Capitale di riferimento indicativo: circa **105.000 EUR**.
- Orizzonte tipico: trade di pochi giorni, con obiettivo indicativo **5–10%**.
- L'obiettivo non è un rendimento atteso né una giustificazione per forzare un ingresso.
- Nessun ordine deve essere dimensionato partendo dal capitale disponibile.
- Sequenza obbligatoria: invalidazione tecnica → perdita massima accettabile → quantità → piano di uscita.
- Stop, target e condizioni di annullamento vanno definiti prima dell'ingresso.
- Preferire ingressi selettivi vicino a livelli verificati e con conferma; evitare inseguimenti e medie automatiche al ribasso.
- Le uscite frazionate sono ammesse quando migliorano il rapporto tra protezione del risultato e partecipazione al rialzo.

## Stato operativo noto

Alla data del 2026-08-03:

- posizione `SEME.MI`: **nessuna quota detenuta**;
- ultimo ingresso noto: 6.950 quote a 15,467 EUR il 2026-07-29;
- prima uscita: 2.500 quote a 16,55 EUR;
- tutte le quote residue sono state vendute venerdì 2026-07-31 tra 16,85 e 17,03 EUR;
- qualsiasi nuova analisi su SEME riguarda quindi un **nuovo ingresso**, non la gestione della posizione precedente.

Lo stato della posizione è temporaneo: prima di ogni nuova indicazione deve essere riconfermato con l'utente o con una fonte di portafoglio aggiornata.

## Fonti e gerarchia dei dati

Per ogni analisi usare, in ordine:

1. dati del datalake, se disponibili e aggiornati;
2. fonte ufficiale dell'emittente o della borsa;
3. provider pubblico affidabile come controllo incrociato.

Per decisioni intraday, i dati end-of-day non sono sufficienti. Ogni prezzo deve riportare almeno strumento/listing, valuta, data e ora, natura del dato (real-time, ritardato o close) e fonte.

Se due fonti non coincidono, non scegliere silenziosamente quella più conveniente: verificare ticker, borsa, valuta, rettifiche e timestamp.

## Standard minimo per un'indicazione operativa

Una proposta di ingresso deve contenere:

- stato corrente della posizione;
- ultimo prezzo verificato con timestamp e fonte;
- timeframe analizzato;
- dati storici utilizzati e loro data finale;
- supporti/resistenze osservati, separati dalle trendline stimate;
- condizione di ingresso e conferma richiesta;
- invalidazione e stop;
- target e rapporto rendimento/rischio;
- size calcolata sulla perdita massima, non sul capitale disponibile;
- eventi imminenti capaci di generare gap;
- limiti, incertezza e scenario alternativo.

Se manca uno di questi elementi essenziali, la risposta corretta è sospendere l'indicazione numerica e dichiarare ciò che deve essere verificato.

## Regola fondamentale

Quando sono coinvolti soldi reali, nessun livello tecnico, calcolo o consiglio operativo può essere pubblicato senza doppio controllo dei dati e verifica matematica. Se il dato non è disponibile o la struttura grafica non è sufficientemente chiara, va detto esplicitamente: non si deve produrre falsa precisione.

Prima di usare la suite o formulare un'indicazione operativa leggere anche `DECISIONS.md` e applicare integralmente `RUNBOOK.md`.
