"""
app/evals/dataset.py — Ground-truth evaluation dataset for LangSmith experiments.
"""

from typing import Any

BENCHMARK_DATASET: list[dict[str, Any]] = [
    {
        "id": "eval-case-1-ai-engineer",
        "name": "Senior Software Engineer -> AI Systems Engineer",
        "resume_text": """
John Doe
Software Engineer with 6 years experience in Python, FastAPI, Docker, and PostgreSQL.
Experience:
- Built distributed microservices handling 50k RPS.
- Designed database schemas and migration pipelines using SQLAlchemy and Alembic.
- Implemented background task queues with Celery and Redis.
Skills: Python, FastAPI, PostgreSQL, Docker, Redis, Git, Linux.
""",
        "job_description": """
Senior AI Systems Engineer at Scale AI.
Requirements:
- Strong Python systems engineering and backend microservices architecture.
- Experience with Agentic AI workflows, LangChain or LangGraph is a plus.
- Production experience with PostgreSQL and Docker.
""",
        "ground_truth": {
            "must_preserve_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "must_not_invent": ["10 years LLM experience", "Designed GPT-4", "Quantum computing"],
            "expected_match_score_min": 75,
        },
    },
    {
        "id": "eval-case-2-ml-infra",
        "name": "Backend Developer -> ML Infrastructure Specialist",
        "resume_text": """
Jane Smith
Backend Engineer specialized in Python, Kubernetes, CI/CD, and asynchronous networking.
Experience:
- Deployed high-throughput APIs on Kubernetes with automated blue-green rollouts.
- Optimized async I/O bottlenecks in Python asyncio microservices.
Skills: Python, Kubernetes, CI/CD, AsyncIO, Prometheus, Helm.
""",
        "job_description": """
ML Infrastructure Engineer at Frontier Labs.
Requirements:
- Expertise in Kubernetes, container orchestration, and Helm deployments.
- Strong asynchronous Python backend development.
- Monitoring and telemetry with Prometheus.
""",
        "ground_truth": {
            "must_preserve_skills": ["Kubernetes", "Helm", "AsyncIO", "Prometheus"],
            "must_not_invent": ["Trained 100B parameter models", "PhD in Deep Learning"],
            "expected_match_score_min": 80,
        },
    },
    {
        "id": "eval-case-3-fullstack",
        "name": "Fullstack Engineer -> Technical Lead",
        "resume_text": """
Alex Taylor
Fullstack Engineer with experience leading agile teams, building React frontends and Python APIs.
Experience:
- Mentored junior engineers and led sprint planning.
- Designed responsive React/TypeScript interfaces and integrated RESTful backend APIs.
Skills: React, TypeScript, Python, REST APIs, Team Leadership.
""",
        "job_description": """
Lead Full Stack Engineer at High Growth Startup.
Requirements:
- Demonstrated track record in React, TypeScript, and modern Python backends.
- Strong team leadership, communication, and technical mentoring capabilities.
""",
        "ground_truth": {
            "must_preserve_skills": ["React", "TypeScript", "Python", "Team Leadership"],
            "must_not_invent": ["CPO at Fortune 500", "Invented React"],
            "expected_match_score_min": 85,
        },
    },
]
