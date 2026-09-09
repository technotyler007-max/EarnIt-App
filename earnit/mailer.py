"""
Sends verification codes by email, using Gmail's SMTP server.

Keeping this separate from app.py the same reason storage.py is separate:
one job, one file. This module knows how to generate a code and mail it —
it has no idea what a "family" or "parent" is, and doesn't touch st.session_state.

Requires two secrets (in .streamlit/secrets.toml, never committed):
  smtp_email        -- a Gmail address
  smtp_app_password -- a 16-character Gmail "app password" (NOT the real
                        Google account password -- see
                        earnit-phase4-platform.md for how to generate one)
"""

import random
import smtplib
from email.mime.text import MIMEText

import streamlit as st

CODE_EXPIRY_MINUTES = 10


def generate_code():
    """A random 6-digit verification code, e.g. '048213'."""
    return f"{random.randint(0, 999999):06d}"


def send_verification_email(to_email, code):
    """Email a verification code. Raises if SMTP isn't configured or sending fails --
    callers should catch and show a friendly error rather than crash."""
    message = MIMEText(
        f"Your EarnIt verification code is: {code}\n\n"
        f"This code expires in {CODE_EXPIRY_MINUTES} minutes. "
        "If you didn't request this, you can ignore this email."
    )
    message["Subject"] = "Your EarnIt verification code"
    message["From"] = st.secrets["smtp_email"]
    message["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(st.secrets["smtp_email"], st.secrets["smtp_app_password"])
        server.sendmail(st.secrets["smtp_email"], [to_email], message.as_string())
