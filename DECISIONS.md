# Decision Log

Ultimo aggiornamento: 2026-08-03

Questo documento registra decisioni consolidate. Non è un diario completo delle conversazioni. Ogni nuova voce deve indicare data, decisione, motivazione e condizioni che potrebbero invalidarla.

## Decisioni storiche conservate

- **[2025-10-08]** Ingestion web Yahoo, normalizzazione date senza timezone e deduplica `(Ticker, Date)`.
- **[2025-10-08]** Guardrail rigidi con stato `YELLOW` per casi borderline o dati incompleti.
- **[2025-10-08]** Walk-forward annuale e trimmed CoV con `wf_trim: 1` e soglia 30%.
- **[2025-10-08]** Pubblicazione dei dataset validati nella cartella `latest/` del datalake.
- **[2025-10-08]** Segnali breakout 52 settimane, stop -7%, target +14% e probabilità fissa 45%: decisione successivamente superata da D-003; non usare come regola operativa.

## Decisioni attive

### D-001 — Separazione datalake e trading suite

- **Data:** 2026-07
- **Decisione:** mantenere separati il repository dei dati e quello di analisi/strategie.
- **Motivo:** qualità e aggiornamento dei dati devono essere verificabili indipendentemente dalla logica di trading.
- **Conseguenza:** nessun segnale è valido se il dataset di input non supera i controlli del `RUNBOOK.md`.

### D-002 — Validazione su un ETF alla volta

- **Data:** 2026-07
- **Decisione:** progettare e validare inizialmente la strategia su un ETF specifico, a partire da `SEME.MI`, e solo dopo verificarla su `XAIX` e `TNOW`.
- **Motivo:** ridurre complessità, data snooping e selezione opportunistica del miglior risultato.
- **Condizione:** l'estensione è ammessa solo dopo test out-of-sample, costi e robustezza.

### D-003 — Eliminazione di stop e target fissi universali

- **Data:** 2026-07
- **Decisione:** non usare automaticamente stop `-7%` e target `+14%` per tutti gli ETF.
- **Motivo:** volatilità, struttura tecnica e orizzonte variano per strumento e regime.
- **Conseguenza:** stop e target devono derivare da invalidazione, volatilità e rapporto rendimento/rischio.

### D-004 — Size determinata dal rischio

- **Data:** 2026-08-03
- **Decisione:** calcolare la quantità solo dopo aver definito invalidazione e perdita massima accettabile.
- **Motivo:** investire l'intero capitale e scegliere lo stop successivamente produce un rischio non controllato.
- **Formula:** `quantità = perdita_massima_EUR / abs(prezzo_ingresso - stop)`, poi arrotondamento prudenziale e controllo dell'esposizione.

### D-005 — Nessun ingresso senza conferma

- **Data:** 2026-08-03
- **Decisione:** un contatto con supporto o bordo di canale non è da solo un segnale d'acquisto.
- **Motivo:** un livello può essere attraversato; serve una regola osservabile di reazione o recupero.
- **Esempi di conferma:** recupero del livello, minimo crescente, chiusura coerente col timeframe o breakout con retest.

### D-006 — Distinzione obbligatoria tra tipi di livello

- **Data:** 2026-08-03
- **Decisione:** riportare separatamente:
  1. massimi/minimi osservati;
  2. supporti/resistenze orizzontali;
  3. trendline e bordi dinamici stimati;
  4. fascia d'incertezza;
  5. ingresso operativo.
- **Motivo:** questi valori non sono equivalenti e confonderli può generare ordini errati.

### D-007 — Verifica preventiva obbligatoria

- **Data:** 2026-08-03
- **Decisione:** prima di indicazioni su denaro reale verificare posizione, ticker/listing, valuta, timestamp, serie storica, metodologia e calcoli.
- **Motivo:** evitare risposte incompatibili o basate su stato e dati obsoleti.
- **Conseguenza:** in assenza di verifica si dichiara l'incertezza e non si fornisce un livello apparentemente preciso.

### D-008 — Documentazione operativa persistente

- **Data:** 2026-08-03
- **Decisione:** mantenere `README_OPS.md`, `DECISIONS.md` e `RUNBOOK.md` come fonte stabile del contesto operativo.
- **Motivo:** evitare di richiedere nuovamente all'utente file o regole già definite.
- **Conseguenza:** questi documenti vanno aggiornati quando cambia una decisione, non ricreati a memoria.

### D-009 — Il segnale della suite non equivale a un ordine

- **Data:** 2026-08-03
- **Decisione:** dashboard, segnali e stato dei guardrail sono input analitici; un ordine reale richiede comunque tutti i controlli del `RUNBOOK.md`.
- **Motivo:** un backtest accettabile non verifica automaticamente posizione corrente, prezzo intraday, eventi imminenti, spread e rischio personale.

### D-010 — Probabilità solo se calibrate

- **Data:** 2026-08-03
- **Decisione:** non assegnare probabilità fisse o intuitive alla salita/discesa. Pubblicare una probabilità solo se deriva da un modello documentato, con campione, orizzonte, validazione out-of-sample e calibrazione verificabili.
- **Motivo:** una percentuale non calibrata crea falsa precisione.

## Correzioni e indicazioni ritirate

### C-001 — Stato della posizione SEME

- **Errore:** è stata ipotizzata una posizione residua di 4.450 quote dopo che era già stata chiusa.
- **Correzione:** al 2026-08-03 la posizione è zero; ogni nuova analisi riguarda il rientro.
- **Prevenzione:** primo passo del runbook = verificare posizione e operazioni successive all'ultimo aggiornamento.

### C-002 — Canale discendente SEME

- **Errore:** sono stati indicati in successione 15,50 EUR, 15,10 EUR e 14,40 EUR come bordo inferiore, confondendo supporti orizzontali, minimi osservati e proiezioni dinamiche.
- **Decisione:** tutte queste stime sono **ritirate come livelli confermati** finché il canale non viene ricostruito dalla serie storica completa con pivot, criterio esplicito, regressione/parallelismo, grafico e controllo indipendente.
- **Prevenzione:** applicare la sezione “Ricostruzione di un canale” del `RUNBOOK.md`.

### C-003 — Dati EOD usati come aggiornati

- **Errore:** un close precedente è stato trattato come prezzo corrente.
- **Correzione:** dichiarare sempre timestamp e natura del dato; per operatività intraday usare una fonte intraday verificabile.

## Stato delle strategie

Le idee breakout, pullback e acquisto sui minimi di un canale discendente sono ipotesi di ricerca, non strategie validate, finché non sono disponibili:

- regole deterministiche di entrata e uscita;
- campione adeguato e periodo out-of-sample;
- costi, spread e slippage;
- metriche di rischio e confronto con benchmark;
- test di sensibilità dei parametri;
- evidenza che il risultato non dipenda da pochi trade o da un singolo regime.
