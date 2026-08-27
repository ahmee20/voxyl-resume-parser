"""
app/services/apify_scraper.py — Job scraping service using Apify Client.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from apify_client import ApifyClient

from app.config import settings

log = structlog.get_logger(__name__)

COUNTRY_MAP = {
    "REMOTE": "Remote",
    "US": "United States",
    "CA": "Canada",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "AU": "Australia",
    "IN": "India",
    "PK": "Pakistan",
    "SG": "Singapore",
    "NL": "Netherlands",
    "AE": "United Arab Emirates",
    "SA": "Saudi Arabia",
    "IE": "Ireland",
    "CH": "Switzerland",
    "JP": "Japan",
    "SE": "Sweden",
    "ES": "Spain",
    "IT": "Italy",
    "BR": "Brazil",
    "NZ": "New Zealand",
    "PL": "Poland",
    "ZA": "South Africa",
}


def _clean_str(val: Any, default: str = "") -> str:
    """Helper: safely extract clean text string from arbitrary nested structures or dicts."""
    if val is None:
        return default
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        return str(val.get("name") or val.get("title") or val.get("text") or val.get("label") or default).strip()
    if isinstance(val, (list, tuple)):
        cleaned = [_clean_str(x) for x in val if x]
        return ", ".join(cleaned)
    return str(val).strip()


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Best-effort parsing of a timestamp-like value into UTC datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        cleaned = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def scrape_jobs_from_apify(
    queries: list[str],
    countries: Optional[list[str]] = None,
    max_results: Optional[int] = None,
    posted_within_hours: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Run Apify Actor or return mock listings if token is not configured.
    Normalizes records into a standard dictionary format.
    When max_results is None, the scraper uses the configured default cap.
    """
    target_role = queries[0] if queries else "Software Engineer"
    selected_countries = countries or ["REMOTE", "US"]
    country_names = [COUNTRY_MAP.get(c.upper(), c) for c in selected_countries]
    location_str = ", ".join(country_names) if country_names else "Remote"
    limit = max_results if max_results is not None else settings.apify_max_results
    limit = limit if limit and limit > 0 else None
    window = timedelta(hours=posted_within_hours) if posted_within_hours else None
    cutoff = datetime.now(timezone.utc) - window if window else None

    if not settings.apify_api_token or settings.apify_api_token == "test-apify-token":
        log.warning("apify_token_not_configured_using_mock_results", queries=queries, location=location_str)
        now_iso = datetime.now(timezone.utc).isoformat()
        mock_count = limit or settings.apify_max_results
        return [
            {
                "external_id": f"mock_job_{i}",
                "title": f"{target_role} - NextGen Platform",
                "company": f"AI Enterprise {i + 1}",
                "url": f"https://jobs.example.com/ai-roles/job-{i + 1}",
                "description": (
                    f"We are hiring a {target_role} in {country_names[i % len(country_names)]}. "
                    "Requirements: Python, Cloud Systems, and AI integrations."
                ),
                "location": location_str,
                "recruiter_email": f"talent@company{i + 1}.ai",
                "posted_at": now_iso,
                "source": "apify",
            }
            for i in range(mock_count)
        ]

    try:
        client = ApifyClient(settings.apify_api_token)
        actor_id = settings.apify_actor_id or "curious_coder~linkedin-jobs-scraper"

        # Build schema-tailored input parameters.
        if "linkedin" in actor_id.lower() or "curious_coder" in actor_id.lower():
            primary_loc = country_names[0] if country_names else "United States"
            if primary_loc.lower() == "remote" and len(country_names) > 1:
                primary_loc = country_names[1]

            run_input: dict[str, Any] = {
                "keywords": target_role,
                "location": primary_loc,
                "datePosted": "past24Hours",
                "scrapeCompany": False,
            }
            if limit:
                run_input["limitPerSource"] = limit
        else:
            run_input = {
                "position": target_role,
                "keywords": target_role,
                "location": location_str,
            }
            if limit:
                run_input["maxItems"] = limit
                run_input["limitPerSource"] = limit

        log.info("triggering_apify_actor", actor_id=actor_id, run_input=run_input)
        run = client.actor(actor_id).call(run_input=run_input)

        dataset_id = None
        if run is not None:
            dataset_id = getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)
            if not dataset_id and isinstance(run, dict):
                dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id") or run.get("data", {}).get("defaultDatasetId")

        if not dataset_id:
            log.error("apify_no_dataset_id_returned", run=str(run))
            return []

        dataset_res = client.dataset(dataset_id).list_items()
        dataset_items = getattr(dataset_res, "items", None) or (dataset_res if isinstance(dataset_res, list) else [])

        log.info("apify_raw_items_fetched", count=len(dataset_items))

        normalized_jobs: list[dict[str, Any]] = []
        for idx, item in enumerate(dataset_items if limit is None else dataset_items[:limit]):
            item_dict = item if isinstance(item, dict) else (item.__dict__ if hasattr(item, "__dict__") else {})

            raw_url = (
                item_dict.get("link")
                or item_dict.get("jobUrl")
                or item_dict.get("url")
                or item_dict.get("applyUrl")
                or f"https://linkedin.com/jobs/view/{item_dict.get('id') or idx}"
            )
            raw_title = (
                item_dict.get("title")
                or item_dict.get("jobTitle")
                or item_dict.get("positionName")
                or target_role
            )
            raw_company = (
                item_dict.get("companyName")
                or item_dict.get("company")
                or item_dict.get("company_name")
                or item_dict.get("companyDetails")
                or "Technology Company"
            )
            raw_location = (
                item_dict.get("location")
                or item_dict.get("city")
                or item_dict.get("country")
                or item_dict.get("place")
                or item_dict.get("locationName")
                or location_str
            )
            raw_desc = (
                item_dict.get("description")
                or item_dict.get("jobDescription")
                or item_dict.get("text")
                or item_dict.get("descriptionText")
                or f"Job listing for {raw_title} at {raw_company}."
            )
            raw_email = (
                item_dict.get("email")
                or item_dict.get("contactEmail")
                or item_dict.get("recruiterEmail")
                or item_dict.get("jobPosterEmail")
            )
            raw_posted = (
                item_dict.get("postedDate")
                or item_dict.get("postedTime")
                or item_dict.get("postedAt")
                or item_dict.get("postingDate")
            )
            posted_dt = _parse_timestamp(raw_posted)
            if cutoff and posted_dt and posted_dt < cutoff:
                continue

            clean_title = _clean_str(raw_title, default=target_role)
            clean_company = _clean_str(raw_company, default="Company")
            clean_url = _clean_str(raw_url, default=f"https://linkedin.com/jobs/view/{idx}")
            clean_location = _clean_str(raw_location, default=location_str) or location_str
            clean_desc = _clean_str(raw_desc, default=f"Job posting for {clean_title} at {clean_company}.")
            clean_email = _clean_str(raw_email, default="") or None
            clean_posted = _clean_str(raw_posted, default="") or None

            normalized_jobs.append(
                {
                    "external_id": str(item_dict.get("id") or item_dict.get("jobId") or idx),
                    "title": clean_title,
                    "company": clean_company,
                    "url": clean_url,
                    "description": clean_desc,
                    "location": clean_location,
                    "recruiter_email": clean_email,
                    "posted_at": clean_posted,
                    "source": "apify",
                }
            )

        log.info("apify_scrape_success", total_normalized=len(normalized_jobs))
        return normalized_jobs

    except Exception as exc:
        log.error("apify_scrape_failed", error=str(exc))
        return []
