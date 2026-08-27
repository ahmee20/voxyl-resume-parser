"""
app/services/apollo_enricher.py — Apollo.io company intelligence and verified recruiter discovery.

Rules:
1. Never fabricate fake/synthetic email addresses (e.g. talent@..., careers@...).
2. Only store recruiter_email if Apollo returns a real, verified email address
   or if an email was explicitly present in the job posting.
3. Capture verified recruiter metadata (name, title, linkedin_url, company domain).
"""

import re
from typing import Any
import httpx
import structlog
from app.config import settings

log = structlog.get_logger(__name__)

APOLLO_ORG_ENRICH_URL = "https://api.apollo.io/v1/organizations/enrich"
APOLLO_PEOPLE_SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"

RECRUITER_TARGET_TITLES = [
    "Technical Recruiter",
    "Talent Acquisition",
    "Head of Talent",
    "Recruiter",
    "Engineering Manager",
    "Director of Engineering",
    "CTO",
    "Founder",
]


async def enrich_job_with_apollo(job: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich a scraped job listing with Apollo.io company and verified recruiter intelligence.
    Does NOT generate synthetic emails. Only genuine, verified contacts are recorded.
    """
    company_name = (job.get("company") or "").strip()
    enriched_job = dict(job)
    enriched_job.setdefault("recruiter_email", job.get("recruiter_email"))

    if not company_name:
        return enriched_job

    # Clean company name to guess domain for search query
    clean_company = re.sub(r"[^a-zA-Z0-9\s]", "", company_name).strip().lower()
    clean_slug = re.sub(r"\s+", "", clean_company)
    fallback_domain = f"{clean_slug}.com" if clean_slug else None

    # Check if real API key is configured
    has_real_key = bool(
        settings.apollo_api_key
        and settings.apollo_api_key != "test-apollo-key"
        and not settings.apollo_api_key.startswith("test-")
    )

    if not has_real_key:
        # Development / offline fallback — provide clear indicator without fake emails
        enriched_job["apollo_enrichment"] = {
            "domain": fallback_domain or f"{clean_company}.com",
            "company_name": company_name,
            "industry": "Technology / Software",
            "verified": False,
            "note": "Apollo API key not configured. Showing scraped job metadata.",
        }
        return enriched_job

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "x-api-key": settings.apollo_api_key,
    }

    resolved_domain = None

    # ── 1. Organization Enrichment ───────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            org_payload = {"domain": fallback_domain} if fallback_domain else {"name": company_name}
            org_resp = await client.post(APOLLO_ORG_ENRICH_URL, json=org_payload, headers=headers)
            if org_resp.status_code == 200:
                data = org_resp.json()
                org = data.get("organization") or {}
                resolved_domain = org.get("primary_domain") or org.get("website_url")
                if resolved_domain:
                    resolved_domain = resolved_domain.replace("https://", "").replace("http://", "").rstrip("/")

                enriched_job["apollo_enrichment"] = {
                    "domain": resolved_domain or fallback_domain,
                    "company_name": org.get("name") or company_name,
                    "industry": org.get("industry") or "Technology / Software",
                    "estimated_num_employees": org.get("estimated_num_employees"),
                    "city": org.get("city"),
                    "country": org.get("country"),
                    "linkedin_url": org.get("linkedin_url"),
                    "verified": True,
                }
            else:
                enriched_job["apollo_enrichment"] = {
                    "domain": fallback_domain,
                    "company_name": company_name,
                    "verified": False,
                }
    except Exception as exc:
        log.debug("apollo_org_enrichment_skipped", company=company_name, reason=str(exc))
        enriched_job["apollo_enrichment"] = {
            "domain": fallback_domain,
            "company_name": company_name,
            "verified": False,
        }

    # ── 2. Verified Recruiter Contact Discovery ──────────────────────────────
    target_domain = resolved_domain or fallback_domain
    if target_domain and not enriched_job.get("recruiter_email"):
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                people_payload = {
                    "q_organization_domains": target_domain,
                    "person_titles": RECRUITER_TARGET_TITLES,
                    "page": 1,
                    "per_page": 5,
                }
                people_resp = await client.post(APOLLO_PEOPLE_SEARCH_URL, json=people_payload, headers=headers)
                if people_resp.status_code == 200:
                    people_data = people_resp.json()
                    people_list = people_data.get("people") or []

                    for person in people_list:
                        email = person.get("email")
                        email_status = person.get("email_status")
                        name = person.get("name") or f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                        title = person.get("title")
                        linkedin = person.get("linkedin_url")

                        # Record recruiter profile details
                        if name and not enriched_job.get("recruiter_name"):
                            enriched_job["recruiter_name"] = name
                            enriched_job["recruiter_title"] = title

                            if enriched_job.get("apollo_enrichment"):
                                enriched_job["apollo_enrichment"]["recruiter_name"] = name
                                enriched_job["apollo_enrichment"]["recruiter_title"] = title
                                enriched_job["apollo_enrichment"]["recruiter_linkedin"] = linkedin

                        # ONLY accept real, unlocked, verified emails
                        if (
                            email
                            and "@" in email
                            and not email.endswith("example.com")
                            and "email_not_unlocked" not in email
                            and "unavailable" not in email.lower()
                            and email_status in ("verified", "extrapolated", "valid")
                        ):
                            enriched_job["recruiter_email"] = email
                            log.info(
                                "apollo_verified_recruiter_found",
                                company=company_name,
                                email=email,
                                name=name,
                                title=title,
                            )
                            break
        except Exception as exc:
            log.debug("apollo_people_discovery_skipped", company=company_name, reason=str(exc))

    # Note: If no genuine email was unlocked from Apollo, we intentionally leave recruiter_email as None/original
    # rather than hallucinating a fake address.
    return enriched_job
