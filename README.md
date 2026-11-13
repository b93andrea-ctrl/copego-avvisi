# Copego monitor

Controlla ogni 5 minuti l'avviso del giorno su copego.cloud e manda una notifica push
al telefono (app ntfy) quando cambia, con l'immagine dell'avviso allegata.

## Come funziona

- `check_copego.py` fa il login con la tua utenza, scarica l'avviso di oggi e ne calcola
  un'impronta (data, testo, immagine). Se è diversa da quella salvata in `state.json`,
  manda la notifica e poi aggiorna la memoria. Se il sito è vuoto non avvisa.
- `.github/workflows/check.yml` fa girare lo script su GitHub Actions a catena (vedi
  "Orario") e salva `state.json` nel repository, così la memoria sopravvive tra un turno
  e l'altro. Ogni turno si allinea all'ultima versione del repository prima di partire.
- `.github/turno_successivo.sh` si assicura che il turno successivo sia prenotato; se non
  ci riesce manda la notifica "Copego: monitor fermo".
- In `state.json` c'è solo un'impronta (hash) e qualche data, mai l'immagine o la password.
- Email, password e argomento ntfy stanno solo nei Secrets del repository, cifrati.
  Nel codice non compare nessun dato personale, quindi il repository può essere pubblico.

## Notifiche che arrivano

- "Copego: avviso di giovedì 13 novembre" con l'immagine allegata: avviso con immagine.
- "Copego: <testo>": avviso di solo testo, il testo è nel titolo.
- "Copego: monitor fermo": la catena non è riuscita a prenotare il turno successivo.
- "Copego: password non accettata": tre login falliti di fila, probabilmente la password
  Copego è cambiata.

Toccando una notifica si apre copego.cloud.

## Installazione su GitHub (una volta sola)

1. Sul telefono apri l'app **ntfy** e iscriviti a un argomento scelto da te: lungo e
   difficile da indovinare, perché chi lo conosce può leggere le notifiche. Nelle
   impostazioni di ntfy attiva la "consegna istantanea".
2. Su GitHub crea un repository nuovo **pubblico** (minuti di Actions illimitati; con un
   repository privato i 2000 minuti gratuiti al mese non bastano per una catena continua).
3. Carica in quel repository tutti i file di questa cartella (`check_copego.py`,
   `requirements.txt`, `README.md`, `.gitignore`, `.env.example` e la cartella `.github/`
   con `workflows/check.yml` e `turno_successivo.sh`). Il file `.env`, se lo crei, non va
   caricato.
4. Nel repository vai su **Settings → Secrets and variables → Actions → New repository secret**
   e crea tre secret:
   - `COPEGO_EMAIL`: la tua email Copego
   - `COPEGO_PASSWORD`: la tua password Copego
   - `NTFY_TOPIC`: l'argomento ntfy scelto al punto 1
5. Vai su **Actions**, scegli "Controllo avviso Copego" e premi **Run workflow**. Entro un
   minuto dovresti ricevere sul telefono la notifica "Copego, monitor attivo" con l'avviso
   del giorno. Da lì in poi va da solo.

## Orario

Il monitor lavora a catena, 24 ore su 24. Ogni esecuzione ("turno") dura circa 5 ore e
50 minuti (GitHub ne concede al massimo 6) e controlla ogni 5 minuti; appena parte
prenota il turno successivo, che resta in coda e scatta nell'istante in cui il precedente
finisce. Non dipende dalla pianificazione di GitHub, poco affidabile: le righe `cron` in
`check.yml` restano solo come rete di sicurezza.

Per avviare la catena la prima volta, o riavviarla se si è interrotta, basta premere
**Run workflow** nella pagina Actions. Le esecuzioni "cancelled" nella pagina Actions sono
prenotazioni sostituite da prenotazioni più recenti, non errori.

## Modifiche allo script

Basta modificare il file su GitHub: il turno successivo si allinea da solo all'ultima
versione quando parte. Per applicare subito una modifica, premi **Run workflow** e poi
annulla il turno in corso con "Cancel workflow".

## Test sul PC (facoltativo)

```
pip install -r requirements.txt
copy .env.example .env      (poi compila .env)
```

Poi, in PowerShell:

```
Get-Content .env | ForEach-Object { $n,$v = $_ -split '=',2; if ($n -and -not $n.StartsWith('#')) { Set-Item "env:$n" $v } }
python check_copego.py
```

## Se smette di funzionare

- Nessuna notifica da giorni: su GitHub apri **Actions** e guarda se c'è un'esecuzione
  "In progress". Se non c'è, la catena si è interrotta: premi **Run workflow** e riparte.
- "Copego: password non accettata": aggiorna il secret `COPEGO_PASSWORD`.
- Per fermare tutto: disattiva il workflow dalla pagina Actions ("Disable workflow").
