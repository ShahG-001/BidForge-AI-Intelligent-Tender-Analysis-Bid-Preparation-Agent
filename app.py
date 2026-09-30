"""BidForge AI: tender analysis, evidence retrieval, compliance and response drafting."""
import base64
import html
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="BidForge AI", page_icon="📑", layout="wide")
if sys.version_info >= (3, 14):
    st.error("Choose Python 3.12 in Streamlit Cloud → Advanced settings, then redeploy.")
    st.stop()

from bidforge.agent import draft_response
from bidforge.analysis import analyze_tender
from bidforge.document_reader import read_uploaded_file
from bidforge.exports import to_docx, to_pdf
from bidforge.memory import add_to_memory, get_memory, reset_memory
from bidforge.rag import chunk_source, retrieve
from bidforge.tools import check_pricing_arithmetic
from bidforge.web_reader import fetch_public_text


LOGO_PATH = Path(__file__).parent / "assets" / "bidforge-logo.png"
LOGO_BASE64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii") if LOGO_PATH.exists() else ""
LOGO_MARKUP = (
    f'<img class="bf-logo" src="data:image/png;base64,{LOGO_BASE64}" alt="BidForge AI logo">'
    if LOGO_BASE64 else '<span class="bf-brand-text">BidForge <b>AI</b></span>'
)

st.markdown(
    """
    <style>
    :root {--bf-blue:#2457d6;--bf-ink:#152238;--bf-muted:#60718b;--bf-line:#dce5f1;}
    .stApp {background:radial-gradient(ellipse at 4% 0%,#e9f1ff 0,transparent 34%),radial-gradient(ellipse at 96% 2%,#e4f7f4 0,transparent 28%),linear-gradient(135deg,#f9fbff,#f2f6fc 55%,#f6fbf9);background-attachment:fixed;color:var(--bf-ink);}
    .block-container {max-width:1400px;padding-top:1rem;padding-bottom:3rem;}
    [data-testid="stHeader"] {background:rgba(248,250,253,.88);}
    [data-testid="stTabs"] button {font-weight:650;color:#40516b!important;}
    .bf-top {display:flex;align-items:center;justify-content:space-between;padding:.45rem 0 1rem;margin-bottom:1.25rem;border-bottom:1px solid var(--bf-line);}
    .bf-logo {width:225px;height:72px;object-fit:contain;object-position:left center;display:block;}
    .bf-brand-text {font-size:1.55rem;font-weight:800;letter-spacing:-.04em;color:#12305e;}
    .bf-brand-text b {color:#0e9b91;}
    .bf-pill {background:white;border:1px solid var(--bf-line);border-radius:999px;padding:.4rem .75rem;color:#4b5d77;font-size:.8rem;}
    .bf-hero {background:linear-gradient(110deg,rgba(255,255,255,.96),rgba(241,247,255,.96) 65%,rgba(237,250,247,.96));border:1px solid #dbe6f4;border-radius:18px;padding:1.4rem 1.6rem;box-shadow:0 10px 28px rgba(23,55,105,.055);margin-bottom:1rem;}
    .bf-hero h1 {color:#152238;font-size:1.85rem;letter-spacing:-.035em;margin:.25rem 0 .35rem;}
    .bf-hero p {color:#536781;margin:0;max-width:850px;}
    .bf-title {font-size:1.18rem;font-weight:760;color:#172b49;margin:.2rem 0;}
    .bf-muted {color:#61738d;font-size:.9rem;margin-bottom:.7rem;}
    .bf-card {background:#fff;border:1px solid var(--bf-line);border-radius:13px;padding:.9rem 1rem;min-height:100px;box-shadow:0 3px 12px rgba(15,23,42,.025);}
    .bf-card-label {color:#6b7b92;font-size:.78rem;font-weight:650;}
    .bf-card-value {font-size:1.5rem;font-weight:780;color:#172b49;margin-top:.25rem;}
    .bf-card-note {font-size:.74rem;color:#6b7b92;}
    .bf-review {background:#fff7e7;border:1px solid #f0d8a9;color:#80520d;border-radius:10px;padding:.8rem 1rem;margin:.8rem 0 1.1rem;}
    .bf-preview {white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto;background:#fff;border:1px solid var(--bf-line);border-radius:10px;padding:.9rem 1rem;font-size:.87rem;line-height:1.55;}
    .bf-ai {color:#673ab7;font-weight:700;font-size:.76rem;}
    .bf-source {color:#1d4ed8;font-weight:700;font-size:.76rem;}
    @media(max-width:760px){.block-container{padding-left:1rem;padding-right:1rem}.bf-logo{width:165px;height:56px}.bf-hero h1{font-size:1.45rem}}
    </style>
    """ + f'<div class="bf-top"><div>{LOGO_MARKUP}</div><div class="bf-pill">Single-agent tender workspace · Groq</div></div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="bf-hero"><div style="color:#2457d6;font-size:.75rem;font-weight:750;letter-spacing:.1em;text-transform:uppercase">Tender intelligence and bid preparation</div><h1>From tender documents to bid-ready intelligence.</h1><p>Extract requirements, retrieve relevant company evidence, review compliance and risks, and draft a response with visible evidence gaps.</p></div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="bf-review"><b>Human review required.</b> BidForge provides source-grounded drafts and review candidates. Confirm all requirements, eligibility, evidence, pricing, deadlines, and legal terms against authoritative documents before submission.</div>', unsafe_allow_html=True)


DEFAULT_MATRIX = pd.DataFrame(columns=[
    "Requirement", "Mandatory", "Tender source", "Tender excerpt", "Company evidence",
    "Status", "Response", "Reviewer notes", "Owner",
])
for key, default in {
    "bidforge_memory": [], "bf_tender_text": "", "bf_tender_name": "",
    "bf_company_chunks": [], "bf_company_facts": "", "bf_company_warnings": [],
    "bf_analysis": None, "bf_matrix": DEFAULT_MATRIX, "bf_matrix_editing": False,
    "bf_draft": "", "bf_draft_editing": False, "bf_draft_saved": "",
    "bf_tender_warnings": [], "bf_company_filenames": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def api_key_from_secrets():
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        try:
            key = st.secrets.get("GROQ_API_KEY", "")
        except Exception:
            key = ""
    return key.strip()


def source_preview(text: str, limit: int = 16000):
    shown = html.escape((text or "")[:limit]) or "No source text available."
    st.markdown(f'<div class="bf-preview">{shown}</div>', unsafe_allow_html=True)


def metric(col, title: str, value: str, hint: str):
    with col:
        st.markdown(f'<div class="bf-card"><div class="bf-card-label">{html.escape(title)}</div><div class="bf-card-value">{html.escape(value)}</div><div class="bf-card-note">{html.escape(hint)}</div></div>', unsafe_allow_html=True)


def refresh_analysis():
    tender = st.session_state.get("bf_tender_text", "")
    if not tender.strip():
        return None
    analysis = analyze_tender(tender, st.session_state.get("bf_company_chunks", []))
    st.session_state.bf_analysis = analysis
    st.session_state.bf_matrix = analysis["matrix"]
    st.session_state.bf_matrix_editing = False
    return analysis


def build_draft_context(analysis: dict, pricing_csv: str, format_notes: str) -> str:
    tender = st.session_state.bf_tender_text
    tender_excerpt = tender[:5200]
    facts = st.session_state.get("bf_company_facts", "")[:1400] or "[Not provided]"
    requirement_lines = "\n".join(
        f"- {item['requirement']} | {item['source']} | {item['mandatory']}"
        for item in analysis["requirements"][:50]
    ) or "No requirement candidates extracted; review the complete tender."
    evidence, seen = [], set()
    for item in analysis["linked_requirements"]:
        for match in item["evidence"]:
            key = (match["source"], match["text"][:160])
            if key in seen:
                continue
            seen.add(key)
            evidence.append(f"[{match['source']}] Relevant to: {item['requirement']}\n{match['text'][:700]}")
            if len(evidence) >= 12:
                break
        if len(evidence) >= 12:
            break
    risk_lines = "\n".join(f"- {item['risk']}: {item['action']}" for item in analysis["risks"]) or "No rule-based flags; review the full contract and tender."
    document_lines = "\n".join(f"- {line}" for line in analysis["document_requests"]) or "No specific attachment requests were identified by the local scan; check the tender list."
    return f"""TENDER EXCERPT (check complete source for anything omitted):
{tender_excerpt}

REQUIREMENT CANDIDATES (locally extracted; verify every item):
{requirement_lines}

COMPANY FACTS PROVIDED BY USER:
{facts}

RETRIEVED COMPANY EVIDENCE (BM25 lexical RAG; source-labelled excerpts):
{chr(10).join(evidence) or '[No relevant company evidence retrieved. Do not claim company compliance.]'}

RISK REVIEW FLAGS (rule-based; not legal advice):
{risk_lines}

POTENTIAL SUPPORTING DOCUMENTS TO CHECK:
{document_lines}

USER-ENTERED PRICING TABLE:
{pricing_csv[:1800] or '[No pricing data. Leave amounts blank; do not estimate.]'}

ISSUER TEMPLATE / FORMAT NOTES:
{format_notes[:1000] or '[Not provided]'}

EXTRACTION WARNINGS:
{chr(10).join(st.session_state.bf_tender_warnings + st.session_state.bf_company_warnings) or 'None reported.'}
"""


tabs = st.tabs(["Dashboard", "Tender Analysis", "Company Evidence", "Bid Builder", "Compliance & Risks", "Documents"])


with tabs[0]:
    st.markdown('<div class="bf-title">Bid preparation dashboard</div><div class="bf-muted">A clear view of tender intake, evidence coverage, gaps, and review status.</div>', unsafe_allow_html=True)
    analysis = st.session_state.bf_analysis or {}
    requirements = analysis.get("linked_requirements", [])
    matches = sum(1 for item in requirements if item.get("evidence"))
    missing = max(0, len(requirements) - matches)
    risks = analysis.get("risks", [])
    metrics = st.columns(5)
    metric(metrics[0], "Tender source", "Loaded" if st.session_state.bf_tender_text else "Needed", "Upload, paste, or fetch a public link")
    metric(metrics[1], "Requirements", str(len(requirements)), "Local source-line candidates")
    metric(metrics[2], "Evidence chunks", str(len(st.session_state.bf_company_chunks)), "Indexed from supplied company sources")
    metric(metrics[3], "Evidence matches", str(matches), "Potential matches; verify manually")
    metric(metrics[4], "Risk flags", str(len(risks)), "Rule-based review prompts")
    st.markdown("")
    coverage = f"{(100 * matches / len(requirements)):.0f}%" if requirements else "—"
    st.info(f"Potential evidence coverage: **{coverage}** · This is lexical overlap, not confirmed eligibility or compliance.")
    st.markdown("**Workflow**  ")
    st.write("1. Load the tender.  2. Index verified company documents.  3. Review requirements, evidence matches, and risks.  4. Draft selected response sections.  5. Edit and export the package.")
    st.caption("Company evidence and notes are held in the current Streamlit session; they are not durable across app restarts.")


with tabs[1]:
    st.markdown('<div class="bf-title">Tender analysis</div><div class="bf-muted">Load a tender, inspect extracted text, then analyze requirements and key dates.</div>', unsafe_allow_html=True)
    pasted_tender = st.text_area("Paste tender text (optional)", height=130, placeholder="Paste text from an RFP/RFT/RFQ…", key="bf_paste_tender")
    tender_file = st.file_uploader("Upload a tender document", type=["pdf", "docx", "txt", "md", "csv"], key="bf_tender_file")
    tender_url = st.text_input("Or add a public tender webpage / direct PDF URL", placeholder="https://…", key="bf_tender_url")
    load_col, clear_col = st.columns([1, 1])
    with load_col:
        if st.button("Load tender source", type="primary", key="bf_load_tender"):
            parts, warnings = [], []
            tender_name = "Pasted tender text"
            if pasted_tender.strip():
                parts.append(f"[SOURCE: Pasted tender text]\n{pasted_tender.strip()}")
            if tender_file:
                parsed, warning = read_uploaded_file(tender_file)
                if parsed.strip():
                    parts.append(parsed)
                    tender_name = tender_file.name
                if warning:
                    warnings.append(warning)
            if tender_url.strip():
                try:
                    parsed, warning = fetch_public_text(tender_url.strip())
                    if parsed.strip():
                        parts.append(parsed)
                        tender_name = tender_url.strip()
                    if warning:
                        warnings.append(warning)
                except Exception as error:
                    warnings.append(f"Tender URL could not be read: {error}")
            if parts:
                st.session_state.bf_tender_text = "\n\n".join(parts)
                st.session_state.bf_tender_name = tender_name
                st.session_state.bf_tender_warnings = warnings
                st.session_state.bf_analysis = None
                st.success(f"Tender loaded: {tender_name}")
            else:
                st.warning("Paste tender text, upload a file, or enter a public URL first.")
    with clear_col:
        if st.button("Clear tender", key="bf_clear_tender"):
            st.session_state.bf_tender_text = ""
            st.session_state.bf_tender_name = ""
            st.session_state.bf_analysis = None
            st.session_state.bf_matrix = DEFAULT_MATRIX.copy()
            st.session_state.bf_draft = ""
            st.rerun()
    if st.session_state.bf_tender_text:
        st.success(f"Loaded · {st.session_state.bf_tender_name or 'Tender source'} · {len(st.session_state.bf_tender_text):,} characters")
        with st.expander("Preview extracted tender text", expanded=False):
            source_preview(st.session_state.bf_tender_text)
        for warning in st.session_state.bf_tender_warnings:
            st.warning(warning)
        if st.button("Analyze requirements, dates, and risks", type="primary", key="bf_analyze_tender"):
            with st.spinner("Extracting requirement candidates and matching indexed company evidence…"):
                result = refresh_analysis()
            st.success(f"Analysis ready · {len(result['requirements'])} requirement candidate(s) · {len(result['risks'])} risk flag(s)")
        analysis = st.session_state.bf_analysis
        if analysis:
            for group, items in analysis["facts"].items():
                with st.expander(group, expanded=group in {"Deadline", "Eligibility"}):
                    if items:
                        for item in items:
                            st.markdown(f"- {item['text']}  \n  _{item['source']}_")
                    else:
                        st.caption("Not identified in extracted text. Check the tender manually.")


with tabs[2]:
    st.markdown('<div class="bf-title">Company evidence library</div><div class="bf-muted">Upload authoritative company materials or add verified facts. BidForge retrieves relevant excerpts for each tender requirement.</div>', unsafe_allow_html=True)
    company_facts = st.text_area("Verified company facts (optional)", height=100, placeholder="Company name, registrations, capabilities, certifications, financial facts…", key="bf_company_facts_input")
    company_files = st.file_uploader("Upload company profile, certificates, CVs, references, or templates", type=["pdf", "docx", "txt", "md", "csv"], accept_multiple_files=True, key="bf_company_files")
    company_urls = st.text_area("Public company evidence URLs (optional; one per line)", height=70, placeholder="https://company.example/about\nhttps://company.example/projects", key="bf_company_urls")
    if st.button("Index company evidence", type="primary", key="bf_index_company"):
        sources, warnings, filenames = [], [], []
        for uploaded in company_files or []:
            extracted, warning = read_uploaded_file(uploaded)
            if extracted.strip():
                sources.append((uploaded.name, extracted))
                filenames.append(uploaded.name)
            if warning:
                warnings.append(warning)
        for url in [line.strip() for line in company_urls.splitlines() if line.strip()]:
            try:
                extracted, warning = fetch_public_text(url)
                if extracted.strip():
                    sources.append((url, extracted))
                    filenames.append(url)
                if warning:
                    warnings.append(f"{url}: {warning}")
            except Exception as error:
                warnings.append(f"{url}: {error}")
        if company_facts.strip():
            sources.append(("User-provided verified company facts", f"[SOURCE: User Input | Company facts]\n{company_facts.strip()}"))
        chunks = []
        for filename, text in sources:
            chunks.extend(chunk_source(text, filename))
        st.session_state.bf_company_chunks = chunks
        st.session_state.bf_company_facts = company_facts.strip()
        st.session_state.bf_company_filenames = filenames
        st.session_state.bf_company_warnings = warnings
        if st.session_state.bf_tender_text:
            refresh_analysis()
        st.success(f"Indexed {len(chunks)} evidence chunk(s) from {len(sources)} source(s).")
    left, right = st.columns(2)
    with left:
        st.metric("Indexed evidence chunks", len(st.session_state.bf_company_chunks))
    with right:
        st.metric("Source files / links", len(st.session_state.bf_company_filenames))
    for warning in st.session_state.bf_company_warnings:
        st.warning(warning)
    with st.expander("Inspect indexed evidence snippets"):
        for index, chunk in enumerate(st.session_state.bf_company_chunks[:30], start=1):
            st.markdown(f"**{index}. {chunk['source']}**")
            st.write(chunk["text"][:700])
    query = st.text_input("Search company evidence", placeholder="Example: ISO certification, comparable projects, cloud security")
    if query:
        results = retrieve(query, st.session_state.bf_company_chunks, top_k=5)
        if results:
            for result in results:
                with st.expander(f"{result['source']} · relevance {result['score']}"):
                    st.write(result["text"])
        else:
            st.info("No indexed company excerpt matched those terms.")
    st.caption("V1 uses in-memory BM25 lexical retrieval (RAG). Matching suggests relevance only; it does not prove a requirement is met.")


with tabs[3]:
    st.markdown('<div class="bf-title">Bid builder</div><div class="bf-muted">Choose sections, supply optional pricing and format constraints, and generate a sourced draft.</div>', unsafe_allow_html=True)
    section_options = [
        "Tender analysis and key facts", "Eligibility review", "Compliance checklist",
        "Scope, methodology, and technical proposal", "Project plan and team placeholders",
        "Financial bid structure", "Missing documents checklist", "Risk analysis",
        "Clarification questions", "Final bid-readiness report",
    ]
    selected_sections = st.multiselect("Sections to draft", section_options, default=section_options, key="bf_sections")
    with st.expander("Pricing inputs and issuer format", expanded=False):
        price_file = st.file_uploader("Import pricing CSV (optional)", type=["csv"], key="bf_price_csv")
        if "bf_pricing" not in st.session_state:
            st.session_state.bf_pricing = pd.DataFrame(columns=["Resource", "Unit", "Quantity", "Rate", "Currency"])
        if price_file:
            try:
                st.session_state.bf_pricing = pd.read_csv(price_file)
            except Exception as error:
                st.warning(f"Could not read pricing CSV: {error}")
        pricing = st.data_editor(st.session_state.bf_pricing, num_rows="dynamic", use_container_width=True, key="bf_pricing_editor")
        st.session_state.bf_pricing = pricing
        price_format = st.text_area("Pricing assumptions / tender pricing format", height=70, key="bf_price_notes")
        template_notes = st.text_area("Required headings, templates, page limits, file naming", height=75, key="bf_template_notes")
        if not pricing.empty:
            arithmetic = check_pricing_arithmetic(pricing.to_dict(orient="records"))
            check_frame = pd.DataFrame(arithmetic)
            if not check_frame.empty:
                st.caption("Arithmetic helper — calculations use only entered Quantity × Rate. Verify currency, tax, and totals.")
                st.dataframe(check_frame, use_container_width=True, hide_index=True)
    if not st.session_state.bf_tender_text:
        st.warning("Load a tender in the Tender Analysis tab before generating a bid.")
    api_key = api_key_from_secrets()
    if not api_key:
        st.warning("Add GROQ_API_KEY under Streamlit Cloud → App settings → Secrets before using AI drafting.")
    if st.button("Analyze tender and prepare draft", type="primary", use_container_width=True, key="bf_generate"):
        if not api_key:
            st.error("GROQ_API_KEY is missing from Streamlit Secrets.")
        elif not st.session_state.bf_tender_text.strip():
            st.warning("Load the tender document first.")
        elif not selected_sections:
            st.warning("Choose at least one response section.")
        else:
            with st.spinner("Running requirement extraction, RAG evidence matching, risk checks, and CrewAI drafting…"):
                analysis = refresh_analysis()
                pricing_csv = pricing.to_csv(index=False) if not pricing.empty else ""
                context = build_draft_context(analysis, pricing_csv, template_notes + "\n" + price_format)
                try:
                    draft = draft_response(api_key, context, selected_sections, get_memory())
                    st.session_state.bf_draft = draft
                    st.session_state.bf_draft_saved = draft
                    add_to_memory(f"A bid draft was generated for {st.session_state.bf_tender_name or 'the current tender'}. Verify every claim and placeholder against source records.")
                    st.success("Draft generated. Review the compliance and evidence tabs before submission.")
                except Exception as error:
                    detail = str(error)
                    if "RateLimitError" in detail or "rate_limit_exceeded" in detail:
                        st.warning("Groq's token-per-minute limit was reached. Wait for the interval shown in the error, then retry with fewer sections selected.")
                    else:
                        st.error("BidForge could not complete the CrewAI draft. Check GROQ_API_KEY and the deployment logs.")
                    with st.expander("Technical details"):
                        st.code(detail)


with tabs[4]:
    st.markdown('<div class="bf-title">Compliance, eligibility, and risks</div><div class="bf-muted">Review each local requirement candidate and the company evidence retrieved for it. No status means confirmed compliance.</div>', unsafe_allow_html=True)
    analysis = st.session_state.bf_analysis
    if analysis:
        matrix = st.session_state.bf_matrix
        linked = analysis["linked_requirements"]
        potential = sum(1 for item in linked if item["evidence"])
        missing = len(linked) - potential
        c1, c2, c3 = st.columns(3)
        metric(c1, "Requirement candidates", str(len(linked)), "Extracted from tender wording")
        metric(c2, "Potential evidence matches", str(potential), "Review source excerpts before marking compliant")
        metric(c3, "No matching excerpt", str(missing), "Evidence may exist outside uploaded materials")
        if st.session_state.bf_matrix_editing:
            edited = st.data_editor(
                matrix, num_rows="dynamic", use_container_width=True, hide_index=True,
                key="bf_matrix_editor",
                column_config={"Status": st.column_config.SelectboxColumn(
                    "Status", options=["Potential evidence — verify", "Missing evidence", "Compliant (human confirmed)", "Not applicable", "Needs review"]
                )},
            )
            save, cancel = st.columns(2)
            with save:
                if st.button("Save compliance edits", type="primary", key="bf_save_matrix"):
                    st.session_state.bf_matrix = edited
                    st.session_state.bf_matrix_editing = False
                    st.rerun()
            with cancel:
                if st.button("Cancel edits", key="bf_cancel_matrix"):
                    st.session_state.bf_matrix_editing = False
                    st.rerun()
        else:
            if matrix.empty:
                st.info("No requirement candidates were detected. Review the full tender and add missing items manually.")
            else:
                st.dataframe(matrix, use_container_width=True, hide_index=True)
                edit, download = st.columns(2)
                with edit:
                    if st.button("Edit compliance register", type="primary", key="bf_edit_matrix"):
                        st.session_state.bf_matrix_editing = True
                        st.rerun()
                with download:
                    st.download_button("Download register CSV", matrix.to_csv(index=False), file_name="bidforge_compliance_register.csv", mime="text/csv", key="bf_download_matrix")
        with st.expander("Eligibility candidates"):
            eligible = analysis["eligible_requirements"]
            if eligible:
                for item in eligible:
                    st.markdown(f"- {item['requirement']}  \n  _{item['source']}_")
            else:
                st.info("No clear eligibility lines were detected. Check the tender eligibility section manually.")
        with st.expander("Missing-document candidates"):
            docs = analysis["document_requests"]
            if docs:
                for document in docs:
                    st.markdown(f"- [ ] {document}")
            else:
                st.info("No likely document attachment requests were detected by the local scan. Review the tender's mandatory-document list.")
        with st.expander("Risk review flags", expanded=True):
            risks = analysis["risks"]
            if risks:
                for risk in risks:
                    st.markdown(f"**{risk['level']} · {risk['risk']}** — {risk['action']}")
            else:
                st.success("No configured risk terms were detected. Review the complete tender and contract manually.")
    else:
        st.info("Load and analyze a tender in the Tender Analysis tab first.")


with tabs[5]:
    st.markdown('<div class="bf-title">Response document</div><div class="bf-muted">Edit, preview, and export the generated Markdown draft.</div>', unsafe_allow_html=True)
    st.caption("Drafts and edits are held in the current Streamlit session. They are cleared when the session ends or the app restarts.")
    if not st.session_state.bf_draft:
        st.info("Generate a draft in Bid Builder to see it here.")
    else:
        st.markdown('<span class="bf-ai">AI DRAFT · HUMAN REVIEW REQUIRED</span>', unsafe_allow_html=True)
        left, right = st.columns([1, 1], gap="large")
        with left:
            edited_text = st.text_area("Draft in Markdown", value=st.session_state.bf_draft_saved or st.session_state.bf_draft, height=620, key="bf_document_editor")
            if st.button("Save draft edits", type="primary", key="bf_save_draft"):
                st.session_state.bf_draft_saved = edited_text
                st.success("Draft edits saved for this session.")
        with right:
            st.markdown("**Formatted preview**")
            with st.container(border=True):
                st.markdown(edited_text)
        final_text = st.session_state.bf_draft_saved or st.session_state.bf_draft
        markdown_col, docx_col, pdf_col = st.columns(3)
        with markdown_col:
            st.download_button("Download Markdown", final_text, file_name="bidforge_response.md", mime="text/markdown")
        with docx_col:
            st.download_button("Download DOCX", to_docx(final_text), file_name="bidforge_response.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        with pdf_col:
            st.download_button("Download PDF", to_pdf(final_text), file_name="bidforge_response.pdf", mime="application/pdf")
    with st.expander("Session memory and preferences"):
        st.caption(f"{len(get_memory())} note(s) saved in this browser session.")
        memory_note = st.text_input("Add a verified session note", placeholder="Example: use PKR as the bid currency", key="bf_memory_note")
        add_col, clear_col = st.columns(2)
        with add_col:
            if st.button("Save note", key="bf_add_memory") and memory_note.strip():
                add_to_memory(memory_note.strip())
                st.rerun()
        with clear_col:
            if st.button("Clear session memory", key="bf_clear_memory"):
                reset_memory()
                st.rerun()

st.caption("Source evidence = uploaded or public source text · User input = facts/prices provided by you · AI draft = generated wording · Verify all content against the original tender and company records.")
