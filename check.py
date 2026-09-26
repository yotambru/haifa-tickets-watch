import json
import os
import smtplib
import urllib.error
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

URL = "https://ethos.smarticket.co.il/iframe/event/28114"
SOLD_OUT = "הכרטיסים אזלו"
PAGE_MARKER = "פסטיבל הסרטים"
STATE_PATH = os.environ.get("STATE_PATH", "state/log.json")
MAX_LINES = 20
EMAIL_TO = os.environ["EMAIL_TO"]
SMTP_APP_PASSWORD = os.environ["SMTP_APP_PASSWORD"]


def now_label():
    return datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%H:%M")


def telegram_api(method, payload):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("telegram skipped")
        return None

    body = json.dumps({"chat_id": chat_id, **payload}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        if "message is not modified" in detail:
            return {"ok": True, "not_modified": True}
        print(method, "failed", error.code)
        return None


def send_telegram(text):
    telegram_api(
        "sendMessage",
        {"text": text, "disable_notification": False},
    )


def load_state():
    if not os.path.exists(STATE_PATH):
        return {"message_id": None, "lines": []}
    with open(STATE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state):
    folder = os.path.dirname(STATE_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False)


def log_check(line):
    state = load_state()
    lines = [line, *state.get("lines", [])][:MAX_LINES]
    text = "לוג בדיקות\n" + "\n".join(lines)
    message_id = state.get("message_id")

    if message_id:
        edited = telegram_api(
            "editMessageText",
            {"message_id": message_id, "text": text},
        )
        if edited is not None:
            state["lines"] = lines
            save_state(state)
            print("log updated")
            return

    created = telegram_api(
        "sendMessage",
        {"text": text, "disable_notification": True},
    )
    if not created or "result" not in created:
        print("log not saved")
        return

    state["message_id"] = created["result"]["message_id"]
    state["lines"] = lines
    save_state(state)
    print("log created", state["message_id"])


def send_email(subject, body):
    mail = EmailMessage()
    mail["From"] = EMAIL_TO
    mail["To"] = EMAIL_TO
    mail["Subject"] = subject
    mail.set_content(body)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_TO, SMTP_APP_PASSWORD)
        smtp.send_message(mail)


def main():
    if os.environ.get("SEND_TEST") == "true":
        send_email(
            "בדיקת התראה מהענן",
            "אם אתה רואה את זה, בדיקת הכרטיסים רצה גם כשהמחשב כבוי.",
        )
        send_telegram("בדיקת התראה. אם אתה רואה את זה, טלגרם עובד.")
        print("test email sent")
        return

    request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        status = response.status
        html = response.read().decode("utf-8", "replace")

    if status in (403, 429):
        log_check(f"{now_label()} — האתר חסם את הבדיקה ({status}).")
        print(f"blocked {status}")
        return

    if PAGE_MARKER not in html:
        log_check(f"{now_label()} — הדף לא נטען. לא נשלחה התראה.")
        print("page did not load, no email sent")
        return

    if SOLD_OUT in html:
        log_check(f"{now_label()} — הכרטיסים עדיין אזלו.")
        print("still sold out")
        return

    alert = f"נפתחו כנראה כרטיסים לפסטיבל הסרטים בחיפה!\n{URL}"
    send_email("נפתחו כנראה כרטיסים", alert)
    send_telegram(alert)
    log_check(f"{now_label()} — נשלחה התראה: ייתכן שנפתחו כרטיסים.")
    print("tickets email sent")


if __name__ == "__main__":
    main()
