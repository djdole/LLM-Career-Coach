#!/usr/bin/env python3
"""
Generates baseline (no-specific-JD) resume + cover letter outputs from
data/resume_data.json, in pdf/docx/txt/md/json formats.

Uses a self-hosted LiteLLM proxy (in front of Ollama, via its OpenAI-
compatible API) rather than a paid hosted API, so this never spends API
credits and never fails due to account balance.

This covers the automated, on-push path only: regenerating the generic
resume/cover letter/README content whenever the knowledge base changes
(new skill, new bullet, etc). Tailoring a resume to a *specific* job
posting is a separate, manual, per-application workflow done in chat
(see data/resume_data.json -> generation_workflow_for_llm step 0), not
something this script does.

Usage:
    python scripts/generate_resumes.py --data data/resume_data.json --out generated/
"""

import argparse
import json
import re
import sys
from pathlib import Path

import os
import openai
from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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
#                                 stack's .env -- this is the bearer token
#                                 LiteLLM already expects on its API
#   Variables: LITELLM_MODEL      the model string LiteLLM proxies to, e.g.
#                                 "ollama/llama3.1:70b" (matches the
#                                 --model argument in the litellm service's
#                                 `command:` in docker-compose.yml) -- NOT
#                                 sensitive, so it's a repo Variable rather
#                                 than a Secret.
#
# IMPORTANT -- network reachability: GitHub's hosted runners live on the
# public internet and cannot reach an instance sitting on your home LAN
# unless it's exposed through something like a Cloudflare Tunnel, Tailscale
# Funnel, or reverse proxy with auth in front of it. If you'd rather not
# expose it at all, run this workflow on a *self-hosted* runner on the same
# network as LiteLLM instead (change `runs-on:` in the workflow file) --
# see the accompanying yml for the toggle.
MODEL = os.environ.get("LITELLM_MODEL", "ollama/llama3.1:70b")


# The model sometimes reaches for an em dash out of habit even when told
# not to. The knowledge base's own never_use_em_dash rule is the primary
# guard; this is a cheap belt-and-suspenders fallback, not a substitute
# for the model actually following the instruction.
EM_DASH = "\u2014"


def strip_em_dashes(text: str) -> str:
    """Replace any stray em dash with a comma, as a last-resort safety net."""
    return text.replace(EM_DASH, ",")


def build_baseline_context(kb: dict) -> dict:
    """
    Trims the full knowledge base down to only what the BASELINE (no-JD)
    path actually needs, per generation_workflow_for_llm step 0's fallback.

    This matters for two separate reasons:
    1. Token budget -- the full KB is ~10k tokens on its own; a small/local
       model's context window (num_ctx in Ollama terms) may be far smaller
       than that, especially combined with the system prompt and the
       expected completion, and often defaults to something like 2048-4096
       unless explicitly raised (see call_llm's extra_body num_ctx).
    2. Signal-to-noise -- the full KB includes fields the model has no
       business copying for this task: JD-tailoring bullet variants,
       per-bullet 'themes'/'skills' tags, both title_by_variant options,
       and cover_letter_building_blocks' opening_hook_options /
       body_paragraph_themes / closing_options (all JD-specific, unused in
       the no-JD path). Those are exactly the field names that showed up
       verbatim in a bad response before this trimming was added -- fewer
       irrelevant JSON shapes nearby means less for the model to latch
       onto instead of the requested output schema.
    """
    rules = kb["meta"]["output_rules"]
    summary = kb.get("summary_variants", {}).get("SDE") or next(
        iter(kb.get("summary_variants", {}).values()), ""
    )
    work_experience = [
        {
            "title": job["title_by_variant"].get("SDE", next(iter(job["title_by_variant"].values()))),
            "company": job["company"],
            "team_context": job.get("team_context", ""),
            "date_range": f"{job['start_date']} - {job['end_date']}",
            "bullets": [b["text"] for b in job["bullets"] if not b["id"].endswith(("_alt", "_variant"))],
        }
        for job in kb["work_experience"]
    ]
    return {
        "output_rules": {
            "never_fabricate": rules["never_fabricate"],
            "never_use_em_dash": rules["never_use_em_dash"],
        },
        "personal_info": kb["personal_info"],
        "education": kb["education"],
        "summary": summary,
        "skills": kb["skills"],
        "work_experience": work_experience,
        "cover_letter_generic_template": kb["cover_letter_building_blocks"]["generic_fallback_template"],
    }


def build_system_prompt(kb: dict) -> str:
    """
    Builds the prompt from a TRIMMED baseline-only context (see
    build_baseline_context), not the raw knowledge base -- see that
    function's docstring for why. The target OUTPUT schema is placed
    AFTER the source data and includes a filled-in example (not just
    types), since smaller/local models otherwise tend to echo the
    nearest JSON shape they've seen instead of the requested one.
    """
    context = build_baseline_context(kb)
    return (
        "You are generating a BASELINE resume and cover letter (no specific "
        "job description provided) for the candidate described below. "
        "Use the summary as given, all skills, all work_experience bullets "
        "in the order given, and cover_letter_generic_template for the "
        "cover letter (lightly adapt it, keep 'Dear Hiring Manager'). "
        "Follow output_rules exactly, especially never_fabricate and "
        "never_use_em_dash.\n\n"
        "=== CANDIDATE DATA (read this for content only; its field names "
        "like team_context, date_range, and cover_letter_generic_template "
        "belong to THIS input and must NOT appear in your answer) ===\n"
        + json.dumps(context, indent=2)
        + "\n\n=== YOUR TASK ===\n"
        "Using only the content above, produce ONE JSON object with EXACTLY "
        "these top-level keys: \"resume\" and \"cover_letter\". Nothing else. "
        "No prose before or after it, no markdown code fences, no headings, "
        "no explanation of what you did.\n\n"
        "Here is a SHAPE EXAMPLE with placeholder values, showing the exact "
        "keys your answer must use (do not copy these placeholder values, "
        "replace them with real content from the candidate data above):\n"
        "{\n"
        '  "resume": {\n'
        '    "name": "Full Name",\n'
        '    "contact_line": "email | phone | linkedin",\n'
        '    "summary": "2-4 sentence professional summary",\n'
        '    "skills": [{"category": "Languages", "items": ["Python", "Go"]}],\n'
        '    "work_experience": [\n'
        "      {\n"
        '        "title": "Job Title", "company": "Company Name",\n'
        '        "date_range": "2020 - 2023", "team_context": "Team X",\n'
        '        "bullets": ["Accomplishment one.", "Accomplishment two."]\n'
        "      }\n"
        "    ],\n"
        '    "education": [{"degree": "B.S. Computer Science", "institution": "Some University", "date": "2010"}]\n'
        "  },\n"
        '  "cover_letter": {"body": "Full cover letter text, paragraphs separated by a blank line."}\n'
        "}\n\n"
        "Respond with ONLY that JSON object. Your entire response must start "
        "with { and end with }."
    )


REQUIRED_RESUME_KEYS = {"name", "contact_line", "summary", "skills", "work_experience", "education"}


def extract_json_object(raw: str) -> str:
    """
    Pulls the first balanced {...} block out of a string that may contain
    markdown fences and/or prose before/after it (both observed from the
    local LiteLLM/Ollama model in practice).
    """
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


def validate_content(content: dict) -> None:
    if not isinstance(content, dict) or "resume" not in content or "cover_letter" not in content:
        raise ValueError("Missing top-level 'resume' and/or 'cover_letter' keys.")
    missing = REQUIRED_RESUME_KEYS - set(content["resume"].keys())
    if missing:
        raise ValueError(f"resume is missing required keys: {missing}")
    if "body" not in content["cover_letter"]:
        raise ValueError("cover_letter is missing required key: 'body'")


def call_llm(kb: dict) -> dict:
    base_url = os.environ.get("LITELLM_BASE_URL")
    api_key = os.environ.get("LITELLM_API_KEY")
    if not base_url or not api_key:
        print(
            "LITELLM_BASE_URL and/or LITELLM_API_KEY are not set. "
            "Set them as repo secrets (Settings -> Secrets and variables -> "
            "Actions) before running this workflow. LITELLM_API_KEY should "
            "match LITELLM_MASTER_KEY in that stack's .env.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = openai.OpenAI(base_url=base_url.rstrip("/") + "/v1", api_key=api_key)
    system_prompt = build_system_prompt(kb)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the baseline resume and cover letter JSON now."},
    ]

    # Rough (chars/4) estimate, printed so a too-small OLLAMA_NUM_CTX is easy
    # to spot in the Actions log rather than showing up only as a confusing
    # malformed-JSON failure.
    est_input_tokens = len(system_prompt) // 4
    print(f"Prompt size estimate: ~{est_input_tokens} input tokens (trimmed baseline context).", file=sys.stderr)

    # max_tokens governs OUTPUT length only. A full resume + cover letter is
    # a substantial completion (many bullets across 8 roles, plus a full
    # cover letter body) -- 4000 risked truncating the JSON mid-object,
    # which extract_json_object() would then correctly reject as
    # "no balanced closing brace", surfacing as a confusing failure rather
    # than a clear one. Raised with headroom.
    max_output_tokens = 10000

    # num_ctx is the separate, often-overlooked budget: INPUT + OUTPUT
    # combined, enforced by Ollama itself. Many Ollama models default to a
    # much smaller context window (frequently 2048-4096) than the model
    # architecture actually supports, regardless of max_tokens. If num_ctx
    # is smaller than (prompt + completion), Ollama silently truncates the
    # context -- which can drop or de-prioritize instructions placed early
    # in the prompt, plausibly contributing to the earlier schema-echo bug.
    # Passed through LiteLLM via extra_body; overridable via env var in case
    # your GPU can't hold a larger context for this model.
    num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", "16384"))

    last_error = None
    for attempt in range(2):  # one retry with a corrective follow-up if the first reply is malformed
        try:
            # response_format is a best-effort hint; many Ollama/local models
            # via LiteLLM honor it (forces valid JSON, not necessarily our
            # exact schema), but not all do, so failures here don't abort --
            # extract_json_object()/validate_content() are the real safety net.
            try:
                response = client.chat.completions.create(
                    model=MODEL, max_tokens=max_output_tokens, temperature=0.4, timeout=180,
                    response_format={"type": "json_object"},
                    extra_body={"options": {"num_ctx": num_ctx}},
                    messages=messages,
                )
            except openai.BadRequestError:
                response = client.chat.completions.create(
                    model=MODEL, max_tokens=max_output_tokens, temperature=0.4, timeout=180,
                    extra_body={"options": {"num_ctx": num_ctx}},
                    messages=messages,
                )
        except openai.APIConnectionError as e:
            print(
                f"Could not reach LiteLLM at {base_url}. Is the stack running and "
                "reachable from this runner? (Hosted GitHub runners cannot reach "
                "a private home LAN instance unless it's tunneled/exposed, or "
                "unless this workflow runs on a self-hosted runner on the same "
                f"network.) Underlying error: {e}",
                file=sys.stderr,
            )
            sys.exit(1)
        except openai.APIStatusError as e:
            print(
                f"LiteLLM returned an error (HTTP {e.status_code}): {e.message}. "
                "Check LITELLM_API_KEY matches LITELLM_MASTER_KEY and that "
                "LITELLM_MODEL matches the --model argument LiteLLM was started with.",
                file=sys.stderr,
            )
            sys.exit(1)

        raw = response.choices[0].message.content or ""
        try:
            json_str = extract_json_object(raw)
            content = json.loads(json_str)
            validate_content(content)
            return content
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            print(f"Attempt {attempt + 1}: model output was malformed ({e}). Raw output:\n{raw}\n", file=sys.stderr)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    f"That response was invalid: {e}. Respond again with ONLY the "
                    "JSON object described earlier -- no prose, no markdown fences, "
                    "no commentary, and use exactly the keys resume/cover_letter "
                    "(not the source knowledge base's own field names)."
                ),
            })

    print(
        f"Model failed to produce valid, correctly-shaped JSON after 2 attempts. Last error: {last_error}",
        file=sys.stderr,
    )
    sys.exit(1)


def render_txt(content: dict) -> str:
    r = content["resume"]
    lines = [r["name"], r["contact_line"], "", "SUMMARY", r["summary"], ""]
    lines.append("SKILLS")
    for group in r["skills"]:
        lines.append(f"{group['category']}: {', '.join(group['items'])}")
    lines.append("")
    lines.append("WORK EXPERIENCE")
    for job in r["work_experience"]:
        lines.append(f"{job['title']} | {job['company']} | {job['date_range']}")
        if job.get("team_context"):
            lines.append(job["team_context"])
        for b in job["bullets"]:
            lines.append(f"- {b}")
        lines.append("")
    lines.append("EDUCATION")
    for ed in r["education"]:
        lines.append(f"{ed['degree']}, {ed['institution']} ({ed['date']})")
    text = "\n".join(lines)
    return strip_em_dashes(text)


def render_md(content: dict) -> str:
    r = content["resume"]
    lines = [f"# {r['name']}", r["contact_line"], "", "## Summary", r["summary"], ""]
    lines.append("## Skills")
    for group in r["skills"]:
        lines.append(f"- **{group['category']}:** {', '.join(group['items'])}")
    lines.append("")
    lines.append("## Work Experience")
    for job in r["work_experience"]:
        lines.append(f"### {job['title']} — {job['company']}")
        # note: literal "—" avoided per never_use_em_dash; use a pipe instead
        lines[-1] = f"### {job['title']} | {job['company']}"
        lines.append(f"*{job['date_range']}*")
        if job.get("team_context"):
            lines.append(f"*{job['team_context']}*")
        for b in job["bullets"]:
            lines.append(f"- {b}")
        lines.append("")
    lines.append("## Education")
    for ed in r["education"]:
        lines.append(f"- {ed['degree']}, {ed['institution']} ({ed['date']})")
    text = "\n".join(lines)
    return strip_em_dashes(text)


def render_docx(content: dict, path: Path) -> None:
    r = content["resume"]
    doc = Document()

    title = doc.add_heading(r["name"], level=1)
    contact = doc.add_paragraph(r["contact_line"])
    contact.runs[0].font.size = Pt(10)

    doc.add_heading("Summary", level=2)
    doc.add_paragraph(strip_em_dashes(r["summary"]))

    doc.add_heading("Skills", level=2)
    for group in r["skills"]:
        p = doc.add_paragraph()
        p.add_run(f"{group['category']}: ").bold = True
        p.add_run(strip_em_dashes(", ".join(group["items"])))

    doc.add_heading("Work Experience", level=2)
    for job in r["work_experience"]:
        p = doc.add_paragraph()
        p.add_run(f"{job['title']} | {job['company']}").bold = True
        doc.add_paragraph(job["date_range"])
        if job.get("team_context"):
            doc.add_paragraph(job["team_context"]).italic = True
        for b in job["bullets"]:
            doc.add_paragraph(strip_em_dashes(b), style="List Bullet")

    doc.add_heading("Education", level=2)
    for ed in r["education"]:
        doc.add_paragraph(f"{ed['degree']}, {ed['institution']} ({ed['date']})")

    doc.save(path)


def render_cover_letter_docx(content: dict, path: Path) -> None:
    doc = Document()
    body = strip_em_dashes(content["cover_letter"]["body"])
    for para in body.split("\n\n"):
        doc.add_paragraph(para)
    doc.save(path)


def render_pdf(content: dict, path: Path, is_cover_letter: bool = False) -> None:
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("Body", parent=styles["Normal"], spaceAfter=8, leading=14)
    heading_style = ParagraphStyle("H2", parent=styles["Heading2"], spaceBefore=12)
    doc = SimpleDocTemplate(str(path), pagesize=LETTER,
                             leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                             topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    story = []

    if is_cover_letter:
        body = strip_em_dashes(content["cover_letter"]["body"])
        for para in body.split("\n\n"):
            story.append(Paragraph(para.replace("\n", "<br/>"), body_style))
    else:
        r = content["resume"]
        story.append(Paragraph(f"<b>{r['name']}</b>", styles["Title"]))
        story.append(Paragraph(r["contact_line"], body_style))
        story.append(Paragraph("Summary", heading_style))
        story.append(Paragraph(strip_em_dashes(r["summary"]), body_style))
        story.append(Paragraph("Skills", heading_style))
        for group in r["skills"]:
            story.append(Paragraph(
                f"<b>{group['category']}:</b> {strip_em_dashes(', '.join(group['items']))}",
                body_style))
        story.append(Paragraph("Work Experience", heading_style))
        for job in r["work_experience"]:
            story.append(Paragraph(f"<b>{job['title']} | {job['company']}</b>", body_style))
            story.append(Paragraph(job["date_range"], body_style))
            if job.get("team_context"):
                story.append(Paragraph(f"<i>{job['team_context']}</i>", body_style))
            for b in job["bullets"]:
                story.append(Paragraph(f"- {strip_em_dashes(b)}", body_style))
            story.append(Spacer(1, 6))
        story.append(Paragraph("Education", heading_style))
        for ed in r["education"]:
            story.append(Paragraph(f"{ed['degree']}, {ed['institution']} ({ed['date']})", body_style))

    doc.build(story)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to resume_data.json")
    parser.add_argument("--out", required=True, help="Output directory (e.g. generated/)")
    args = parser.parse_args()

    kb = json.loads(Path(args.data).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    content = call_llm(kb)

    base = "Dennis_Dole_Resume_Baseline"
    cl_base = "Dennis_Dole_CoverLetter_Baseline"

    (out_dir / f"{base}.json").write_text(json.dumps(content["resume"], indent=2), encoding="utf-8")
    (out_dir / f"{base}.txt").write_text(render_txt(content), encoding="utf-8")
    (out_dir / f"{base}.md").write_text(render_md(content), encoding="utf-8")
    render_docx(content, out_dir / f"{base}.docx")
    render_pdf(content, out_dir / f"{base}.pdf", is_cover_letter=False)

    (out_dir / f"{cl_base}.txt").write_text(strip_em_dashes(content["cover_letter"]["body"]), encoding="utf-8")
    (out_dir / f"{cl_base}.json").write_text(json.dumps(content["cover_letter"], indent=2), encoding="utf-8")
    render_cover_letter_docx(content, out_dir / f"{cl_base}.docx")
    render_pdf(content, out_dir / f"{cl_base}.pdf", is_cover_letter=True)

    print(f"Wrote baseline resume + cover letter (5 formats each) to {out_dir}/")


if __name__ == "__main__":
    main()