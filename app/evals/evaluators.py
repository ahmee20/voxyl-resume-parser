"""
app/evals/evaluators.py — Custom evaluator functions for LangSmith and offline testing.
"""

from typing import Any
import re


def evaluate_factual_grounding(
    original_resume: str,
    tailored_resume: str,
    must_not_invent: list[str] | None = None,
) -> dict[str, Any]:
    """
    Evaluates whether the tailored resume respects ground truth.
    Returns pass boolean, hallucination count, and score (0.0 to 1.0).
    """
    hallucinations = []
    if must_not_invent:
        for forbidden in must_not_invent:
            if forbidden.lower() in tailored_resume.lower() and forbidden.lower() not in original_resume.lower():
                hallucinations.append(forbidden)

    is_grounded = len(hallucinations) == 0
    return {
        "key": "factual_grounding",
        "score": 1.0 if is_grounded else 0.0,
        "pass": is_grounded,
        "hallucinations_detected": hallucinations,
    }


def evaluate_ats_keyword_match(
    job_description: str,
    tailored_resume: str,
    must_preserve_skills: list[str] | None = None,
) -> dict[str, Any]:
    """
    Evaluates keyword presence and density in the tailored resume.
    """
    skills = must_preserve_skills or ["python"]
    matched = [s for s in skills if s.lower() in tailored_resume.lower()]
    match_ratio = len(matched) / len(skills) if skills else 1.0

    return {
        "key": "ats_keyword_match",
        "score": round(match_ratio, 2),
        "pass": match_ratio >= 0.75,
        "matched_skills": matched,
        "missing_skills": [s for s in skills if s not in matched],
    }


def evaluate_email_quality(
    email_content: str | dict[str, Any],
    max_words: int = 250,
) -> dict[str, Any]:
    """
    Evaluates outreach email length, formatting, and professionalism.
    """
    if isinstance(email_content, dict):
        body = email_content.get("body", "")
        subject = email_content.get("subject", "")
    else:
        body = email_content
        subject = "Application"

    word_count = len(re.findall(r"\b\w+\b", body))
    is_concise = 15 <= word_count <= max_words
    has_subject = bool(subject.strip())
    has_salutation = any(body.lower().strip().startswith(greeting) for greeting in ["hi", "hello", "dear", "to the", "i am", "i'm"])

    score = 0.0
    if has_subject:
        score += 0.3
    if is_concise:
        score += 0.4
    if has_salutation:
        score += 0.3

    return {
        "key": "email_quality",
        "score": round(score, 2),
        "pass": score >= 0.7,
        "word_count": word_count,
        "is_concise": is_concise,
    }
