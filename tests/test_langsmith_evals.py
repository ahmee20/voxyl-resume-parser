"""
tests/test_langsmith_evals.py — Pytest evaluation suite marked with @pytest.mark.eval.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.evals.evaluators import (
    evaluate_factual_grounding,
    evaluate_ats_keyword_match,
    evaluate_email_quality,
)
from app.evals.dataset import BENCHMARK_DATASET
from app.evals.runner import run_offline_evaluations


@pytest.mark.eval
def test_evaluator_factual_grounding():
    original = "Experienced Python and FastAPI backend engineer."
    
    # Grounded response: passes
    grounded = "<div>Experienced Python and FastAPI backend engineer. Optimized API latency.</div>"
    result = evaluate_factual_grounding(original, grounded, must_not_invent=["Invented PyTorch", "Designed GPT-4"])
    assert result["pass"] is True
    assert result["score"] == 1.0

    # Hallucinated response: fails
    hallucinated = "<div>Experienced Python engineer. Designed GPT-4 and trained frontier models.</div>"
    result_fail = evaluate_factual_grounding(original, hallucinated, must_not_invent=["Designed GPT-4"])
    assert result_fail["pass"] is False
    assert result_fail["score"] == 0.0
    assert "Designed GPT-4" in result_fail["hallucinations_detected"]


@pytest.mark.eval
def test_evaluator_ats_keyword_match():
    job_desc = "Looking for Senior Engineer with Python, Docker, Kubernetes, and PostgreSQL."
    resume_good = "<div>Skills: Python, Docker, Kubernetes, PostgreSQL.</div>"
    res_good = evaluate_ats_keyword_match(job_desc, resume_good, must_preserve_skills=["Python", "Docker", "Kubernetes", "PostgreSQL"])
    assert res_good["pass"] is True
    assert res_good["score"] == 1.0

    resume_sparse = "<div>Skills: Python.</div>"
    res_sparse = evaluate_ats_keyword_match(job_desc, resume_sparse, must_preserve_skills=["Python", "Docker", "Kubernetes", "PostgreSQL"])
    assert res_sparse["pass"] is False
    assert res_sparse["score"] == 0.25


@pytest.mark.eval
def test_evaluator_email_quality():
    body = "Hi Hiring Team,\n\nI am writing to apply for the Senior AI Systems Engineer role. With 6 years in Python microservices, I would love to contribute to your platform.\n\nBest,\nJohn"
    result = evaluate_email_quality(body)
    assert result["pass"] is True
    assert result["score"] >= 0.7


@pytest.mark.eval
def test_benchmark_dataset_execution():
    """
    Run offline evaluations across the benchmark dataset.
    Mocks LLM to verify deterministic scoring logic.
    """
    mock_gap_json = '{"missing_skills": ["LangGraph"], "matching_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "React", "TypeScript", "Team Leadership"], "match_score": 85}'
    mock_tailored = '<div><p>Candidate with Python, FastAPI, PostgreSQL, Docker, Kubernetes, Helm, AsyncIO, Prometheus, React, TypeScript, Team Leadership.</p></div>'
    mock_email = 'Hi Hiring Team, I am writing to express my interest in this role given my backend systems and Python experience. Best, Alex'

    with patch("app.agent.nodes.analyze_gaps.get_llm") as mock_gaps_llm, \
         patch("app.agent.nodes.tailor_resume.get_llm") as mock_tailor_llm, \
         patch("app.agent.nodes.draft_email.get_llm") as mock_email_llm:

        gaps_chat = MagicMock()
        gaps_chat.invoke.return_value = MagicMock(content=mock_gap_json)
        mock_gaps_llm.return_value = gaps_chat

        tailor_chat = MagicMock()
        tailor_chat.invoke.return_value = MagicMock(content=mock_tailored)
        mock_tailor_llm.return_value = tailor_chat

        email_chat = MagicMock()
        email_chat.invoke.return_value = MagicMock(content=mock_email)
        mock_email_llm.return_value = email_chat

        eval_summary = run_offline_evaluations()

        assert eval_summary["dataset_size"] == len(BENCHMARK_DATASET)
        assert eval_summary["mean_factual_grounding"] == 1.0  # 0% hallucination
        assert eval_summary["mean_ats_keyword_match"] >= 0.75
        assert eval_summary["mean_email_quality"] >= 0.70
