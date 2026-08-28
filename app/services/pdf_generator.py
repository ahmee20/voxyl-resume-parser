"""
app/services/pdf_generator.py - PDF generation service via PDF.co REST API.
"""

from __future__ import annotations

import json
import asyncio
from typing import Any

import httpx
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.services.llm import get_llm

log = structlog.get_logger(__name__)

PDFCO_API_URL = "https://api.pdf.co/v1/pdf/convert/from/html"
PDFCO_TEMPLATE_URL = "https://api.pdf.co/v1/templates/html/{template_id}"
_TEMPLATE_HTML_CACHE: dict[int, str] = {}


async def _diagnose_pdfco_failure(error: str, payload: dict[str, Any]) -> None:
    try:
        llm = get_llm(temperature=0.0, max_tokens=2000)
        response = await asyncio.to_thread(
            llm.invoke,
            [
                SystemMessage(
                    content=(
                        "You diagnose PDF.co HTML-to-PDF template failures. Explain the likely issue and the exact correction. "
                        "PDF.co template mode requires valid HTML in 'html', a numeric 'templateid', and 'templatedata' as a JSON string "
                        "whose keys match the saved template. Do not invent missing template fields."
                    ),
                ),
                HumanMessage(
                    content=f"PDF.co error:\n{error}\n\nRequest payload:\n{json.dumps(payload, ensure_ascii=False)}",
                ),
            ],
        )
        diagnosis = getattr(response, "content", str(response))
        log.error("pdfco_failure_diagnosed", error=error, diagnosis=str(diagnosis)[:4000])
    except Exception as exc:
        log.error("pdfco_failure_diagnosis_failed", error=error, diagnosis_error=str(exc))


async def _post_pdfco_with_retry(payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(PDFCO_API_URL, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                if data.get("error"):
                    raise ValueError(f"PDF.co conversion error: {data.get('message', 'Unknown error')}")
                return data
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                await asyncio.sleep(2)

    await _diagnose_pdfco_failure(str(last_error), payload)
    raise last_error or RuntimeError("PDF.co conversion failed")


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            pruned = _prune_empty(item)
            if pruned in (None, "", [], {}):
                continue
            cleaned[key] = pruned
        return cleaned
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            pruned = _prune_empty(item)
            if pruned in (None, "", [], {}):
                continue
            cleaned_list.append(pruned)
        return cleaned_list
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


async def _fetch_template_html(template_id: int) -> str | None:
    cached = _TEMPLATE_HTML_CACHE.get(template_id)
    if cached:
        return cached

    headers = {
        "x-api-key": settings.pdfco_api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(PDFCO_TEMPLATE_URL.format(template_id=template_id), headers=headers)
        response.raise_for_status()
        data = response.json()
        template_html = data.get("body") or data.get("html")
        if isinstance(template_html, str) and template_html.strip():
            _TEMPLATE_HTML_CACHE[template_id] = template_html
            return template_html
    return None


async def convert_html_to_pdf(
    html_content: str,
    filename: str = "tailored_resume.pdf",
    template_data: dict[str, Any] | None = None,
    template_id: int | None = None,
) -> str:
    """
    Call PDF.co to convert HTML into a PDF document.

    When a template id is provided, PDF.co renders the saved HTML template and
    fills it with the structured JSON payload. We do not fall back to plain HTML
    rendering for resume PDFs.
    """
    if not settings.pdfco_api_key or settings.pdfco_api_key == "test-pdfco-key":
        log.warning("pdfco_api_key_not_configured_using_mock")
        return f"https://api.pdf.co/mock-download/{filename}"

    resolved_template_id = template_id or settings.pdfco_resume_template_id
    use_template_mode = template_id is not None or template_data is not None

    payload: dict[str, Any] = {
        "name": filename,
        "margins": "15px 15px 15px 15px",
        "paperSize": "Letter",
        "orientation": "Portrait",
        "printBackground": True,
    }

    cleaned_template_data = _prune_empty(template_data) if template_data else {}
    if use_template_mode:
        payload["templateid"] = resolved_template_id
        payload["templatedata"] = json.dumps(cleaned_template_data if isinstance(cleaned_template_data, dict) else {}, ensure_ascii=False)
        try:
            template_html = await _fetch_template_html(resolved_template_id)
            if not template_html:
                raise ValueError(f"PDF.co template {resolved_template_id} returned empty HTML.")
            payload["html"] = template_html
        except Exception as exc:
            log.error("pdfco_template_fetch_failed", template_id=resolved_template_id, error=str(exc))
            raise
    else:
        payload["html"] = html_content

    headers = {
        "x-api-key": settings.pdfco_api_key,
        "Content-Type": "application/json",
    }

    data = await _post_pdfco_with_retry(payload, headers)

    url = data.get("url")
    if not url:
        raise ValueError("PDF.co did not return a valid download URL.")
    return url
