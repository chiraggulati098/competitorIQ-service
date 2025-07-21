import smtplib
from email.mime.text import MIMEText
import dotenv
import os
import time
import resend

dotenv.load_dotenv()
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

def send_email(receiver_email, subject, body):
    r = resend.Emails.send({
    "from": "onboarding@resend.dev",
    "to": receiver_email,
    "subject": subject,
    "html": body
    })

# def send_email(receiver_email, subject, body, retries=3, delay=2):
#     sender_email = "competitoriq@gmail.com"
#     app_password = GMAIL_PASSWORD

#     msg = MIMEText(body)
#     msg["Subject"] = subject
#     msg["From"] = sender_email
#     msg["To"] = receiver_email

#     last_error = None
#     for attempt in range(1, retries + 1):
#         try:
#             with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
#                 server.login(sender_email, app_password)
#                 server.send_message(msg)
#             return {"success": True, "attempt": attempt}
#         except smtplib.SMTPAuthenticationError:
#             return {"success": False, "error": "Authentication failed. Check your email and app password.", "attempt": attempt}
#         except smtplib.SMTPException as e:
#             last_error = {"success": False, "error": f"SMTP error: {str(e)}", "attempt": attempt}
#         except Exception as e:
#             last_error = {"success": False, "error": f"Unexpected error: {str(e)}", "attempt": attempt}
#         if attempt < retries:
#             time.sleep(delay)
#     return last_error if last_error else {"success": False, "error": "Unknown error.", "attempt": retries}
