"""Shared fixtures for the generator.py test suite."""

import copy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def resume_template_text(repo_root) -> str:
    return (repo_root / "RESUME.template.md").read_text(encoding="utf-8")


@pytest.fixture
def readme_template_text(repo_root) -> str:
    return (repo_root / "README.template.md").read_text(encoding="utf-8")


@pytest.fixture
def analysis_prompt_template_text(repo_root) -> str:
    return (repo_root / "ANALYSIS_PROMPT.template.txt").read_text(encoding="utf-8")


def _base_kb() -> dict:
    """A small, hand-built knowledge base with the same shape as
    profile.json, deliberately covering a few edge cases:
    - one job with team_context, one without
    - one skill category present in CATEGORY_LABELS, one that isn't
      (exercises the title-case fallback)
    - a job whose title_by_variant is missing the "SDET" key (exercises
      the "fall back to the first available variant" branch)
    - bullets with an "_alt" id, which the baseline-context trimming
      should drop
    """
    return {
        "meta": {
            "output_rules": {
                "never_fabricate": "Do not invent facts.",
                "never_use_em_dash": "Never use an em dash.",
            }
        },
        "personal_info": {
            "full_name": "Jane Q. Doe",
            "email": "jane@example.com",
            "phone": "555-1234",
            "linkedin": "linkedin.com/in/janedoe",
            "portfolio_or_profile": "example.com/jane",
            "location_short": "Anytown, USA",
        },
        "education": [
            {
                "institution": "State University",
                "field of study": "Computer Science",
                "concentration": "Computer Science",
                "degree": "Bachelor of Science in Computer Science",
                "graduation date": "2015",
            }
        ],
        "summary_variants": {
            "SDE": "SDE summary.",
            "SDET": "SDET summary.",
        },
        "summary_building_blocks": {},
        "skills": {
            "languages": ["Python", "Go"],
            "operating_systems": ["Linux", "macOS"],
            "skill_selection_guidance": "Pick relevant ones.",
        },
        "work_experience": [
            {
                "title_by_variant": {"SDE": "Software Engineer", "SDET": "SDET"},
                "company": "Acme Corp",
                "team_context": "Team Widgets, Platform Squad",
                "start_date": "2020-01",
                "end_date": "2023-01",
                "technologies": ["Python"],
                "bullets": [
                    {"id": "acme_1", "text": "Built the widget service."},
                    {"id": "acme_1_alt", "text": "Alternate phrasing, should be dropped."},
                ],
            },
            {
                "title_by_variant": {"SDE": "Junior Engineer"},
                "company": "Beta Inc",
                "start_date": "2018-01",
                "end_date": "2020-01",
                "technologies": ["Java"],
                "bullets": [
                    {"id": "beta_1", "text": "Maintained the beta system."},
                ],
            },
        ],
        "career_narrative_notes": {
            "strongest_differentiators": ["Ships fast.", "Deep testing background."]
        },
        "cover_letter_building_blocks": {
            "generic_fallback_template": "Dear Hiring Manager, ... Sincerely, Jane",
            "opening_hook_options": ["Hook option."],
        },
        "output_format_instructions": {},
        "generation_workflow_for_llm": {},
    }


@pytest.fixture
def sample_kb() -> dict:
    """A fresh copy of the sample knowledge base for each test, so tests
    can freely mutate it without affecting other tests."""
    return copy.deepcopy(_base_kb())


@pytest.fixture
def sample_resume_dict() -> dict:
    """A resume dict in the shape parse_filled_resume() / the renderers
    expect (as returned by parse_filled_resume or call_llm_fill_resume)."""
    return {
        "name": "Jane Q. Doe",
        "contact_line": "jane@example.com \u00b7 555-1234",
        "skills_heading": "CORE TECHNICAL SKILLS",
        "summary": "Great engineer\u2014does things.",
        "skills": [{"category": "Languages", "items": ["Python", "Go"]}],
        "work_experience": [
            {
                "title": "Software Engineer",
                "company": "Acme Corp",
                "date_range": "2020-01 - 2023-01",
                "team_context": "Team Widgets",
                "bullets": ["Did a thing.", "Did another thing."],
            },
            {
                "title": "Junior Engineer",
                "company": "Beta Inc",
                "date_range": "2018-01 - 2020-01",
                "team_context": "",
                "bullets": ["Maintained the beta system."],
            },
        ],
        "education": [
            {"degree": "BS in Computer Science", "institution": "State University", "date": "2015"}
        ],
    }


@pytest.fixture
def sample_cover_letter_dict() -> dict:
    return {"body": "Dear Hiring Manager,\n\nI am great\u2014truly.\n\nSincerely,\nJane"}


@pytest.fixture
def sample_job_fit_analysis_dict() -> dict:
    """A job-fit analysis dict in the shape validate_job_fit_analysis() /
    call_llm_analyze_fit() expect, with a single fit assessment (the
    common case: the job description didn't separate its qualifications
    into distinct lists)."""
    return {
        "fit_assessments": [
            {
                "list_label": "Overall Qualifications",
                "fit_percentage": 72,
                "assessment_summary": "Strong overlap in languages and testing background, but the posting wants cloud orchestration experience not reflected in the candidate data.",
                "matched_qualifications": ["Python", "Test automation"],
                "missing_qualifications": ["Kubernetes"],
            }
        ],
        "overall_summary": "Strong overlap in languages and testing background, but the posting wants cloud orchestration experience not reflected in the candidate data.",
        "upskill_resources": [
            {
                "missing_item": "Kubernetes",
                "resource_name": "Kubernetes Basics",
                "resource_type": "course",
                "resource_url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/",
                "is_free": True,
            }
        ],
    }


@pytest.fixture
def sample_job_fit_analysis_multi_dict() -> dict:
    """A job-fit analysis dict with more than one fit assessment: the
    case where the job description separates required vs. preferred
    qualifications into distinct lists."""
    return {
        "fit_assessments": [
            {
                "list_label": "Required Qualifications",
                "fit_percentage": 90,
                "assessment_summary": "Meets nearly every required qualification.",
                "matched_qualifications": ["Python", "REST APIs"],
                "missing_qualifications": ["PostgreSQL"],
            },
            {
                "list_label": "Preferred Qualifications",
                "fit_percentage": 40,
                "assessment_summary": "Missing most of the preferred cloud and orchestration skills.",
                "matched_qualifications": ["Test automation"],
                "missing_qualifications": ["Kubernetes", "Terraform"],
            },
        ],
        "overall_summary": "Strong match on required qualifications, but several preferred skills are missing.",
        "upskill_resources": [
            {
                "missing_item": "PostgreSQL",
                "resource_name": "PostgreSQL Tutorial",
                "resource_type": "documentation",
                "resource_url": "https://www.postgresql.org/docs/current/tutorial.html",
                "is_free": True,
            },
            {
                "missing_item": "Kubernetes",
                "resource_name": "Kubernetes Basics",
                "resource_type": "course",
                "resource_url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/",
                "is_free": True,
            },
            {
                "missing_item": "Terraform",
                "resource_name": "Terraform: Get Started",
                "resource_type": "tutorial",
                "resource_url": "https://developer.hashicorp.com/terraform/tutorials",
                "is_free": True,
            },
        ],
    }