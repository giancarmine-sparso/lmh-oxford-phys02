# Stress test Quarto

Presentazione diagnostica offline per verificare fluidità, decodifica video,
Canvas 2D, WebGL e carico CPU sul computer usato per la talk.

## Avvio

Per provare la versione sorgente con aggiornamento automatico:

```sh
quarto preview index.qmd
```

Per generare la cartella portabile:

```sh
quarto render
```

Copiare l'intera cartella `_site` sul computer finale e aprire
`_site/index.html` con Chrome o Chromium. Non è richiesta una connessione a
Internet.

All'avvio si può scegliere il ciclo rapido da 3 minuti o quello completo da
15 minuti. Il pulsante rosso e il tasto `X` interrompono immediatamente i
workload e portano al rapporto finale.

## Verifica accelerata

Con `_site` servita localmente sulla porta 8765:

```sh
node tests/chromium-smoke.mjs
```

Il controllo attraversa tutti i nove workload in circa 20 secondi, verifica
il rapporto finale e salva uno screenshot in `/tmp/stress-test-results.png`.
