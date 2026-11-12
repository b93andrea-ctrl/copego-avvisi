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
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://copego.cloud"
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
STATE_FILE = Path(os.environ.get("STATE_FILE", "state.json"))
TIMEOUT = 30


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERRORE: variabile d'ambiente {name} mancante", file=sys.stderr)
        sys.exit(2)
    return value


def login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/authenticate",
        json={"username": email, "password": password, "rememberMe": False},
        timeout=TIMEOUT,
    )
    if r.status_code == 401:
        raise SystemExit("ERRORE: login rifiutato (email o password errate)")
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
    if notice is None:
        return "nessun-avviso"
    h = hashlib.sha256()
    for key in ("id", "notificationDate", "lastModifiedDate", "notificationText", "notificationImage"):
        h.update(str(notice.get(key)).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ntfy_text(topic: str, title: str, message: str, priority: str = "high") -> None:
    r = requests.post(
        f"{NTFY_SERVER}/{topic}",
        data=message.encode("utf-8"),
        headers={"Title": title, "Priority": priority, "Tags": "fish"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()


def ntfy_image(topic: str, title: str, image_bytes: bytes, filename: str = "avviso.jpg") -> None:
    r = requests.put(
        f"{NTFY_SERVER}/{topic}",
        data=image_bytes,
        headers={"Title": title, "Priority": "high", "Tags": "fish", "Filename": filename},
        timeout=TIMEOUT,
    )
    r.raise_for_status()


def notify(topic: str, notice: dict | None, first_run: bool) -> None:
    # I titoli negli header HTTP devono restare in ASCII: niente accenti qui.
    if notice is None:
        ntfy_text(topic, "Copego: nessun avviso", "Oggi non risulta nessun avviso pubblicato.")
        return

    date = notice.get("notificationDate") or ""
    title = f"Copego: avviso aggiornato {date}".strip()
    if first_run:
        title = f"Copego: monitor attivo, avviso di {date}".strip()

    text = (notice.get("notificationText") or "").strip()
    image_b64 = notice.get("notificationImage")

    if image_b64:
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception:
            image_bytes = b""
        if image_bytes:
            ntfy_image(topic, title, image_bytes)
            if text:
                ntfy_text(topic, title, text, priority="default")
            return

    ntfy_text(topic, title, text or "L'avviso e' cambiato ma non contiene testo ne' immagine.")


def main() -> int:
    email = env("COPEGO_EMAIL")
    password = env("COPEGO_PASSWORD")
    topic = env("NTFY_TOPIC")

    token = login(email, password)
    notice = fetch_today(token)
    fp = fingerprint(notice)

    state = load_state()
    previous = state.get("fingerprint")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if previous == fp:
        print(f"[{now}] Nessun cambiamento (impronta {fp[:12]}).")
        state["last_checked"] = now
        save_state(state)
        return 0

    first_run = previous is None
    print(f"[{now}] {'Primo avvio' if first_run else 'CAMBIAMENTO rilevato'}: {previous} -> {fp[:12]}")
    notify(topic, notice, first_run)

    state.update(
        {
            "fingerprint": fp,
            "notification_id": notice.get("id") if notice else None,
            "notification_date": notice.get("notificationDate") if notice else None,
            "last_modified": notice.get("lastModifiedDate") if notice else None,
            "last_changed": now,
            "last_checked": now,
        }
    )
    save_state(state)
    print("Notifica inviata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
