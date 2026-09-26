import json
import os
import smtplib
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

URL = "https://ethos.smarticket.co.il/iframe/event/28114"
SOLD_OUT = "הכרטיסים אזלו"
PAGE_MARKER = "פסטיבל הסרטים"
EMAIL_TO = os.environ["EMAIL_TO"]
SMTP_APP_PASSWORD = os.environ["SMTP_APP_PASSWORD"]


def now_label():
    return datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%H:%M")


def send_telegram(text, silent=False):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("telegram skipped")
        return

    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_notification": silent,
        }
    ).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print("telegram", response.status)


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
        send_telegram(f"בדיקה {now_label()} — האתר חסם את הבדיקה ({status}).", silent=True)
        print(f"blocked {status}")
        return

    if PAGE_MARKER not in html:
        send_telegram(f"בדיקה {now_label()} — הדף לא נטען. לא נשלחה התראה.", silent=True)
        print("page did not load, no email sent")
        return

    if SOLD_OUT in html:
        send_telegram(f"בדיקה {now_label()} — הכרטיסים עדיין אזלו.", silent=True)
        print("still sold out")
        return

    alert = f"נפתחו כנראה כרטיסים לפסטיבל הסרטים בחיפה!\n{URL}"
    send_email("נפתחו כנראה כרטיסים", alert)
    send_telegram(alert)
    print("tickets email sent")


if __name__ == "__main__":
    main()
