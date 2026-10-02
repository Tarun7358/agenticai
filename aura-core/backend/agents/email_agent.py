"""
Gmail & Email Agent for AURA / JARVIS.
======================================
Connects directly to Gmail or IMAP inbox to fetch unread emails,
read recent email bodies, and provide voice briefings.
Executes safely with strict local sovereignty.
"""

import os
import re
import imaplib
import email
from email.header import decode_header
from typing import List, Dict, Any, Optional

# Base directory for loading config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

def _get_email_credentials():
    """Retrieves email configuration from backend environment / .env."""
    try:
        from dotenv import dotenv_values
        env_path = os.path.join(BACKEND_DIR, ".env")
        vals = dotenv_values(env_path) if os.path.exists(env_path) else {}
    except Exception:
        vals = {}

    email_addr = os.environ.get("EMAIL_ADDRESS") or vals.get("EMAIL_ADDRESS", "rdxyzprvt@gmail.com").strip()
    email_pwd = os.environ.get("EMAIL_PASSWORD") or vals.get("EMAIL_PASSWORD", "").strip()
    imap_host = os.environ.get("EMAIL_IMAP_HOST") or vals.get("EMAIL_IMAP_HOST", "imap.gmail.com").strip()
    imap_port = int(os.environ.get("EMAIL_IMAP_PORT") or vals.get("EMAIL_IMAP_PORT", 993))

    return email_addr, email_pwd, imap_host, imap_port


def _clean_header(header_val: str) -> str:
    """Decodes MIME encoded headers safely."""
    if not header_val:
        return ""
    try:
        decoded_parts = decode_header(header_val)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or "utf-8", errors="ignore"))
            else:
                result.append(str(part))
        return "".join(result).strip()
    except Exception:
        return str(header_val)


def _clean_sender(sender_val: str) -> str:
    """Extracts human readable sender name."""
    decoded = _clean_header(sender_val)
    # If formatted as "Name <email@domain.com>", extract "Name"
    m = re.match(r"^\"?([^\"]+?)\"?\s*<.*?>$", decoded)
    if m:
        return m.group(1).strip()
    return decoded.split("<")[0].strip() or decoded


def check_email_connection() -> Dict[str, Any]:
    """Tests IMAP authentication and reports status."""
    email_addr, email_pwd, imap_host, imap_port = _get_email_credentials()
    if not email_pwd or email_pwd in ["your_app_password", "password"]:
        return {
            "status": "needs_auth",
            "message": f"App password needed for {email_addr}."
        }

    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=6)
        mail.login(email_addr, email_pwd)
        mail.logout()
        return {"status": "ok", "message": f"Connected to {email_addr}."}
    except Exception as ex:
        return {"status": "error", "message": str(ex)}


def get_unread_emails_summary(limit: int = 5) -> str:
    """
    Fetches and summarizes recent unread emails for Jarvis voice response.
    """
    email_addr, email_pwd, imap_host, imap_port = _get_email_credentials()

    if not email_pwd or email_pwd in ["your_app_password", "password"]:
        return (
            f"Sir, your email address is configured as {email_addr}, but I need your 16-character "
            "Google App Password in your .env file to access your inbox securely. "
            "You can generate one under Google Account Security."
        )

    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=8)
        mail.login(email_addr, email_pwd)
        mail.select("INBOX", readonly=True)

        status, response = mail.search(None, "UNSEEN")
        if status != "OK" or not response[0]:
            mail.logout()
            return f"You have zero unread emails in your inbox, sir. Everything is up to date."

        msg_ids = response[0].split()
        total_unread = len(msg_ids)

        # Get latest unread IDs
        latest_ids = msg_ids[-limit:]
        latest_ids.reverse()

        summaries = []
        for mid in latest_ids:
            try:
                res, msg_data = mail.fetch(mid, "(RFC822.HEADER)")
                if res != "OK":
                    continue
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                sender = _clean_sender(msg.get("From", "Unknown"))
                subject = _clean_header(msg.get("Subject", "No Subject"))
                summaries.append(f"from {sender} regarding {subject}")
            except Exception:
                continue

        mail.logout()

        if not summaries:
            return f"You have {total_unread} unread emails, sir, but could not retrieve header details."

        if len(summaries) == 1:
            return f"Sir, you have one unread email: {summaries[0]}."

        return f"Sir, you have {total_unread} unread emails. Recent messages include: {'; '.join(summaries[:3])}."

    except imaplib.IMAP4.error as ex:
        err_msg = str(ex).lower()
        if "authenticationfailed" in err_msg or "invalid credentials" in err_msg:
            return "Sir, Gmail rejected the login. Please ensure 2-Step Verification is on and use a 16-character Google App Password in .env."
        return f"Gmail access encountered an authentication issue: {ex}"
    except Exception as ex:
        return f"Unable to check emails right now: {ex}"


def get_latest_email_body() -> str:
    """
    Fetches the body text of the most recent email in the inbox.
    """
    email_addr, email_pwd, imap_host, imap_port = _get_email_credentials()
    if not email_pwd or email_pwd in ["your_app_password", "password"]:
        return "Sir, please configure your 16-character Google App Password in .env to allow me to read emails."

    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=8)
        mail.login(email_addr, email_pwd)
        mail.select("INBOX", readonly=True)

        status, response = mail.search(None, "ALL")
        if status != "OK" or not response[0]:
            mail.logout()
            return "Your inbox is empty, sir."

        msg_ids = response[0].split()
        latest_id = msg_ids[-1]

        res, msg_data = mail.fetch(latest_id, "(RFC822)")
        if res != "OK":
            mail.logout()
            return "Could not retrieve the email contents, sir."

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        sender = _clean_sender(msg.get("From", "Unknown"))
        subject = _clean_header(msg.get("Subject", "No Subject"))

        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get("Content-Disposition"))
                if ctype == "text/plain" and "attachment" not in cdispo:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(errors="ignore")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body_text = payload.decode(errors="ignore")

        mail.logout()

        # Clean whitespace and truncate for speech
        clean_body = re.sub(r"\s+", " ", body_text).strip()
        snippet = clean_body[:240] if clean_body else "Email contains no plain text."

        return f"Latest email from {sender} about '{subject}'. It reads: \"{snippet}\"."

    except Exception as ex:
        return f"Unable to read the latest email: {ex}"
