#!/usr/bin/env bash
# Si assicura che un altro turno del monitor sia in coda (o in attesa di partire).
# Se non c'e', prova a prenotarlo fino a tre volte; se fallisce, manda una notifica ntfy.
# Variabili attese: GH_TOKEN, GITHUB_REPOSITORY, GITHUB_RUN_ID, NTFY_TOPIC.

set -u

turni_in_coda() {
  gh run list --workflow check.yml --repo "$GITHUB_REPOSITORY" --limit 20 \
    --json databaseId,status \
    --jq "[.[] | select(.databaseId != ${GITHUB_RUN_ID}) | select(.status == \"queued\" or .status == \"waiting\" or .status == \"pending\" or .status == \"requested\" or .status == \"in_progress\")] | length" \
    2>/dev/null || echo 0
}

for tentativo in 1 2 3; do
  n=$(turni_in_coda)
  if [ "${n:-0}" -ge 1 ]; then
    echo "Turno successivo in coda (altri turni attivi: $n)."
    exit 0
  fi
  echo "Nessun turno in coda, prenoto (tentativo $tentativo)..."
  gh workflow run check.yml --ref main --repo "$GITHUB_REPOSITORY" || true
  sleep 20
done

echo "ERRORE: non riesco a prenotare il turno successivo." >&2
curl -s -o /dev/null \
  -H "Title: Copego: monitor fermo" \
  -H "Priority: urgent" \
  -H "Tags: warning" \
  -H "Click: https://github.com/${GITHUB_REPOSITORY}/actions" \
  -d "Il turno successivo non si e' messo in coda. Apri GitHub Actions e premi Run workflow." \
  "https://ntfy.sh/${NTFY_TOPIC}"
exit 1
