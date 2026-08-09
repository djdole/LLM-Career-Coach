#!/usr/bin/env python3
"""
Generates baseline (no-specific-JD) resume + cover letter outputs from
data/resume_data.json, in pdf/docx/txt/md/json formats.

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

import anthropic
from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

MODEL = "claude-sonnet-4-6"

# The model sometimes reaches for an em dash out of habit even when told
# not to. The knowledge base's own never_use_em_dash rule is the primary
# guard; this is a cheap belt-and-suspenders fallback, not a substitute
# for the model actually following the instruction.
EM_DASH = "\u2014"


def strip_em_dashes(text: str) -> str:
    """Replace any stray em dash with a comma, as a last-resort safety net."""
    return text.replace(EM_DASH, ",")


def build_system_prompt(kb: dict) -> str:
    """
    Embeds the knowledge base's own meta/output_rules/generation_workflow
    instructions into the system prompt, so the resume generation logic
    lives in one place (the JSON file) rather than being duplicated here.
    """
    return (
        "You are generating a BASELINE resume and cover letter (no specific "
        "job description provided) from the candidate knowledge base below. "
        "Follow generation_workflow_for_llm step 0's no-JD fallback: use the "
        "SDE summary_variant as the default summary, default skill category "
        "order, all default (non-alt) work_experience bullets, and "
        "cover_letter_building_blocks.generic_fallback_template for the "
        "cover letter. Follow every rule in meta.output_rules, especially "
        "never_fabricate and never_use_em_dash.\n\n"
        "Respond with ONLY a single JSON object (no markdown fences, no "
        "commentary) matching exactly this shape:\n"
        "{\n"
        '  "resume": {\n'
        '    "name": str, "contact_line": str, "summary": str,\n'
        '    "skills": [{"category": str, "items": [str, ...]}, ...],\n'
        '    "work_experience": [\n'
        '      {"title": str, "company": str, "date_range": str,\n'
        '       "team_context": str, "bullets": [str, ...]}, ...\n'
        "    ],\n"
        '    "education": [{"degree": str, "institution": str, "date": str}]\n'
        "  },\n"
        '  "cover_letter": {"body": str}\n'
        "}\n\n"
        "Knowledge base:\n" + json.dumps(kb, indent=2)
    )


def call_claude(kb: dict) -> dict:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=build_system_prompt(kb),
        messages=[
            {
                "role": "user",
                "content": "Generate the baseline resume and cover letter JSON now.",
            }
        ],
    )
    raw = "".join(block.text for block in response.content if block.type == "text")
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print("Model did not return valid JSON:\n", raw, file=sys.stderr)
        raise e


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

    content = call_claude(kb)

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
    