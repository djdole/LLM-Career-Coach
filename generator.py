#!/usr/bin/env python3
"""
Generates baseline (no-specific-JD) SDE and SDET resumes, plus a cover
letter, from resume_data.json, in pdf/docx/txt/md/json formats.

Uses a self-hosted LiteLLM proxy (in front of Ollama, per that stack's
docker-compose.yml) rather than a paid hosted API, so this never spends
API credits and never fails due to account balance.

Tailoring a resume to a *specific* job posting is a different task (it
requires selecting/adapting content to a JD) and stays a separate,
manual, chat-based workflow -- see resume_data.json's own
generation_workflow_for_llm for that path. This script does not do that.

Usage:
    python generate.py
"""

import json
import os
import re
import sys
from pathlib import Path

import openai
import httpx
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

VARIANTS = ["SDE", "SDET"]

# Points at a self-hosted LiteLLM proxy instead of the Anthropic API. This
# stack runs LiteLLM in front of Ollama specifically as an OpenAI-compatible
# gateway (see docker-compose.yml), so we call LiteLLM directly rather than
# Open WebUI's own API layer. Avoids paid-API token usage entirely;
# generation runs against whatever local model Ollama has loaded.
#
# Required repo configuration (Settings -> Secrets and variables -> Actions):
#   Secrets:   LITELLM_BASE_URL   e.g. https://litellm.example.com
#                                 (points at the LiteLLM container's port,
#                                 ${LITELLM_PORT} in docker-compose.yml --
#                                 NOT Open WebUI's UI port)
#              LITELLM_API_KEY    same value as LITELLM_MASTER_KEY in that
#                                 stack's .env
#   Variables: LITELLM_MODEL      the model string LiteLLM proxies to, e.g.
#                                 "qwen3.6:latest" -- NOT sensitive,
#                                 so it's a repo Variable rather than a
#                                 Secret.
#   Optional:  OLLAMA_NUM_CTX     context window size override (default
#                                 16384) -- lower if your GPU can't hold
#                                 that much context for the model in use.
MODEL = os.environ.get("LITELLM_MODEL", "qwen3.6:latest")

# How long we wait for a *single* chat completion response before giving up
# on that attempt. There's no one correct default -- it depends on your
# model size, hardware, LITELLM_MAX_TOKENS, and OLLAMA_NUM_CTX -- so it's
# configurable via LITELLM_TIMEOUT rather than hardcoded. Keep it
# comfortably BELOW any reverse proxy's own read timeout in front of
# LiteLLM (proxy_read_timeout in nginx, etc.): if the proxy's timeout is
# shorter, IT kills the connection first, silently, and this timeout never
# gets the chance to produce the clearer error below. 550s is a safe
# default under nginx's commonly-recommended 600s.
LITELLM_TIMEOUT_SECONDS = float(os.environ.get("LITELLM_TIMEOUT", "550"))

# A single flat timeout number applies uniformly to the whole request,
# which isn't quite right for this use case: just reaching LiteLLM at all
# should fail fast (a few seconds) if it's unreachable, while actually
# *waiting on generated tokens* legitimately needs the full
# LITELLM_TIMEOUT_SECONDS budget for a local model generating up to
# LITELLM_MAX_TOKENS against OLLAMA_NUM_CTX of context. httpx.Timeout lets
# connect and read differ, so an unreachable/misconfigured proxy fails in
# ~10s with a clear connection error instead of burning the entire
# generation budget first only to fail for an unrelated reason. Passed to
# every client.chat.completions.create() call below in place of a bare
# `timeout=<seconds>`.
LLM_REQUEST_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=LITELLM_TIMEOUT_SECONDS,
    write=30.0,
    pool=LITELLM_TIMEOUT_SECONDS,
)

# How long Ollama keeps this model loaded in VRAM after a request, before
# unloading it. Left unset, a slow request (or a gap between the several
# calls a full run makes) risks the model unloading between calls, making
# the NEXT call pay a full model-load penalty on top of generation time.
# Explicit and generous relative to how long a full run takes end to end,
# so the model stays warm for the whole run rather than idling out mid-run.
# Ollama accepts a duration string ("30m", "1h") or seconds as a number.
LITELLM_KEEP_ALIVE = os.environ.get("LITELLM_KEEP_ALIVE", "30m")


def build_llm_client() -> openai.OpenAI:
    """
    Builds the single OpenAI-compatible client shared by every LLM call in
    a run. Reusing one client (and its underlying HTTP connection pool)
    instead of building a fresh one per call site avoids repeating the
    TCP/TLS handshake to LITELLM_BASE_URL for every one of the ~5-14
    sequential requests a full run makes.
    """
    base_url = os.environ.get("LITELLM_BASE_URL")
    api_key = os.environ.get("LITELLM_API_KEY")
    if not base_url or not api_key:
        print("LITELLM_BASE_URL and/or LITELLM_API_KEY are not set.", file=sys.stderr)
        sys.exit(1)
    return openai.OpenAI(base_url=base_url.rstrip("/") + "/v1", api_key=api_key)

# Maps the knowledge base's snake_case skill category keys to display
# labels matching the existing hand-written resumes' style, fed to the
# model as already-formatted so it only has to copy them, not invent
# formatting for them.
CATEGORY_LABELS = {
    "languages": "Languages",
    "apis_and_web_servers": "APIs & Web Servers",
    "test_automation_frameworks": "Test Automation Frameworks",
    "frontend_and_mobile_testing": "Frontend & Mobile Testing",
    "unit_integration_testing": "Unit & Integration Testing",
    "test_management_and_planning": "Test Management & Planning",
    "performance_testing": "Performance Testing",
    "ci_cd_and_devops": "CI/CD & DevOps",
    "databases_and_query_languages": "Databases & Query Languages",
    "version_control": "Version Control",
    "debugging_and_diagnostics": "Debugging & Diagnostics",
    "virtualization_and_infra": "Virtualization & Infra",
    "developer_tools_and_ides": "Developer Tools & IDEs",
    "ai_and_automation_tooling": "AI & Automation Tooling",
    "methodologies": "Methodologies",
    "collaboration_and_docs": "Collaboration & Docs",
    "monitoring_and_incident_mgmt": "Monitoring / Incident Mgmt",
}

SKILLS_HEADING_BY_VARIANT = {"SDE": "CORE TECHNICAL SKILLS", "SDET": "CORE SDET SKILLS"}
BULLET_CHAR = "\u25cf"  # "●", matches the existing hand-written resumes' style
EM_DASH = "\u2014"


def compute_job_column_widths(work_experience: list, body_pt: float, total_pt: float, min_title_pt: float = 130) -> tuple:
    """
    Sizes the title/employer/date columns from the ACTUAL text in this
    resume at this font size, instead of fixed percentages -- fixed splits
    silently overflow whenever a company name (e.g. 'Cosworth Tech Inc. /
    MAHLE Powertrain LLC') is longer than whatever guess produced the
    split, forcing it to wrap mid-name. Measured with reportlab's
    Helvetica-Bold metrics as a stand-in font for both PDF and DOCX --
    DOCX's actual font differs slightly, but widths are close enough that
    this still prevents wrapping in practice.

    Employer and date each get exactly what their longest actual value
    needs (plus a small buffer); title gets whatever's left, floored at
    min_title_pt so a long employer name can't crush the title column to
    nothing.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth
    pad = 8
    employer_pt = max(stringWidth(j["company"], "Helvetica-Bold", body_pt) for j in work_experience) + pad
    date_pt = max(stringWidth(j["date_range"], "Helvetica-Bold", body_pt) for j in work_experience) + pad
    title_pt = max(total_pt - employer_pt - date_pt, min_title_pt)
    return title_pt, employer_pt, date_pt


def strip_em_dashes(text: str) -> str:
    """Belt-and-suspenders fallback behind the never_use_em_dash rule the
    model is given -- not a substitute for the model actually following it."""
    return text.replace(EM_DASH, ",")


# --- Prompt construction -------------------------------------------------

def build_baseline_context(kb: dict, variant: str) -> dict:
    """
    Trims the full knowledge base down to only what the BASELINE (no-JD)
    path needs for ONE variant (SDE or SDET), per generation_workflow_for_llm
    step 0's fallback.

    Trimming matters for two reasons: (1) token budget -- the full KB is
    ~10k tokens alone, likely exceeding a local model's context window
    unless num_ctx is raised (see call_llm); (2) signal-to-noise -- the
    full KB includes JD-tailoring-only fields (bullet variants, per-bullet
    themes/skills tags, the other variant's title, cover letter JD-specific
    building blocks) that have shown up verbatim in bad output before this
    trimming existed -- fewer irrelevant JSON shapes nearby means less for
    a smaller model to latch onto instead of the requested schema.

    Skill category labels are pre-formatted here (see CATEGORY_LABELS) so
    the model only has to copy them, not invent formatting.
    """
    rules = kb["meta"]["output_rules"]
    summary = kb["summary_variants"].get(variant) or kb["summary_variants"]["SDE"]
    skills = [
        {"category": CATEGORY_LABELS.get(k, k.replace("_", " ").title()), "items": v}
        for k, v in kb["skills"].items() if isinstance(v, list)
    ]
    work_experience = [
        {
            "title": job["title_by_variant"].get(variant) or next(iter(job["title_by_variant"].values())),
            "company": job["company"],
            "team_context": job.get("team_context", ""),
            "date_range": f"{job['start_date']} - {job['end_date']}",
            "bullets": [b["text"] for b in job["bullets"] if not b["id"].endswith(("_alt", "_variant"))],
        }
        for job in kb["work_experience"]
    ]
    # The raw KB uses the key "graduation date" (with a space); the output
    # schema calls it "date". Renaming it here -- rather than relying on the
    # model to perform that rename -- is what actually fixed education[]
    # entries coming back without a date at all.
    education = [
        {"degree": ed["degree"], "institution": ed["institution"], "date": ed["graduation date"]}
        for ed in kb["education"]
    ]
    return {
        "output_rules": {
            "never_fabricate": rules["never_fabricate"],
            "never_use_em_dash": rules["never_use_em_dash"],
        },
        "personal_info": kb["personal_info"],
        "education": education,
        "summary": summary,
        "skills_heading": SKILLS_HEADING_BY_VARIANT[variant],
        "skills": skills,
        "work_experience": work_experience,
        "cover_letter_generic_template": kb["cover_letter_building_blocks"]["generic_fallback_template"],
    }


def build_resume_fill_prompt(kb: dict, variant: str, template_text: str) -> str:
    """Fills RESUME_TEMPLATE using the trimmed baseline context -- same
    spirit as build_readme_system_prompt, adapted for the resume's
    pipe-delimited, code-parsed structure."""
    context = build_baseline_context(kb, variant)
    return (
        f"You are filling in a plain-text resume TEMPLATE for a BASELINE "
        f"{variant} resume (no specific job description provided), using "
        "the candidate data below. Preserve the template's exact structure "
        "and formatting -- section header text (SUMMARY, WORK EXPERIENCE, "
        "EDUCATION), the bullet character, and especially the exact ' | ' "
        "(space-pipe-space) delimiters on the job-header and education "
        "lines, since those are parsed by code afterward and must be exact. "
        "Only replace the {{PLACEHOLDER}} tokens with real content. Follow "
        "the template's HTML-comment instructions for repeating blocks (one "
        "skills line per category, one Experience block per job, one "
        "Education line per entry). Omit the team-context line entirely "
        "for a job with no team_context. Follow output_rules exactly, "
        "especially never_fabricate and never_use_em_dash.\n\n"
        "=== TEMPLATE ===\n" + template_text + "\n\n"
        "=== CANDIDATE DATA (read for content only; do not include field "
        "names like team_context or date_range in your answer) ===\n"
        + json.dumps(context, indent=2)
        + "\n\n=== YOUR TASK ===\n"
        "Output ONLY the final, completed document -- no commentary, no "
        "markdown code fences around the whole thing, no leftover "
        "{{PLACEHOLDER}} tokens or HTML comments from the template."
    )


def parse_filled_resume(text: str) -> dict:
    """Parses a filled RESUME_TEMPLATE (see build_resume_fill_prompt) back
    into the structured dict the existing renderers expect. Raises
    ValueError on any structural mismatch, which the caller uses to
    trigger a corrective retry rather than crash deep inside rendering."""
    lines = text.strip("\n").split("\n")
    i = 0

    def skip_blank():
        nonlocal i
        while i < len(lines) and lines[i].strip() == "":
            i += 1

    if len(lines) < 2:
        raise ValueError("Output too short to contain name/contact lines.")
    name = lines[i].strip(); i += 1
    contact_line = lines[i].strip(); i += 1

    skip_blank()
    if i >= len(lines) or lines[i].strip() != "SUMMARY":
        raise ValueError(f"Expected 'SUMMARY' header, got: {lines[i].strip() if i < len(lines) else 'EOF'!r}")
    i += 1
    skip_blank()
    summary_lines = []
    while i < len(lines) and lines[i].strip() != "":
        summary_lines.append(lines[i].strip())
        i += 1
    summary = " ".join(summary_lines)

    skip_blank()
    if i >= len(lines):
        raise ValueError("Output ended before a skills_heading line.")
    skills_heading = lines[i].strip(); i += 1
    skills = []
    while i < len(lines) and lines[i].strip() and lines[i].strip() != "WORK EXPERIENCE":
        m = re.match(r"^(.+?):\s*(.+)$", lines[i].strip())
        if not m:
            raise ValueError(f"Could not parse skills line: {lines[i]!r}")
        category, items_str = m.groups()
        skills.append({"category": category, "items": [x.strip() for x in items_str.split(",") if x.strip()]})
        i += 1
    skip_blank()
    if i >= len(lines) or lines[i].strip() != "WORK EXPERIENCE":
        raise ValueError(f"Expected 'WORK EXPERIENCE' header, got: {lines[i].strip() if i < len(lines) else 'EOF'!r}")
    i += 1
    skip_blank()

    work_experience = []
    while i < len(lines) and lines[i].strip() and lines[i].strip() != "EDUCATION":
        header = lines[i].strip(); i += 1
        parts = [p.strip() for p in header.split("|")]
        if len(parts) != 3:
            raise ValueError(f"Job header line not in 'Title | Company | Dates' shape: {header!r}")
        title, company, date_range = parts
        team_context = ""
        if i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(BULLET_CHAR):
            team_context = lines[i].strip()
            i += 1
        bullets = []
        while i < len(lines) and lines[i].strip().startswith(BULLET_CHAR):
            bullets.append(lines[i].strip()[1:].strip())
            i += 1
        if not bullets:
            raise ValueError(f"Job '{title}' has no bullets.")
        work_experience.append({"title": title, "company": company, "date_range": date_range,
                                 "team_context": team_context, "bullets": bullets})
        skip_blank()

    if i >= len(lines) or lines[i].strip() != "EDUCATION":
        raise ValueError(f"Expected 'EDUCATION' header, got: {lines[i].strip() if i < len(lines) else 'EOF'!r}")
    i += 1
    skip_blank()
    education = []
    while i < len(lines) and lines[i].strip():
        parts = [p.strip() for p in lines[i].split("|")]
        if len(parts) != 3:
            raise ValueError(f"Education line not in 'Degree | Institution | Date' shape: {lines[i]!r}")
        degree, institution, date = parts
        education.append({"degree": degree, "institution": institution, "date": date})
        i += 1

    return {"name": name, "contact_line": contact_line, "skills_heading": skills_heading,
            "summary": summary, "skills": skills, "work_experience": work_experience, "education": education}


def call_llm_fill_resume(client: openai.OpenAI, kb: dict, variant: str, template_text: str) -> dict:
    system_prompt = build_resume_fill_prompt(kb, variant, template_text)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Fill in the template now."},
    ]
    max_output_tokens = int(os.environ.get("LITELLM_MAX_TOKENS", "10000"))
    num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", "16384"))
    expected_job_count = len(kb["work_experience"])

    est_input_tokens = len(system_prompt) // 4
    print(f"[{variant}] Resume prompt size estimate: ~{est_input_tokens} input tokens.", file=sys.stderr)

    last_error = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL, max_tokens=max_output_tokens, temperature=0.3, timeout=LLM_REQUEST_TIMEOUT,
                extra_body={"options": {"num_ctx": num_ctx}, "keep_alive": LITELLM_KEEP_ALIVE}, messages=messages,
            )
        except openai.APIConnectionError as e:
            print(f"[{variant}] Could not reach LiteLLM at {client.base_url}: {e}", file=sys.stderr)
            sys.exit(1)
        except openai.APIStatusError as e:
            print(f"[{variant}] LiteLLM returned an error (HTTP {e.status_code}): {e.message}", file=sys.stderr)
            sys.exit(1)

        raw = response.choices[0].message.content or ""
        text = extract_markdown(raw)
        try:
            parsed = parse_filled_resume(text)
            if len(parsed["work_experience"]) != expected_job_count:
                raise ValueError(f"Got {len(parsed['work_experience'])} jobs, expected {expected_job_count}.")
            return parsed
        except ValueError as e:
            last_error = e
            print(f"[{variant}] Attempt {attempt + 1}: malformed resume output ({e}). Raw:\n{raw}\n", file=sys.stderr)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"That response was invalid: {e}. Output ONLY the corrected, complete filled-in template, following all the same rules.",
            })

    print(f"[{variant}] Model failed to produce a valid filled resume after 2 attempts. Last error: {last_error}", file=sys.stderr)
    sys.exit(1)


REQUIRED_COVER_LETTER_KEYS = {"body"}


def extract_json_object(raw: str) -> str:
    """Pulls the first balanced {...} block out of a string that may
    contain markdown fences and/or prose before/after it."""
    start = raw.find("{")
    if start == -1:
        raise ValueError("No '{' found in model output.")
    depth = 0
    for i, ch in enumerate(raw[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]
    raise ValueError("No balanced closing '}' found in model output.")


def build_cover_letter_prompt(kb: dict, variant: str) -> str:
    context = build_baseline_context(kb, variant)
    return (
        "You are producing a BASELINE cover letter (no specific job "
        "description provided), for the candidate described below. Use "
        "cover_letter_generic_template as the cover letter (lightly adapt "
        "it, keep 'Dear Hiring Manager'). Follow output_rules exactly, "
        "especially never_fabricate and never_use_em_dash.\n\n"
        "=== CANDIDATE DATA ===\n" + json.dumps({
            "output_rules": context["output_rules"],
            "cover_letter_generic_template": context["cover_letter_generic_template"],
        }, indent=2)
        + "\n\n=== YOUR TASK ===\n"
        'Respond with ONLY a JSON object of the shape {"body": "full cover '
        'letter text, paragraphs separated by a blank line"}. No prose '
        "before or after it, no markdown code fences. Your entire response "
        "must start with { and end with }."
    )


def call_llm_cover_letter(client: openai.OpenAI, kb: dict, variant: str) -> dict:
    system_prompt = build_cover_letter_prompt(kb, variant)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the cover letter JSON now."},
    ]
    max_output_tokens = int(os.environ.get("LITELLM_MAX_TOKENS", "10000"))
    num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", "16384"))

    last_error = None
    for attempt in range(2):
        try:
            try:
                response = client.chat.completions.create(
                    model=MODEL, max_tokens=max_output_tokens, temperature=0.3, timeout=LLM_REQUEST_TIMEOUT,
                    response_format={"type": "json_object"},
                    extra_body={"options": {"num_ctx": num_ctx}, "keep_alive": LITELLM_KEEP_ALIVE}, messages=messages,
                )
            except openai.BadRequestError:
                response = client.chat.completions.create(
                    model=MODEL, max_tokens=max_output_tokens, temperature=0.3, timeout=LLM_REQUEST_TIMEOUT,
                    extra_body={"options": {"num_ctx": num_ctx}, "keep_alive": LITELLM_KEEP_ALIVE}, messages=messages,
                )
        except openai.APIConnectionError as e:
            print(f"[{variant}] Could not reach LiteLLM at {client.base_url}: {e}", file=sys.stderr)
            sys.exit(1)
        except openai.APIStatusError as e:
            print(f"[{variant}] LiteLLM returned an error (HTTP {e.status_code}): {e.message}", file=sys.stderr)
            sys.exit(1)

        raw = response.choices[0].message.content or ""
        try:
            cl = json.loads(extract_json_object(raw))
            if REQUIRED_COVER_LETTER_KEYS - set(cl.keys()):
                raise ValueError("cover letter is missing required key: 'body'")
            return cl
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            print(f"[{variant}] Attempt {attempt + 1}: malformed cover letter output ({e}). Raw:\n{raw}\n", file=sys.stderr)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"That response was invalid: {e}. Respond again with ONLY the JSON object described earlier.",
            })

    print(f"[{variant}] Model failed to produce a valid cover letter after 2 attempts. Last error: {last_error}", file=sys.stderr)
    sys.exit(1)


# --- Plain text / Markdown -------------------------------------------------

def render_resume_txt(r: dict) -> str:
    lines = [r["name"], r["contact_line"], "", "SUMMARY", r["summary"], "", r["skills_heading"]]
    for group in r["skills"]:
        lines.append(f"{group['category']}: {', '.join(group['items'])}")
    lines += ["", "WORK EXPERIENCE"]
    for job in r["work_experience"]:
        lines.append(f"{job['title']} {job['date_range']}")
        line2 = job["company"] + (f" \u00b7 {job['team_context']}" if job.get("team_context") else "")
        lines.append(line2)
        for b in job["bullets"]:
            lines.append(f"{BULLET_CHAR} {b}")
        lines.append("")
    lines.append("EDUCATION")
    for ed in r["education"]:
        lines.append(f"{ed['degree']}")
        lines.append(f"{ed['institution']} ({ed['date']})")
    return strip_em_dashes("\n".join(lines))


def render_resume_md(r: dict) -> str:
    lines = [f"# {r['name']}", r["contact_line"], "", "## Summary", r["summary"], "", f"## {r['skills_heading'].title()}"]
    for group in r["skills"]:
        lines.append(f"- **{group['category']}:** {', '.join(group['items'])}")
    lines += ["", "## Work Experience"]
    for job in r["work_experience"]:
        lines.append(f"### {job['title']} | {job['date_range']}")
        line2 = job["company"] + (f" \u00b7 {job['team_context']}" if job.get("team_context") else "")
        lines.append(f"*{line2}*")
        for b in job["bullets"]:
            lines.append(f"- {b}")
        lines.append("")
    lines.append("## Education")
    for ed in r["education"]:
        lines.append(f"- {ed['degree']}, {ed['institution']} ({ed['date']})")
    return strip_em_dashes("\n".join(lines))


def render_cover_letter_txt(cl: dict) -> str:
    return strip_em_dashes(cl["body"])


def render_cover_letter_md(cl: dict) -> str:
    return strip_em_dashes(cl["body"])


# --- DOCX --------------------------------------------------------------

ACCENT_RGB = RGBColor(0x1F, 0x38, 0x64)  # navy, sampled from the existing hand-written resumes


def _tight(paragraph, space_after=2, space_before=0):
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.space_before = Pt(space_before)
    return paragraph


def render_resume_docx(r: dict, path: Path, body_pt: float = 10.5) -> None:
    doc = Document()
    doc.styles["Normal"].font.size = Pt(body_pt)
    for section in doc.sections:
        section.top_margin = Pt(40)
        section.bottom_margin = Pt(40)
        section.left_margin = Pt(54)
        section.right_margin = Pt(54)

    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = name_p.add_run(r["name"])
    run.bold = True
    run.font.size = Pt(body_pt + 9)
    run.font.color.rgb = ACCENT_RGB
    _tight(name_p, space_after=2)

    contact_p = doc.add_paragraph()
    contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    crun = contact_p.add_run(r["contact_line"])
    crun.font.size = Pt(body_pt - 1)
    _tight(contact_p, space_after=10)

    def add_heading(text):
        h = doc.add_paragraph()
        hr = h.add_run(text)
        hr.bold = True
        hr.font.size = Pt(body_pt + 1.5)
        hr.font.color.rgb = ACCENT_RGB
        _tight(h, space_after=1, space_before=10)
        pPr = h._p.get_or_add_pPr()
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        pBdr = pPr.makeelement(f"{ns}pBdr")
        bottom = pPr.makeelement(f"{ns}bottom")
        bottom.set(f"{ns}val", "single")
        bottom.set(f"{ns}sz", "6")
        bottom.set(f"{ns}color", "1F3864")
        pBdr.append(bottom)
        pPr.append(pBdr)
        return h

    add_heading("SUMMARY")
    _tight(doc.add_paragraph(strip_em_dashes(r["summary"])), space_after=8)

    add_heading(r["skills_heading"])
    for group in r["skills"]:
        p = doc.add_paragraph()
        p.add_run(f"{group['category']}: ").bold = True
        p.add_run(strip_em_dashes(", ".join(group["items"])))
        _tight(p, space_after=2)

    add_heading("WORK EXPERIENCE")
    docx_usable_pt = 612 - 2 * 54  # page width minus the left/right margins set above (Pt(54) each)
    title_col, employer_col, date_col = compute_job_column_widths(r["work_experience"], body_pt, docx_usable_pt)
    for job in r["work_experience"]:
        table = doc.add_table(rows=1, cols=3)
        table.autofit = True
        table.columns[0].width = Pt(title_col)
        table.columns[1].width = Pt(employer_col)
        table.columns[2].width = Pt(date_col)
        left, middle, right = table.rows[0].cells
        lp = left.paragraphs[0]
        lr = lp.add_run(job["title"])
        lr.bold = True
        _tight(lp, space_after=0)
        mp = middle.paragraphs[0]
        mr = mp.add_run(job["company"])
        mr.bold = True
        _tight(mp, space_after=0)
        rp = right.paragraphs[0]
        rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        rr = rp.add_run(job["date_range"])
        rr.bold = True
        _tight(rp, space_after=0)

        if job.get("team_context"):
            cp = doc.add_paragraph()
            cr = cp.add_run(job["team_context"])
            cr.italic = True
            cr.font.color.rgb = ACCENT_RGB
            cr.font.size = Pt(body_pt - 0.5)
            _tight(cp, space_after=3)

        for i, b in enumerate(job["bullets"]):
            bp = doc.add_paragraph(style="List Bullet")
            bp.add_run(strip_em_dashes(b))
            is_last = i == len(job["bullets"]) - 1
            _tight(bp, space_after=6 if is_last else 1)

    add_heading("EDUCATION")
    for ed in r["education"]:
        _tight(doc.add_paragraph(f"{ed['degree']}, {ed['institution']} ({ed['date']})"), space_after=1)

    doc.save(path)


def render_cover_letter_docx(cl: dict, path: Path) -> None:
    doc = Document()
    for para in strip_em_dashes(cl["body"]).split("\n\n"):
        doc.add_paragraph(para)
    doc.save(path)


# --- PDF (with page-fit: retries at smaller sizes until <=2 pages) -----

ACCENT_COLOR = colors.HexColor("#1F3864")  # sampled from the existing hand-written resumes

# Each tier: (body_pt, leading, bullet_space_after, top/bottom margin inches, name_pt, heading_pt)
PDF_TIERS = [
    (10.5, 13, 2, 0.55, 21, 12.5),
    (10, 12.5, 2, 0.5, 20, 12),
    (9.5, 12, 1.5, 0.45, 19, 11.5),
    (9, 11.5, 1, 0.4, 18, 11),
]


def _build_resume_story(r: dict, tier) -> list:
    body_pt, leading, bullet_space, _, name_pt, heading_pt = tier
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=body_pt, leading=leading, spaceAfter=3)
    bullet_style = ParagraphStyle("Bullet", parent=body_style, spaceAfter=bullet_space, leftIndent=10)
    company_style = ParagraphStyle("Company", parent=body_style, textColor=ACCENT_COLOR, fontName="Helvetica-Oblique", spaceAfter=3)
    heading_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=heading_pt, textColor=ACCENT_COLOR,
                                    spaceBefore=heading_pt * 0.9, spaceAfter=2, fontName="Helvetica-Bold")
    name_style = ParagraphStyle("Name", parent=styles["Title"], fontSize=name_pt, textColor=ACCENT_COLOR, alignment=TA_CENTER, spaceAfter=2)
    contact_style = ParagraphStyle("Contact", parent=body_style, alignment=TA_CENTER, spaceAfter=10, fontSize=body_pt - 0.5)
    title_style = ParagraphStyle("JobTitle", parent=body_style, fontName="Helvetica-Bold", spaceAfter=0)
    employer_style = ParagraphStyle("JobEmployer", parent=body_style, fontName="Helvetica-Bold", spaceAfter=0)
    date_style = ParagraphStyle("JobDate", parent=title_style, alignment=2)

    def heading(text):
        return [Paragraph(text, heading_style), HRFlowable(width="100%", thickness=0.75, color=ACCENT_COLOR, spaceAfter=4)]

    story = [Paragraph(r["name"], name_style), Paragraph(r["contact_line"], contact_style)]
    story += heading("SUMMARY")
    story.append(Paragraph(strip_em_dashes(r["summary"]), body_style))
    story += heading(r["skills_heading"])
    for group in r["skills"]:
        story.append(Paragraph(f"<b>{group['category']}:</b> {strip_em_dashes(', '.join(group['items']))}", body_style))
    story += heading("WORK EXPERIENCE")
    usable_width = LETTER[0] - 2 * 0.7 * inch
    title_col, employer_col, date_col = compute_job_column_widths(r["work_experience"], body_pt, usable_width)
    for job in r["work_experience"]:
        row = Table(
            [[Paragraph(job["title"], title_style), Paragraph(job["company"], employer_style), Paragraph(job["date_range"], date_style)]],
            colWidths=[title_col, employer_col, date_col],
        )
        row.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(row)
        if job.get("team_context"):
            story.append(Paragraph(job["team_context"], company_style))
        for b in job["bullets"]:
            story.append(Paragraph(f"{BULLET_CHAR} {strip_em_dashes(b)}", bullet_style))
    story += heading("EDUCATION")
    for ed in r["education"]:
        story.append(Paragraph(f"{ed['degree']}, {ed['institution']} ({ed['date']})", body_style))
    return story


def render_resume_pdf(r: dict, path: Path, max_pages: int = 2):
    """Tries progressively smaller tiers until the rendered PDF fits within
    max_pages, or the smallest tier is reached. Returns (pages, body_pt)."""
    for tier in PDF_TIERS:
        _, _, _, margin_in, _, _ = tier
        doc = SimpleDocTemplate(
            str(path), pagesize=LETTER,
            leftMargin=0.7 * inch, rightMargin=0.7 * inch,
            topMargin=margin_in * inch, bottomMargin=margin_in * inch,
        )
        doc.build(_build_resume_story(r, tier))
        if doc.page <= max_pages:
            return doc.page, tier[0]
    return doc.page, tier[0]


def render_cover_letter_pdf(cl: dict, path: Path) -> None:
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=11, leading=15, spaceAfter=10)
    doc = SimpleDocTemplate(str(path), pagesize=LETTER,
                             leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                             topMargin=0.9 * inch, bottomMargin=0.9 * inch)
    story = [Paragraph(p.replace("\n", "<br/>"), body_style) for p in strip_em_dashes(cl["body"]).split("\n\n")]
    doc.build(story)


# --- GitHub profile README (separate, template-driven LLM call) -------

README_REQUIRED_HEADERS = ["## \U0001f6e0\ufe0f Skills", "## \U0001f4bc Experience", "## \U0001f393 Education", "## \u2728 Career Highlights"]


def build_readme_context(kb: dict) -> dict:
    """Trimmed context for the README call -- same spirit as
    build_baseline_context, but variant-agnostic (the profile README isn't
    SDE- or SDET-specific) and includes the extra fields the resume schema
    doesn't carry: location, each education entry's field of study, and
    the career_narrative_notes differentiators list."""
    rules = kb["meta"]["output_rules"]
    skills = [
        {"category": CATEGORY_LABELS.get(k, k.replace("_", " ").title()), "items": v}
        for k, v in kb["skills"].items() if isinstance(v, list)
    ]
    work_experience = [
        {
            "title": job["title_by_variant"].get("SDE") or next(iter(job["title_by_variant"].values())),
            "company": job["company"],
            "team_context": job.get("team_context", ""),
            "date_range": f"{job['start_date']} - {job['end_date']}",
            "bullets": [b["text"] for b in job["bullets"] if not b["id"].endswith(("_alt", "_variant"))],
        }
        for job in kb["work_experience"]
    ]
    education = [
        {"degree": ed["degree"], "institution": ed["institution"],
         "field_of_study": ed.get("field of study", ""), "graduation_date": ed["graduation date"]}
        for ed in kb["education"]
    ]
    return {
        "output_rules": {"never_fabricate": rules["never_fabricate"], "never_use_em_dash": rules["never_use_em_dash"]},
        "personal_info": kb["personal_info"],
        "summary": kb["summary_variants"]["SDE"],
        "skills": skills,
        "work_experience": work_experience,
        "education": education,
        "career_highlights": kb.get("career_narrative_notes", {}).get("strongest_differentiators", []),
    }


def build_readme_system_prompt(kb: dict, template_text: str) -> str:
    context = build_readme_context(kb)
    return (
        "You are filling in a Markdown TEMPLATE for a GitHub profile README, "
        "using the candidate data below. Preserve the template's exact "
        "structure, Markdown syntax, emoji, and formatting (bold, headers, "
        "horizontal rules, bullet style) -- only replace the {{PLACEHOLDER}} "
        "tokens with real content. Follow the template's HTML-comment "
        "instructions for repeating blocks (one skills line per category, "
        "one Experience block per job, one Education block per entry, one "
        "bullet per career highlight). Reproduce career_highlights items "
        "VERBATIM -- do not reword, shorten, combine, or reorder them. Omit "
        "the '* team context *' line entirely for a job with no "
        "team_context. Follow output_rules exactly, especially "
        "never_fabricate and never_use_em_dash.\n\n"
        "=== TEMPLATE ===\n" + template_text + "\n\n"
        "=== CANDIDATE DATA (read for content only; do not include field "
        "names like team_context or graduation_date in your answer) ===\n"
        + json.dumps(context, indent=2)
        + "\n\n=== YOUR TASK ===\n"
        "Output ONLY the final, completed Markdown document -- no commentary, "
        "no markdown code fences around the whole thing, no leftover "
        "{{PLACEHOLDER}} tokens or HTML comments from the template. Start "
        "your response with the first line of the filled-in template."
    )


def extract_markdown(raw: str) -> str:
    """Strips a single wrapping ```...``` fence if the model put one around
    the whole document, despite being told not to."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


def validate_readme(md: str, expected_job_count: int) -> None:
    if not md.startswith("# "):
        raise ValueError("README does not start with a top-level '# ' heading.")
    missing = [h for h in README_REQUIRED_HEADERS if h not in md]
    if missing:
        raise ValueError(f"README is missing required section(s): {missing}")
    if "{{" in md or "}}" in md:
        raise ValueError("README still contains unfilled {{placeholder}} tokens.")
    if EM_DASH in md:
        raise ValueError("README contains an em dash, which violates never_use_em_dash.")
    job_headers = len(re.findall(r"^### ", md, flags=re.MULTILINE))
    if job_headers != expected_job_count:
        raise ValueError(f"README has {job_headers} job entries, expected {expected_job_count} (a job may have been dropped or duplicated).")


def call_llm_readme(client: openai.OpenAI, kb: dict, template_text: str) -> str:
    system_prompt = build_readme_system_prompt(kb, template_text)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Fill in the template now."},
    ]
    max_output_tokens = int(os.environ.get("LITELLM_MAX_TOKENS", "10000"))
    num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", "16384"))
    expected_job_count = len(kb["work_experience"])

    est_input_tokens = len(system_prompt) // 4
    print(f"[README] Prompt size estimate: ~{est_input_tokens} input tokens.", file=sys.stderr)

    last_error = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL, max_tokens=max_output_tokens, temperature=0.3, timeout=LLM_REQUEST_TIMEOUT,
                extra_body={"options": {"num_ctx": num_ctx}, "keep_alive": LITELLM_KEEP_ALIVE}, messages=messages,
            )
        except openai.APIConnectionError as e:
            print(f"[README] Could not reach LiteLLM at {client.base_url}: {e}", file=sys.stderr)
            sys.exit(1)
        except openai.APIStatusError as e:
            print(f"[README] LiteLLM returned an error (HTTP {e.status_code}): {e.message}", file=sys.stderr)
            sys.exit(1)

        raw = response.choices[0].message.content or ""
        md = extract_markdown(raw)
        try:
            validate_readme(md, expected_job_count)
            return md
        except ValueError as e:
            last_error = e
            print(f"[README] Attempt {attempt + 1}: malformed output ({e}). Raw:\n{raw}\n", file=sys.stderr)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"That response was invalid: {e}. Output ONLY the corrected, complete filled-in template, following all the same rules.",
            })

    print(f"[README] Model failed to produce a valid README after 2 attempts. Last error: {last_error}", file=sys.stderr)
    sys.exit(1)


def load_file_location_settings() -> dict:
    return {
        "OUTPUT_FOLDER": os.environ.get("OUTPUT_FOLDER", "generated"),
        "KNOWLEDGE_BASE": os.environ.get("KNOWLEDGE_BASE", "resume_data.json"),
        "README_TEMPLATE": os.environ.get("README_TEMPLATE", "README.template.md"),
        "README_OUTPUT": os.environ.get("README_OUTPUT", "README.md"),
        "RESUME_TEMPLATE": os.environ.get("RESUME_TEMPLATE", "RESUME.template.md"),
        "RESUME_NAMING_TEMPLATE": os.environ.get(
            "RESUME_NAMING_TEMPLATE", "{FirstName} {LastName} Resume ({JobAcronym}).{Extension}"
        ),
        "COVERLETTER_NAMING_TEMPLATE": os.environ.get(
            "COVERLETTER_NAMING_TEMPLATE", "{FirstName} {LastName} Cover Letter ({JobAcronym}).{Extension}"
        ),
    }


def render_filename(naming_template: str, full_name: str, job_acronym: str, extension: str) -> str:
    """Fills a naming template like '{FirstName} {LastName} Resume
    ({JobAcronym}).{Extension}' using the candidate's full name (first and
    last token; a middle name/initial is dropped, matching the existing
    file-naming convention) and the given variant/extension."""
    parts = full_name.split()
    first_name, last_name = parts[0], parts[-1]
    return naming_template.format(FirstName=first_name, LastName=last_name, JobAcronym=job_acronym, Extension=extension)


def main():
    s = load_file_location_settings()
    kb = json.loads(Path(s["KNOWLEDGE_BASE"]).read_text(encoding="utf-8"))
    out_dir = Path(s["OUTPUT_FOLDER"])
    out_dir.mkdir(parents=True, exist_ok=True)
    full_name = kb["personal_info"]["full_name"]
    resume_template_text = Path(s["RESUME_TEMPLATE"]).read_text(encoding="utf-8")

    # One client (and its underlying connection pool) for every LLM call
    # in this run, rather than a fresh one per call site.
    client = build_llm_client()

    for variant in VARIANTS:
        r = call_llm_fill_resume(client, kb, variant, resume_template_text)
        cl = call_llm_cover_letter(client, kb, variant)

        def resume_path(ext: str) -> Path:
            return out_dir / render_filename(s["RESUME_NAMING_TEMPLATE"], full_name, variant, ext)

        def cl_path(ext: str) -> Path:
            return out_dir / render_filename(s["COVERLETTER_NAMING_TEMPLATE"], full_name, variant, ext)

        resume_path("json").write_text(json.dumps(r, indent=2), encoding="utf-8")
        resume_path("txt").write_text(render_resume_txt(r), encoding="utf-8")
        resume_path("md").write_text(render_resume_md(r), encoding="utf-8")

        pages, body_pt = render_resume_pdf(r, resume_path("pdf"))
        if pages > 2:
            print(f"WARNING: {variant} resume rendered at {pages} pages even at the smallest tier ({body_pt}pt).")
        else:
            print(f"{variant} resume: {pages} page(s) at {body_pt}pt.")
        render_resume_docx(r, resume_path("docx"), body_pt=body_pt)

        cl_path("txt").write_text(render_cover_letter_txt(cl), encoding="utf-8")
        render_cover_letter_docx(cl, cl_path("docx"))
        render_cover_letter_pdf(cl, cl_path("pdf"))

    # Separate LLM call, template-driven: fills README_TEMPLATE using
    # resume_data.json, rather than reusing the resume call above.
    template_text = Path(s["README_TEMPLATE"]).read_text(encoding="utf-8")
    readme_markdown = call_llm_readme(client, kb, template_text)
    readme_path = Path(s["README_OUTPUT"])
    readme_path.write_text(readme_markdown, encoding="utf-8")
    print(f"Wrote GitHub profile README to {readme_path}")

    print(f"Wrote {len(VARIANTS)} resume variant(s) (5 formats) + cover letters (3 formats) to {out_dir}/")


if __name__ == "__main__":
    main()