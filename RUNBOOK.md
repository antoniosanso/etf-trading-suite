# Trading Analysis Runbook

Ultimo aggiornamento: 2026-08-03

Questa procedura è obbligatoria prima di produrre segnali, livelli o indicazioni operative su denaro reale.

## 0. Eseguire e controllare la piattaforma

1. Nel datalake eseguire Actions -> `Update validated ETF universe`.
2. Aprire `latest/quality-report.json`: `status` deve essere `pass`, l'universo atteso deve essere presente e ogni esclusione deve avere una motivazione.
3. Nella suite eseguire Actions -> `Trading suite from validated datalake`.
4. Controllare gli artifact: `backtest-artifacts`, `wf_report.json`, `wf_summary.txt`, `signals`, `operational-report` ed `eod-dataset`.
5. Per l'universo, modificare prima `universe.csv` nel datalake e poi allineare `etf-trading-config/universe.csv` nella suite.

Un workflow verde o un guardrail non rosso non sostituisce i controlli operativi delle sezioni successive.

## 1. Verificare il mandato

Chiarire quale decisione è richiesta:

- nuovo ingresso;
- gestione di una posizione aperta;
- uscita o riduzione;
- analisi tecnica senza ordine;
- backtest o modifica della piattaforma.

Non trasformare una richiesta di analisi in un ordine e non assumere che una posizione precedente sia ancora aperta.

## 2. Verificare lo stato della posizione

Registrare:

- strumento e listing;
- quantità attuale;
- prezzo medio di carico;
- ordini pendenti;
- vendite/acquisti successivi all'ultimo aggiornamento;
- capitale effettivamente destinabile;
- perdita massima accettabile in EUR e in percentuale.

Se lo stato non è verificabile, dichiarare l'assunzione e chiedere conferma prima di una raccomandazione eseguibile.

## 3. Validare i dati

Controlli minimi sulla serie:

- ticker, ISIN se disponibile, borsa e valuta corretti;
- data/ora dell'ultimo record;
- nessun duplicato di data;
- ordinamento cronologico;
- valori numerici non mancanti per OHLC;
- `Low <= Open/Close <= High`;
- volumi e prezzi non negativi;
- calendario senza buchi anomali non spiegati;
- rettifiche/split coerenti;
- confronto degli ultimi record con una seconda fonte.

Per dati intraday specificare ritardo e timestamp. Un close EOD non è un prezzo real-time.

## 4. Ricostruire supporti e canali

### 4.1 Dati osservati

Elencare prima i pivot realmente osservati con data e prezzo. Non chiamare “supporto del canale” un singolo minimo.

### 4.2 Metodo

Definire prima del calcolo:

- periodo e timeframe;
- regola oggettiva per identificare i pivot;
- numero minimo di contatti;
- trattamento delle violazioni temporanee;
- metodo di fit delle trendline;
- criterio di parallelismo del canale.

Un canale è utilizzabile solo se entrambe le linee hanno contatti sufficienti, pendenza coerente e residui compatibili con la volatilità. In caso contrario descrivere la struttura come intervallo o trend incerto.

### 4.3 Output obbligatorio

Riportare separatamente:

- supporti/resistenze orizzontali;
- trendline superiore e inferiore;
- formula o pendenza usata;
- valore proiettato alla data esatta;
- intervallo d'incertezza;
- grafico con pivot e linee;
- test di sensibilità cambiando i pivot ragionevolmente selezionabili.

Se piccoli cambiamenti nei pivot spostano molto il livello, il canale non è abbastanza robusto per guidare un ordine.

## 5. Controllare eventi e contesto

Prima di un trade breve verificare almeno:

- risultati societari delle principali partecipazioni dell'ETF;
- dati macro, banche centrali e festività di mercato;
- movimenti del settore e dei principali titoli sottostanti;
- rischio cambio;
- gap recenti, liquidità e spread.

Le informazioni potenzialmente cambiate devono essere controllate su fonti aggiornate e preferibilmente ufficiali.

## 6. Costruire il piano

Definire in questo ordine:

1. scenario e condizione d'ingresso;
2. conferma richiesta;
3. livello che invalida lo scenario;
4. stop eseguibile, considerando gap e spread;
5. perdita massima accettabile;
6. quantità acquistabile;
7. target realistici;
8. rapporto rendimento/rischio netto di costi;
9. condizioni di non-ingresso;
10. gestione dopo TP1 e regole di uscita temporale.

Non adattare lo stop per far entrare più capitale. Se il rapporto rendimento/rischio non è sufficiente, restare liquidi è una decisione valida.

## 7. Verificare i calcoli due volte

Eseguire almeno questi controlli:

```text
capitale_impiegato = quantità × prezzo_ingresso
rischio_unitario = abs(prezzo_ingresso - stop)
perdita_stop = quantità × rischio_unitario + costi_stimati
profitto_target = quantità × abs(target - prezzo_ingresso) - costi_stimati
R_multiple = profitto_target / perdita_stop
rendimento_percentuale = (prezzo_uscita / prezzo_ingresso - 1) × 100
```

Secondo controllo obbligatorio:

- ricalcolo indipendente o script/test;
- verifica di segni, quantità parziali, valuta e percentuali;
- coerenza tra testo, tabella e conclusione;
- confronto tra perdita dichiarata e capitale realmente esposto.

## 8. Formato della risposta operativa

Ogni risposta eseguibile deve iniziare dalla conclusione e includere:

1. **Stato verificato** — posizione, prezzo, timestamp, fonte;
2. **Lettura** — scenario principale e alternativo;
3. **Piano** — ingresso, conferma, stop, target, size;
4. **Rischio** — perdita massima, gap, eventi e limiti;
5. **Cosa invaliderebbe l'analisi**;
6. **Grado di confidenza**, senza percentuali arbitrarie.

Distinguere sempre fatti, calcoli, stime e giudizi.

## 9. Backtest e modifiche alla strategia

Prima di definire una strategia “soddisfacente” verificare:

- assenza di look-ahead bias e survivorship bias;
- separazione training/test o walk-forward;
- costi, spread e slippage realistici;
- numero di trade e distribuzione dei rendimenti;
- CAGR/ritorno, max drawdown, volatilità, Sharpe/Sortino e profit factor;
- dipendenza dai migliori trade;
- sensibilità dei parametri;
- confronto con buy-and-hold e benchmark coerente;
- robustezza su `XAIX` e `TNOW` solo dopo il test primario su `SEME.MI`.

Una strategia non è validata solo perché ha funzionato sull'ultima operazione reale.

## 10. Aggiornare la documentazione

Dopo una decisione o una correzione materiale:

- aggiornare `DECISIONS.md` con data e motivazione;
- aggiornare `README_OPS.md` se cambia il contesto operativo;
- aggiornare questo runbook se emerge un nuovo controllo necessario;
- non cancellare gli errori rilevanti: registrarli come indicazioni ritirate e spiegare la prevenzione.

## Checklist finale

Prima di inviare una risposta su denaro reale, tutte le caselle devono essere vere:

- [ ] Posizione e richiesta comprese correttamente.
- [ ] Ticker, listing, valuta e timestamp verificati.
- [ ] Storico aggiornato e controllato.
- [ ] Fonte secondaria coerente.
- [ ] Livelli osservati distinti da quelli stimati.
- [ ] Metodo del canale dichiarato e robusto, se usato.
- [ ] Eventi imminenti verificati.
- [ ] Stop definito dall'invalidazione.
- [ ] Size definita dalla perdita massima.
- [ ] Calcoli ricontrollati indipendentemente.
- [ ] Incertezza e condizioni di non-ingresso esplicite.
- [ ] Nessun numero presentato con precisione superiore a quella consentita dai dati.
