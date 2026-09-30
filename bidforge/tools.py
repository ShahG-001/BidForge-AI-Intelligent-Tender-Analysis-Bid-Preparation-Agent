"""Deterministic procurement helpers run before the language model."""
import re


REQUIREMENT_TERMS = (
    "must", "shall", "required", "mandatory", "submit", "provide", "include",
    "deadline", "closing date", "eligibility", "bid security", "bid bond",
    "evaluation", "deliverable", "pricing", "tax", "certificate", "insurance",
    "reference", "curriculum vitae", "cv of", "schedule", "audit logging",
    "data protection", "backup", "warranty", "support", "training",
    "experience", "turnover", "financial standing", "registration", "license",
    "licence", "comparable project", "past performance", "declaration", "source code",
    "performance security", "validity period", "restore process", "security approach",
)


def _source_lines(text: str):
    marker = "[SOURCE NOT IDENTIFIED]"
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[SOURCE:"):
            marker = line.strip("[]")
            continue
        if line:
            yield marker, line


def scan_requirements(tender_text: str, limit: int = 100) -> list[dict]:
    """Extract requirement-like source lines; these are candidates, not legal conclusions."""
    results, seen = [], set()
    for source, line in _source_lines(tender_text):
        candidate = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if len(candidate) < 8 or not any(term in candidate.lower() for term in REQUIREMENT_TERMS):
            continue
        normalized = candidate.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        text = candidate.lower()
        mandatory = any(term in text for term in ("must", "shall", "mandatory", "required"))
        results.append({
            "requirement": candidate[:500],
            "source": source,
            "excerpt": candidate[:700],
            "mandatory": "Potentially mandatory — verify" if mandatory else "Needs review",
        })
        if len(results) >= limit:
            break
    return results


def check_pricing_arithmetic(rows: list[dict]) -> list[dict]:
    """Calculate explicit quantity × rate rows without guessing missing values."""
    output = []
    for row in rows:
        item = str(row.get("Resource", row.get("Item", row.get("Description", "Item"))))
        quantity_value = row.get("Quantity", row.get("Qty"))
        rate_value = row.get("Rate", row.get("Unit Price", row.get("Unit rate")))
        try:
            quantity = float(str(quantity_value).replace(",", ""))
            rate = float(str(rate_value).replace(",", ""))
        except (TypeError, ValueError):
            output.append({"item": item, "total": None, "note": "Not calculated: provide numeric Quantity and Rate."})
            continue
        output.append({"item": item, "total": quantity * rate, "note": "Calculated from user-provided quantity and rate; verify taxes and charges."})
    return output


def analyze_risks(tender_text: str) -> list[dict]:
    """Flag clauses or information gaps for human review, without giving legal advice."""
    flagged = {
        "penalty": "Review penalty amounts, triggers, and caps with a qualified reviewer.",
        "liquidated damages": "Review liquidated damages terms and exposure with a qualified reviewer.",
        "indemnity": "Review indemnity obligations with legal counsel.",
        "liability": "Review liability limits and exclusions with legal counsel.",
        "intellectual property": "Confirm ownership and licensing terms with legal counsel.",
        "termination": "Review termination rights and notice periods with legal counsel.",
        "insurance": "Verify required coverage types, limits, and evidence with the broker.",
        "warranty": "Confirm warranty duration and obligations with delivery leads.",
        "data protection": "Review privacy/security obligations with the security or legal team.",
        "bid security": "Confirm amount, validity, issuer, and format; obtain original evidence if required.",
    }
    lower = tender_text.lower()
    results = []
    for phrase, action in flagged.items():
        if phrase in lower:
            results.append({"risk": phrase.title(), "level": "Review", "action": action})
    if not any(phrase in lower for phrase in ("deadline", "closing date", "closing time", "due date")):
        results.append({"risk": "Submission deadline not identified", "level": "High", "action": "Verify the deadline and timezone in the original tender."})
    if not any(phrase in lower for phrase in ("evaluation criteria", "evaluation criteria:", "scoring", "weighting")):
        results.append({"risk": "Evaluation detail may be incomplete", "level": "Review", "action": "Confirm evaluation criteria and weighting in the complete tender."})
    return results


def find_document_requests(requirements: list[dict]) -> list[str]:
    """Collect candidate attachment/document requests from extracted requirements."""
    terms = ("certificate", "registration", "tax", "insurance", "cv", "curriculum vitae", "reference", "cover letter", "bid bond", "bid security", "financial statement", "audit", "company profile", "project")
    found = []
    for item in requirements:
        line = item["requirement"]
        if any(term in line.lower() for term in terms) and line not in found:
            found.append(line)
    return found
