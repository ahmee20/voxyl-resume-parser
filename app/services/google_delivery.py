"""
app/services/google_delivery.py — Lightweight REST-based delivery for Gmail API and Google Drive.
Uses async httpx directly, avoiding the heavy google-api-python-client dependency.
"""

import base64
import json
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
import structlog

from app.config import settings

log = structlog.get_logger(__name__)


async def _get_access_token(refresh_token: str) -> str:
    """Exchange OAuth refresh token for a fresh Google access token."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if resp.status_code != 200:
            log.error("google_token_refresh_failed", status_code=resp.status_code, error=resp.text)
            raise RuntimeError(f"Failed to refresh Google token: {resp.text}")
        data = resp.json()
        return data["access_token"]


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

    access_token = await _get_access_token(refresh_token)

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

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw_message},
        )
        if resp.status_code not in (200, 201):
            log.error("gmail_send_failed", status_code=resp.status_code, error=resp.text)
            raise RuntimeError(f"Gmail API error: {resp.text}")

        sent_data = resp.json()
        message_id = sent_data.get("id", "")
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

    access_token = await _get_access_token(refresh_token)
    headers = {"Authorization": f"Bearer {access_token}"}

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder_name = f"{company} — {job_title} — {date_str}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Create Folder
        folder_resp = await client.post(
            "https://www.googleapis.com/drive/v3/files?fields=id,webViewLink",
            headers=headers,
            json={
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            },
        )
        if folder_resp.status_code not in (200, 201):
            log.error("drive_folder_create_failed", status_code=folder_resp.status_code, error=folder_resp.text)
            raise RuntimeError(f"Drive API folder creation error: {folder_resp.text}")

        folder_data = folder_resp.json()
        folder_id = folder_data.get("id")
        folder_url = folder_data.get("webViewLink", f"https://drive.google.com/drive/folders/{folder_id}")

        # 2. Upload email_draft.txt
        await client.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            headers=headers,
            files={
                "metadata": (None, json.dumps({"name": "email_draft.txt", "parents": [folder_id]}), "application/json; charset=UTF-8"),
                "file": ("email_draft.txt", email_text.encode("utf-8"), "text/plain"),
            },
        )

        # 3. Upload resume PDF if present
        if pdf_bytes:
            await client.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                headers=headers,
                files={
                    "metadata": (None, json.dumps({"name": pdf_filename, "parents": [folder_id]}), "application/json; charset=UTF-8"),
                    "file": (pdf_filename, pdf_bytes, "application/pdf"),
                },
            )

        log.info("drive_folder_filed", folder_name=folder_name, folder_url=folder_url)
        return folder_url
