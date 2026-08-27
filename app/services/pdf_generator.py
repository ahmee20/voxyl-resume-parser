"""
app/services/pdf_generator.py — PDF generation service via PDF.co REST API.
"""

import httpx
import structlog
from app.config import settings

log = structlog.get_logger(__name__)

PDFCO_API_URL = "https://api.pdf.co/v1/pdf/convert/from/html"


async def convert_html_to_pdf(html_content: str, filename: str = "tailored_resume.pdf") -> str:
    """
    Call PDF.co to convert HTML string to a PDF document.
    Returns the public download URL of the generated PDF.
    """
    if not settings.pdfco_api_key or settings.pdfco_api_key == "test-pdfco-key":
        log.warning("pdfco_api_key_not_configured_using_mock")
        return f"https://api.pdf.co/mock-download/{filename}"

    payload = {
        "html": html_content,
        "name": filename,
        "margins": "15px 15px 15px 15px",
        "paperSize": "Letter",
        "orientation": "Portrait",
        "printBackground": True,
    }
    headers = {
        "x-api-key": settings.pdfco_api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(PDFCO_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data.get("error"):
            raise ValueError(f"PDF.co conversion error: {data.get('message', 'Unknown error')}")

        url = data.get("url")
        if not url:
            raise ValueError("PDF.co did not return a valid download URL.")
        return url
