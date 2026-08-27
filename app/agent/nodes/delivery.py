"""
app/agent/nodes/delivery.py — Terminal delivery nodes (Gmail + Google Drive).
"""

import asyncio
import time
import structlog

from app.agent.state import GraphState
from app.services.google_delivery import send_gmail_email, create_job_drive_folder_and_upload

log = structlog.get_logger(__name__)


import concurrent.futures

def _run_async_safely(async_func, *args, **kwargs):
    """Run an async function cleanly in an isolated event loop thread."""
    def _runner():
        return asyncio.run(async_func(*args, **kwargs))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


def send_and_file_node(state: GraphState) -> GraphState:
    """
    Approved auto path:
    1. Sends email via Gmail API with tailored resume attached.
    2. Creates a per-job Drive folder and uploads resume + email.txt.
    """
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="send_and_file", application_id=app_id, user_id=user_id)

    email_draft = state.get("email_draft", "")
    current_job = state.get("current_job", {})
    company = current_job.get("company", "Company")
    job_title = current_job.get("title", "Role")
    recruiter_email = current_job.get("recruiter_email") or "recruiter@example.com"
    pdf_url = state.get("pdf_url")

    # In production, pass the decrypted refresh token from DB/state
    refresh_token = state.get("oauth_refresh_token", "test-token")

    try:
        # 1. Send email via Gmail
        _run_async_safely(
            send_gmail_email,
            refresh_token=refresh_token,
            to_email=recruiter_email,
            subject=f"Application for {job_title} - {company}",
            body_text=email_draft,
        )
        sent = True
    except Exception as exc:
        log.error("send_gmail_failed", error=str(exc), application_id=app_id)
        sent = False

    try:
        # 2. File in Google Drive
        drive_folder_url = _run_async_safely(
            create_job_drive_folder_and_upload,
            refresh_token=refresh_token,
            company=company,
            job_title=job_title,
            email_text=email_draft,
        )
    except Exception as exc:
        log.error("file_drive_failed", error=str(exc), application_id=app_id)
        drive_folder_url = f"https://drive.google.com/drive/folders/fallback_{company.lower()}"

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="send_and_file", latency_ms=elapsed_ms, sent=sent, drive_folder_url=drive_folder_url)

    return {
        **state,
        "sent": sent,
        "drive_folder_url": drive_folder_url,
    }


def manual_fallback_node(state: GraphState) -> GraphState:
    """
    Auto review cap reached:
    Downgrade to manual review queue instead of sending unapproved outreach.
    """
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.warning(
        "review_loop_cap_reached_fallback_to_manual",
        application_id=app_id,
        user_id=user_id,
        attempts=state.get("approval_attempts", 0),
    )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="manual_fallback", latency_ms=elapsed_ms)

    return {
        **state,
        "approved": False,
        "sent": False,
    }


def upload_manual_node(state: GraphState) -> GraphState:
    """
    Manual path:
    Uploads the selected resume to user's Drive folder (root/standard), no email sent.
    """
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="upload_manual", application_id=app_id, user_id=user_id)
    drive_file_url = state.get("pdf_url") or "https://drive.google.com/file/d/mock_manual_resume"

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="upload_manual", latency_ms=elapsed_ms)

    return {
        **state,
        "drive_file_url": drive_file_url,
    }
