"""
app/evals/runner.py — Standalone LangSmith dataset evaluator and offline CLI runner.
"""

import structlog
from langsmith import Client

from app.config import settings
from app.evals.dataset import BENCHMARK_DATASET
from app.evals.evaluators import (
    evaluate_factual_grounding,
    evaluate_ats_keyword_match,
    evaluate_email_quality,
)
from app.agent.nodes.analyze_gaps import analyze_gaps_node
from app.agent.nodes.tailor_resume import tailor_resume_node
from app.agent.nodes.draft_email import draft_email_node
from app.agent.state import GraphState

log = structlog.get_logger(__name__)


def run_offline_evaluations() -> dict:
    """
    Run evaluation pipeline against all benchmark dataset test cases.
    Returns overall scores and case-by-case report.
    """
    results = []
    total_grounding = 0.0
    total_ats = 0.0
    total_email = 0.0

    print("\n" + "=" * 70)
    print("  RUNNING LANGSMITH BENCHMARK EVALUATION SUITE")
    print("=" * 70)

    for case in BENCHMARK_DATASET:
        print(f"\n[EVAL] Testing: {case['name']} (ID: {case['id']})")
        state: GraphState = {
            "application_id": 999,
            "user_id": 1,
            "resume_text": case["resume_text"],
            "resume_html": "<div><h1>Candidate Resume</h1><div class='experience'>Experience</div></div>",
            "current_job": {
                "title": case["name"],
                "company": "Target Company",
                "description": case["job_description"],
            },
        }

        # 1. Run pipeline nodes
        state = analyze_gaps_node(state)
        state = tailor_resume_node(state)
        state = draft_email_node(state)

        tailored_content = state.get("tailored_resume_html", "")
        email_content = state.get("email_draft", "")

        # 2. Run evaluators
        grounding = evaluate_factual_grounding(
            original_resume=case["resume_text"],
            tailored_resume=tailored_content,
            must_not_invent=case["ground_truth"]["must_not_invent"],
        )

        ats = evaluate_ats_keyword_match(
            job_description=case["job_description"],
            tailored_resume=tailored_content,
            must_preserve_skills=case["ground_truth"]["must_preserve_skills"],
        )

        email = evaluate_email_quality(email_content=email_content)

        total_grounding += grounding["score"]
        total_ats += ats["score"]
        total_email += email["score"]

        case_summary = {
            "id": case["id"],
            "name": case["name"],
            "grounding_score": grounding["score"],
            "grounding_pass": grounding["pass"],
            "ats_score": ats["score"],
            "ats_pass": ats["pass"],
            "email_score": email["score"],
            "email_pass": email["pass"],
        }
        results.append(case_summary)

        print(f"  - Factual Grounding: {grounding['score'] * 100:.0f}% (Pass: {grounding['pass']})")
        print(f"  - ATS Keyword Match: {ats['score'] * 100:.0f}% (Pass: {ats['pass']})")
        print(f"  - Email Quality:    {email['score'] * 100:.0f}% (Pass: {email['pass']})")

    n = len(BENCHMARK_DATASET)
    avg_grounding = total_grounding / n
    avg_ats = total_ats / n
    avg_email = total_email / n

    print("\n" + "-" * 70)
    print(f"  OVERALL BENCHMARK SUMMARY (N={n})")
    print(f"  - Mean Factual Grounding: {avg_grounding * 100:.1f}%")
    print(f"  - Mean ATS Keyword Match: {avg_ats * 100:.1f}%")
    print(f"  - Mean Email Quality:    {avg_email * 100:.1f}%")
    print("=" * 70 + "\n")

    return {
        "dataset_size": n,
        "mean_factual_grounding": avg_grounding,
        "mean_ats_keyword_match": avg_ats,
        "mean_email_quality": avg_email,
        "results": results,
    }


def upload_dataset_to_langsmith() -> None:
    """Upload benchmark dataset to LangSmith if API key is active."""
    api_key = settings.langchain_api_key
    if not api_key or api_key.startswith("test-") or api_key == "lsv2_pt_your_actual_key_here":
        log.warning("langsmith_api_key_not_configured_skipping_remote_sync")
        return

    try:
        client = Client(api_key=api_key)
        dataset_name = "job-autopilot-evaluation-benchmark"

        if not client.has_dataset(dataset_name=dataset_name):
            dataset = client.create_dataset(
                dataset_name=dataset_name,
                description="Ground-truth resume tailoring & ATS review evaluation dataset",
            )
            for case in BENCHMARK_DATASET:
                client.create_example(
                    inputs={
                        "resume_text": case["resume_text"],
                        "job_description": case["job_description"],
                    },
                    outputs=case["ground_truth"],
                    dataset_id=dataset.id,
                )
            log.info("langsmith_dataset_created", name=dataset_name)
        else:
            log.info("langsmith_dataset_exists", name=dataset_name)
    except Exception as exc:
        log.error("langsmith_sync_failed", error=str(exc))


if __name__ == "__main__":
    upload_dataset_to_langsmith()
    run_offline_evaluations()
