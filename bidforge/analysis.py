"""Tender-to-evidence analysis and bid-readiness helpers."""
import pandas as pd

from bidforge.tools import analyze_risks, find_document_requests, scan_requirements
from bidforge.rag import retrieve_for_requirements


def _find_fact_lines(tender_text: str) -> dict[str, list[dict]]:
    groups = {
        "Authority": ("authority", "contracting authority", "issued by", "procuring entity", "department"),
        "Deadline": ("deadline", "closing date", "closing time", "submission deadline", "due date"),
        "Submission": ("submit", "submission method", "portal", "email", "hard copy", "copies"),
        "Evaluation": ("evaluation criteria", "scoring", "weighting", "technical score", "financial score"),
        "Key dates": ("site visit", "pre-bid", "pre bid", "clarification deadline", "opening date"),
        "Eligibility": ("eligible", "eligibility", "minimum experience", "years of experience", "financial standing", "turnover"),
    }
    found = {key: [] for key in groups}
    source = "[SOURCE NOT IDENTIFIED]"
    for raw in tender_text.splitlines():
        line = raw.strip()
        if line.startswith("[SOURCE:"):
            source = line.strip("[]")
            continue
        lower = line.lower()
        if not line:
            continue
        for key, terms in groups.items():
            if any(term in lower for term in terms) and len(found[key]) < 12:
                found[key].append({"text": line[:500], "source": source})
    return found


def analyze_tender(tender_text: str, company_chunks: list[dict]) -> dict:
    requirements = scan_requirements(tender_text)
    linked = retrieve_for_requirements(requirements, company_chunks)
    rows = []
    for item in linked:
        sources = item["evidence"]
        if sources:
            status = "Potential evidence — verify"
            company_evidence = "\n\n".join(f"[{ev['source']}] {ev['text'][:650]}" for ev in sources)
            response = "Review the cited evidence and confirm it satisfies the exact tender wording."
        else:
            status = "Missing evidence"
            company_evidence = "[TO BE PROVIDED: supporting company evidence]"
            response = "Identify an authoritative company document or record, or explain the gap."
        rows.append({
            "Requirement": item["requirement"],
            "Mandatory": item["mandatory"],
            "Tender source": item["source"],
            "Tender excerpt": item["excerpt"],
            "Company evidence": company_evidence,
            "Status": status,
            "Response": response,
            "Reviewer notes": "AI-assisted candidate; verify against original tender and evidence.",
            "Owner": "[TO BE ASSIGNED]",
        })
    matrix = pd.DataFrame(rows, columns=[
        "Requirement", "Mandatory", "Tender source", "Tender excerpt", "Company evidence",
        "Status", "Response", "Reviewer notes", "Owner",
    ])
    return {
        "facts": _find_fact_lines(tender_text),
        "requirements": requirements,
        "linked_requirements": linked,
        "matrix": matrix,
        "risks": analyze_risks(tender_text),
        "document_requests": find_document_requests(requirements),
        "eligible_requirements": [item for item in requirements if any(term in item["requirement"].lower() for term in ("eligib", "experience", "turnover", "financial standing", "registration", "license", "licence"))],
    }
