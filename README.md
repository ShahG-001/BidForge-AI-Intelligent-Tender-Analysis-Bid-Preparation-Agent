# BidForge AI — Tender Intelligence & Bid Preparation

**From Tender Documents to Bid-Ready Intelligence.**

BidForge AI is a beginner-friendly Streamlit app that reads a tender, extracts requirement candidates, retrieves relevant excerpts from company evidence, builds an editable compliance register, flags risks and evidence gaps, and drafts selected response sections with Groq's `openai/gpt-oss-120b` through CrewAI.

## What V1 does

- Accepts PDF, DOCX, TXT, Markdown, and CSV tender and company files, plus pasted text and public HTTP(S) pages/PDFs.
- Adds source labels and PDF page / DOCX paragraph markers where extractable.
- Finds likely requirements, eligibility items, dates, attachment requests, and risk clauses using transparent Python rules.
- Chunks company evidence and retrieves relevant excerpts for each tender candidate using a lightweight BM25 lexical RAG retriever.
- Builds an editable compliance register with evidence excerpts and **potential match / missing evidence** statuses. A lexical match is never presented as proof of compliance.
- Calculates line totals only when the user provides numeric quantity and rate.
- Drafts chosen sections through one CrewAI agent using the retrieved source material.
- Keeps review notes, generated draft edits, and uploaded evidence in the current Streamlit session.
- Exports the generated or edited response as Markdown, DOCX, or PDF.

## V1 design choices

The company evidence retriever is a small in-memory BM25-style lexical index written in `bidforge/rag.py`. It demonstrates retrieval-augmented generation without a separate vector database, embedding provider, or local model download. Evidence is re-indexed when uploaded and cleared when the app session ends. This keeps the first deployment light and easier to troubleshoot. A persistent vector database can be added later if multi-user, long-term document storage is needed.

The CrewAI agent does not call tender text through LLM tool-call arguments. BidForge runs source scanning, retrieval, arithmetic, and risk checks in Python first, then gives their results to the CrewAI drafting task. This makes long source text safer to process through Groq's chat endpoint.

## Project structure

```text
bidforge-ai/
├── app.py
├── requirements.txt
├── README.md
├── .streamlit/
│   └── config.toml
├── assets/
│   └── bidforge-logo.png
└── bidforge/
    ├── __init__.py
    ├── agent.py
    ├── analysis.py
    ├── document_reader.py
    ├── exports.py
    ├── memory.py
    ├── rag.py
    ├── tools.py
    └── web_reader.py
```

## Set up in GitHub using the browser

No local Python installation is needed to upload and deploy the project.

1. Open your GitHub repository.
2. Use **Add file → Create new file** for text files. Enter each full path from the structure above, such as `bidforge/rag.py` or `.streamlit/config.toml`, and paste in that file's code.
3. To add the logo, use **Add file → Upload files** and upload `bidforge-logo.png` into the `assets` folder. Keep the exact name and capitalization.
4. Replace the repository's existing files with the matching files from this project. Commit your changes to the deployment branch (usually `main`).

## Deploy on Streamlit Community Cloud

1. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) and choose **Create app**.
2. Select your GitHub repository, branch, and the root entrypoint `app.py`.
3. In **Advanced settings**, select **Python 3.12**. Streamlit Cloud's app settings include a Python version selector, and the version cannot be changed after the app is deployed without redeploying it.
4. Add the Groq key in the **Secrets** field. Do not put the key in `app.py` or commit it to GitHub:

   ```toml
   GROQ_API_KEY = "paste-your-real-groq-key-here"
   ```

5. Deploy. A later commit to the selected branch triggers a redeployment.

Streamlit Community Cloud reads Python packages from the root `requirements.txt`; `.streamlit/config.toml` must live at the repository root under the `.streamlit` folder. See the [official dependency guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies) and [deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## Suggested demo workflow

1. Upload or paste a sample tender in **Tender Analysis** and select **Load tender source**.
2. Click **Analyze requirements, dates, and risks**.
3. In **Company Evidence**, upload a profile, certificates, CVs, and past project references; add only verified company facts, then click **Index company evidence**.
4. Review the evidence search results, compliance register, potential eligibility items, missing-document candidates, and risk flags.
5. In **Bid Builder**, choose the desired response sections, provide any rates/format notes, and select **Analyze tender and prepare draft**.
6. Edit the draft and download Markdown, DOCX, or PDF in **Documents**.

## Important safeguards and limitations

- Requirement and eligibility rows are candidates detected from text. Check them against the full original tender and add any missed conditions manually.
- RAG matches are lexical relevance scores, not semantic proof. Open each cited source and verify that it supports the requirement.
- A scanned PDF without selectable text is not OCR-processed in this starter build. Upload a searchable copy or paste the relevant text.
- Public URL import does not sign in or follow redirects. Some sites block automated requests. Import only publicly accessible sources you are authorized to use.
- Tender and company text submitted for drafting is sent to Groq. Do not upload confidential material unless your organization permits that processing.
- Session memory, evidence, and edited drafts are temporary. Add authentication and a managed database before multi-user or long-term storage.
- Financial outputs must use user-provided prices. Verify arithmetic, taxes, currency, and totals.
- Legal, insurance, bid security, and contractual clauses require qualified human review. BidForge does not provide legal advice.
- DOCX/PDF downloads use a basic layout and do not reproduce an issuer's exact form or guarantee its page limits.
- Every generated response is a draft and needs human approval before submission.
