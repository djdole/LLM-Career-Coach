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


# Keys from resume_data.json that must NOT be embedded verbatim in this
# script's prompt. Both were written for a different, interactive workflow
# (a chat assistant tailoring a resume to a pasted job description) and
# actively contradict this script's single-JSON-object contract:
#   - generation_workflow_for_llm step 9 says to "clearly separate RESUME
#     and COVER LETTER content" as prose sections.
#   - output_format_instructions describes pdf/docx/txt/md/json as parallel
#     *output formats* to choose between, not a nested JSON schema.
# A weaker local model will follow whichever instruction it saw, and these
# two blocks are large, detailed, and internally consistent enough that
# they can out-compete the wrapper instruction below. Excluding them here
# removes the contradiction instead of just out-shouting it.
_KB_KEYS_TO_OMIT_FROM_PROMPT = {"generation_workflow_for_llm", "output_format_instructions"}


def build_system_prompt(kb: dict) -> str:
    """
    Embeds the relevant parts of the knowledge base into the system prompt.
    See _KB_KEYS_TO_OMIT_FROM_PROMPT for what's deliberately left out and why.
    """
    trimmed_kb = {k: v for k, v in kb.items() if k not in _KB_KEYS_TO_OMIT_FROM_PROMPT}

    return (
        "You are generating a BASELINE resume and cover letter (no specific "
        "job description provided) from the candidate knowledge base below. "
        "Use the SDE summary_variant as the default summary, default skill "
        "category order, all default (non-alt) work_experience bullets, and "
        "cover_letter_building_blocks.generic_fallback_template for the "
        "cover letter. Follow every rule in meta.output_rules, especially "
        "never_fabricate and never_use_em_dash.\n\n"
        "CRITICAL RULES:\n"
        "- DO NOT BREAK ANY OF THE FOLLOWING RULES.\n"
        "- Do NOT omit data by using placeholder text like '...'.\n"
        "- Do NOT include any introductory or concluding text in your response.\n"
        "- Respond with EXACTLY ONE JSON object and nothing else.\n"
        "- Do NOT include markdown formatting, markdown blocks, or triple backticks (```).\n"
        "- Do not include markdown code fences (no ```).\n"
        "- Do not include any heading, label, or prose before or after the JSON (no '**Resume:**', no '**Cover Letter:**', no 'Here is the generated baseline resume and cover letter JSON:', no closing notes explaining the output, no apologies, no requests, no inquiries, no superfluous text at all).\n"
        "- Do not produce two separate JSON objects. The resume and cover letter both go INSIDE the one object below, as the 'resume' and 'cover_letter' keys.\n"
        "- Do not include any additional text before or after the JSON response. Your entire response should be SOLELY valid JSON.\n"
        "- Your entire response must be parseable by json.loads() with no preprocessing.\n"
        "- Before responding, review your response to ensure you're only returning valid parsable JSON.\n\n"
        "Required shape, with a filled-in example so the structure is "
        "unambiguous (use your own real content from the knowledge base, "
        "this is only to illustrate the shape):\n"
        "{\n"
        '  "resume": {\n'
        '    "name": "Dennis Jay Dole",\n'
        '    "contact_line": "Des Moines, WA | Dennis.Dole@djdole.net | 734-218-2358",\n'
        '    "summary": "Software developer with ...",\n'
        '    "skills": [{"category": "Languages", "items": ["C#", "Python"]}],\n'
        '    "work_experience": [\n'
        "      {\n"
        '        "title": "Software Developer",\n'
        '        "company": "Docusign, Inc.",\n'
        '        "date_range": "Mar 2024 - Jul 2025",\n'
        '        "team_context": "Docusign Connect",\n'
        '        "bullets": ["Designed and implemented ..."]\n'
        "      }\n"
        "    ],\n"
        '    "education": [{"degree": "B.S. Computer Science", "institution": "Michigan Technological University", "date": "Dec 2004"}]\n'
        "  },\n"
        '  "cover_letter": {"body": "Dear Hiring Manager, ..."}\n'
        "}\n\n"
        "Knowledge base:\n" + json.dumps(trimmed_kb, indent=2)
    )


def extract_json_object(raw: str) -> str:
    """
    Best-effort extraction of a single JSON object from model output that
    may still have stray prose/labels/fences around it despite the prompt
    (local models drift more than hosted ones). Finds the first '{' and
    the matching closing '}' by brace counting, so leading text like
    '**Resume:**' or a trailing 'Note that this output is...' sentence
    doesn't break json.loads(). Does NOT attempt to merge multiple
    separate JSON objects -- if the model returned two objects instead of
    one, that's a prompt-compliance failure the retry in call_llm handles,
    not something safe to paper over here.
    """
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text  # unbalanced; let json.loads() raise with the real error


def validate_content_shape(content: dict) -> None:
    """Fail with a clear message instead of a KeyError deep in a render_* function."""
    if "resume" not in content or "cover_letter" not in content:
        raise ValueError(
            f"Parsed JSON is missing top-level 'resume' and/or 'cover_letter' "
            f"keys. Got keys: {list(content.keys())}"
        )
    resume_required = {"name", "contact_line", "summary", "skills", "work_experience", "education"}
    missing = resume_required - set(content["resume"].keys())
    if missing:
        raise ValueError(f"'resume' object is missing required keys: {sorted(missing)}")
    if "body" not in content["cover_letter"]:
        raise ValueError("'cover_letter' object is missing required key: 'body'")


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

    messages = [
        {"role": "system", "content": build_system_prompt(kb)},
        {"role": "user", "content": "Generate the baseline resume and cover letter JSON now."},
    ]

    # Local/open models are less reliable than hosted ones about staying on
    # format; give it one corrective retry with the bad output and a
    # sharper instruction before giving up, rather than failing the whole
    # workflow run on the first drift.
    last_error: Exception | None = None
    for attempt in range(1, 3):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=10000,
                temperature=0.4,
                timeout=180,  # fail fast rather than hang if the instance is unreachable
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
        candidate = extract_json_object(raw)
        try:
            content = json.loads(candidate)
            validate_content_shape(content)
            return content
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            print(f"Attempt {attempt} did not produce valid content ({e}).", file=sys.stderr)
            if attempt == 1:
                print("Raw model output was:\n", raw, file=sys.stderr)
                print("Retrying once with a corrective follow-up message...", file=sys.stderr)
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": (
                        f"That response was invalid: {e}. It must be EXACTLY ONE JSON object with top-level keys 'resume' and 'cover_letter', no headings like '**Resume:**', no separate JSON objects, no commentary before or after, no markdown code fences. Return the corrected JSON object now, and nothing else.\nCRITICAL RULES:\n- DO NOT BREAK ANY OF THE FOLLOWING RULES.\n- Do NOT omit data by using placeholder text like '...'.\n- Do NOT include any introductory or concluding text in your response.\n- Respond with EXACTLY ONE JSON object and nothing else.\n- Do NOT include markdown formatting, markdown blocks, or triple backticks (```).\n- Do not include markdown code fences (no ```).\n- Do not include any heading, label, or prose before or after the JSON (no '**Resume:**', no '**Cover Letter:**', no 'Here is the generated baseline resume and cover letter JSON:', no closing notes explaining the output, no apologies, no requests, no inquiries, no superfluous text at all).\n- Do not produce two separate JSON objects. The resume and cover letter both go INSIDE the one object below, as the 'resume' and 'cover_letter' keys.\n- Do not include any additional text before or after the JSON response. Your entire response should be SOLELY valid JSON.\n- Your entire response must be parseable by json.loads() with no preprocessing.\n- Before responding, review your response to ensure you're only returning valid parsable JSON."
                    ),
                })

    print("Model did not return valid JSON after retrying:\n", raw, file=sys.stderr)
    raise last_error


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