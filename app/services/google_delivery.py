"""
app/services/google_delivery.py — Service for sending emails via Gmail API and filing docs in Google Drive.
"""

import base64
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
import httpx
import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings

log = structlog.get_logger(__name__)


def build_google_credentials(refresh_token: str) -> Credentials:
    """Build google.oauth2.credentials from refresh token."""
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


async def send_gmail_email(
    refresh_token: str,
    to_email: str,
    subject: str,
    body_text: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "resume.pdf",
) -> str:
    """
    Send an email via Gmail API using the candidate's authorized account.
    Returns the message ID.
    """
    if not refresh_token or refresh_token.startswith("test-"):
        log.warning("mock_gmail_send_executed", to=to_email, subject=subject)
        return "mock_message_id_123"

    creds = build_google_credentials(refresh_token)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    message = MIMEMultipart()
    message["to"] = to_email
    message["subject"] = subject

    # Attach body
    message.attach(MIMEText(body_text, "plain"))

    # Attach PDF if provided
    if pdf_bytes:
        pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_attachment.add_header("Content-Disposition", "attachment", filename=pdf_filename)
        message.attach(pdf_attachment)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    sent = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
    message_id = sent.get("id", "")
    log.info("gmail_message_sent", message_id=message_id, to=to_email)
    return message_id


async def create_job_drive_folder_and_upload(
    refresh_token: str,
    company: str,
    job_title: str,
    email_text: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "tailored_resume.pdf",
) -> str:
    """
    Create a new Google Drive folder for the application:
    "{Company} — {Job Title} — {Date}" and upload resume.pdf + email.txt into it.
    Returns the Drive folder URL.
    """
    if not refresh_token or refresh_token.startswith("test-"):
        log.warning("mock_drive_folder_created", company=company, job_title=job_title)
        return f"https://drive.google.com/drive/folders/mock_folder_{company.lower().replace(' ', '_')}"

    creds = build_google_credentials(refresh_token)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder_name = f"{company} — {job_title} — {date_str}"

    # 1. Create Folder
    folder_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=folder_metadata, fields="id, webViewLink").execute()
    folder_id = folder.get("id")
    folder_url = folder.get("webViewLink", f"https://drive.google.com/drive/folders/{folder_id}")

    # 2. Upload email.txt
    from googleapiclient.http import MediaInMemoryUpload
    email_media = MediaInMemoryUpload(email_text.encode("utf-8"), mimetype="text/plain")
    email_file_metadata = {
        "name": "email_draft.txt",
        "parents": [folder_id],
    }
    service.files().create(body=email_file_metadata, media_body=email_media).execute()

    # 3. Upload PDF resume
    if pdf_bytes:
        pdf_media = MediaInMemoryUpload(pdf_bytes, mimetype="application/pdf")
        pdf_file_metadata = {
            "name": pdf_filename,
            "parents": [folder_id],
        }
        service.files().create(body=pdf_file_metadata, media_body=pdf_media).execute()

    log.info("drive_folder_filed", folder_name=folder_name, folder_url=folder_url)
    return folder_url
