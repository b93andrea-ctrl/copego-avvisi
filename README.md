# Copego monitor

Controlla ogni 5 minuti l'avviso del giorno su copego.cloud e manda una notifica push
al telefono (app ntfy) quando cambia, con l'immagine dell'avviso allegata.

## Come funziona

- `check_copego.py` fa il login con la tua utenza, scarica l'avviso di oggi e ne calcola
  un'impronta. Se è diversa da quella salvata in `state.json`, manda la notifica.
- `.github/workflows/check.yml` esegue lo script su GitHub Actions a orario e salva
  `state.json` nel repository, così il confronto sopravvive tra un'esecuzione e l'altra.
- In `state.json` c'è solo un'impronta (hash), mai l'immagine o la password.
- Email, password e argomento ntfy stanno solo nei Secrets del repository, cifrati.
  Nel codice non compare nessun dato personale, quindi il repository può essere pubblico.

## Installazione su GitHub (una volta sola)

1. Sul telefono apri l'app **ntfy** e iscriviti a un argomento scelto da te: lungo e
   difficile da indovinare, perché chi lo conosce può leggere le notifiche.
2. Su GitHub crea un repository nuovo. Pubblico: i minuti di Actions sono illimitati.
   Privato: il piano gratuito dà 2000 minuti al mese, che con un controllo ogni 5 minuti
   non bastano; in quel caso allarga l'intervallo a 15 minuti.
3. Carica in quel repository tutti i file di questa cartella (`check_copego.py`,
   `requirements.txt`, `README.md`, `.gitignore`, `.env.example` e la cartella
   `.github/workflows/`). Il file `.env`, se lo crei, non va caricato.
4. Nel repository vai su **Settings → Secrets and variables → Actions → New repository secret**
   e crea tre secret:
   - `COPEGO_EMAIL`: la tua email Copego
   - `COPEGO_PASSWORD`: la tua password Copego
   - `NTFY_TOPIC`: l'argomento ntfy scelto al punto 1
5. Vai su **Actions**, scegli "Controllo avviso Copego" e premi **Run workflow** per la
   prima esecuzione manuale. Entro un minuto dovresti ricevere sul telefono la notifica
   "Copego: monitor attivo" con l'avviso di oggi. Da lì in poi va da solo.

## Orario

Il workflow gira ogni 5 minuti dalle 5:00 alle 19:55 UTC, cioè 6:00-20:55 in inverno e
7:00-21:55 in estate. Per cambiarlo modifica la riga `cron` in `check.yml`.
GitHub può ritardare le esecuzioni pianificate di qualche minuto nelle ore di punta.

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

- Nessuna notifica da giorni: su GitHub apri **Actions** e guarda se le esecuzioni sono
  verdi. GitHub disattiva i workflow pianificati dopo 60 giorni senza modifiche al
  repository: basta premere "Enable workflow" o fare una modifica qualsiasi.
- "login rifiutato": la password Copego è cambiata, aggiorna il secret.
- Per fermare tutto: disattiva il workflow dalla pagina Actions.
