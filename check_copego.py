"""Controlla l'avviso del giorno su copego.cloud e manda una notifica push via ntfy quando cambia.

Variabili d'ambiente richieste:
  COPEGO_EMAIL     email dell'utenza Copego Cloud
  COPEGO_PASSWORD  password
  NTFY_TOPIC       argomento ntfy a cui e' iscritto il telefono
Opzionali:
  NTFY_SERVER      default https://ntfy.sh
  STATE_FILE       default state.json
"""

import base64
import hashlib
import html
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://copego.cloud"
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
STATE_FILE = Path(os.environ.get("STATE_FILE", "state.json"))
TIMEOUT = 30
LOGIN_FAILURES_BEFORE_ALERT = 3
FINGERPRINT_VERSION = 2  # da alzare ogni volta che cambia la formula dell'impronta

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]


class LoginError(Exception):
    pass


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERRORE: variabile d'ambiente {name} mancante", file=sys.stderr)
        sys.exit(2)
    return value


# --- Copego -----------------------------------------------------------------

def login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/authenticate",
        json={"username": email, "password": password, "rememberMe": False},
        timeout=TIMEOUT,
    )
    if r.status_code == 401:
        raise LoginError("login rifiutato (email o password errate)")
    r.raise_for_status()
    return r.json()["id_token"]


def fetch_today(token: str) -> dict | None:
    r = requests.get(
        f"{BASE_URL}/api/notification/today",
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    if r.status_code == 404 or not r.text.strip():
        return None
    r.raise_for_status()
    return r.json()


def fingerprint(notice: dict | None) -> str:
    """Impronta del solo contenuto (data, testo, immagine): un avviso risalvato
    senza modifiche non viene notificato di nuovo."""
    if notice is None:
        return "nessun-avviso"
    h = hashlib.sha256()
    for key in ("notificationDate", "notificationText", "notificationImage"):
        h.update(str(notice.get(key)).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


# --- Stato -------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --- Testo e date ------------------------------------------------------------

def clean_text(raw: str | None) -> str:
    """Toglie HTML, entita' (&nbsp;) e spazi doppi dal testo dell'avviso."""
    if not raw:
        return ""
    text = html.unescape(raw)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def italian_date(iso: str | None) -> str:
    """'2026-11-13' -> 'giovedì 13 novembre'. Se la data non si legge, la restituisce com'e'."""
    try:
        d = date.fromisoformat(iso or "")
    except ValueError:
        return iso or ""
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]}"


# --- ntfy --------------------------------------------------------------------

def hdr(value: str) -> str:
    """Gli header HTTP accettano solo ASCII: il resto va codificato (RFC 2047), ntfy lo decodifica."""
    if value.isascii():
        return value
    return "=?UTF-8?B?" + base64.b64encode(value.encode("utf-8")).decode("ascii") + "?="


def ntfy_headers(title: str, priority: str, tags: str) -> dict:
    return {
        "Title": hdr(title),
        "Priority": priority,
        "Tags": tags,
        "Click": f"{BASE_URL}/",
    }


def ntfy_text(topic: str, title: str, message: str, priority: str = "high", tags: str = "fish") -> None:
    r = requests.post(
        f"{NTFY_SERVER}/{topic}",
        data=message.encode("utf-8"),
        headers=ntfy_headers(title, priority, tags),
        timeout=TIMEOUT,
    )
    r.raise_for_status()


def ntfy_image(topic: str, title: str, message: str, image_bytes: bytes, filename: str = "avviso.jpg") -> None:
    headers = ntfy_headers(title, "high", "fish")
    headers["Filename"] = filename
    headers["Message"] = hdr(message)
    r = requests.put(f"{NTFY_SERVER}/{topic}", data=image_bytes, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()


def notify(topic: str, notice: dict, first_run: bool) -> None:
    giorno = italian_date(notice.get("notificationDate"))
    text = clean_text(notice.get("notificationText"))
    image_b64 = notice.get("notificationImage")

    image_bytes = b""
    if image_b64:
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception:
            image_bytes = b""

    prefix = "Copego, monitor attivo" if first_run else "Copego"

    if image_bytes:
        title = f"{prefix}: avviso di {giorno}" if giorno else f"{prefix}: nuovo avviso"
        ntfy_image(topic, title, "Apri per vedere l'immagine.", image_bytes)
        if text:
            ntfy_text(topic, title, text, priority="default")
        return

    if text:
        # Avviso di solo testo: il testo va nel titolo, cosi' si legge dalla tendina.
        first_line = text.splitlines()[0]
        title = f"{prefix}: {first_line}" if len(first_line) <= 90 else f"{prefix}: {first_line[:87]}..."
        ntfy_text(topic, title, f"Avviso di {giorno}\n\n{text}" if giorno else text)
        return

    ntfy_text(topic, f"{prefix}: avviso di {giorno}", "L'avviso e' cambiato ma non contiene testo ne' immagine.")


# --- Main --------------------------------------------------------------------

def handle_login_failure(state: dict, topic: str, error: str) -> int:
    failures = int(state.get("login_failures", 0)) + 1
    state["login_failures"] = failures
    print(f"ERRORE: {error} (tentativo fallito n. {failures})", file=sys.stderr)
    if failures == LOGIN_FAILURES_BEFORE_ALERT:
        ntfy_text(
            topic,
            "Copego: password non accettata",
            "Il monitor non riesce piu' a entrare in Copego Cloud. Se hai cambiato la password, "
            "aggiorna il secret COPEGO_PASSWORD su GitHub.",
            priority="urgent",
            tags="warning",
        )
        print("Allarme password inviato.")
    save_state(state)
    return 1


def main() -> int:
    email = env("COPEGO_EMAIL")
    password = env("COPEGO_PASSWORD")
    topic = env("NTFY_TOPIC")

    state = load_state()

    try:
        token = login(email, password)
    except LoginError as e:
        return handle_login_failure(state, topic, str(e))

    if state.pop("login_failures", None) is not None:
        save_state(state)
        print("Login tornato a funzionare.")

    notice = fetch_today(token)
    fp = fingerprint(notice)
    previous = state.get("fingerprint")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if previous is not None and state.get("fingerprint_version") != FINGERPRINT_VERSION:
        # Cambiata la formula dell'impronta: si ricalcola in silenzio, senza
        # notificare un avviso che e' gia' stato visto.
        state["fingerprint"] = fp
        state["fingerprint_version"] = FINGERPRINT_VERSION
        save_state(state)
        print(f"[{now}] Impronta ricalcolata con la formula {FINGERPRINT_VERSION}, nessuna notifica.")
        return 0

    if previous == fp:
        print(f"[{now}] Nessun cambiamento (impronta {fp[:12]}).")
        return 0

    first_run = previous is None
    print(f"[{now}] {'Primo avvio' if first_run else 'CAMBIAMENTO rilevato'}: {previous} -> {fp[:12]}")

    # Prima si avvisa, poi si salva la memoria: se ntfy non risponde, l'eccezione
    # interrompe qui e il prossimo controllo riprova. Un eventuale doppione e'
    # preferibile a un avviso perso per sempre.
    if notice is None:
        # Sito vuoto (avviso tolto): nessuna notifica, solo memoria dello stato,
        # cosi' il prossimo avviso vero viene riconosciuto come novita'.
        print("Nessun avviso pubblicato: nessuna notifica.")
    else:
        notify(topic, notice, first_run)
        print("Notifica inviata.")

    state.update(
        {
            "fingerprint": fp,
            "fingerprint_version": FINGERPRINT_VERSION,
            "notification_id": notice.get("id") if notice else None,
            "notification_date": notice.get("notificationDate") if notice else None,
            "last_modified": notice.get("lastModifiedDate") if notice else None,
            "last_changed": now,
        }
    )
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
