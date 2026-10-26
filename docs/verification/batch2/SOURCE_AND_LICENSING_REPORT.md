# Genuine Indian judgments: source and licensing report (Batch 2)

**Date:** 2026-10-25. **Status:** findings and a recommendation for the
owner. **No judgment has been downloaded or imported.** This is not legal
advice. Whether LexFlow may store and search a corpus is the owner's
decision, ideally after a lawyer reads the evidence below (register R4).

## 1. Method and evidence

The primary pages were fetched on 2026-10-25 and saved **raw**
(HTML/Markdown/YAML, not summaries) in `source-evidence/`.
`evidence-manifest.json` records the URL, HTTP status, size and SHA-256 of
each file.

The earlier assessment (`docs/phase7-prerequisites/SOURCE_CANDIDATE_SCI_JUDGMENTS.md`)
could only report claims, because those pages were unreachable (403) or not
saved. Here, the official portals' policy pages were reachable with an
ordinary browser user agent, and are preserved.

**Not reachable:** India Code (the Copyright Act's official text) timed out
twice, so section 52 below is from secondary sources.

## 2. Verified findings (from the saved primary pages)

### 2.1 Official portals: e-SCR and the eCourts judgment search

These are `scr.sci.gov.in` (Supreme Court Reports) and
`judgments.ecourts.gov.in` (High Courts). Files: `scr-footer-*.html`,
`ecourts-footer-*.html`, `sci-website-policies.html`.

- **Copyright policy** (identical wording on both portals, and on
  sci.gov.in):

  > "The contents on this website shall not be reproduced partially or
  > fully, without duly & prominently acknowledging the source. The contents
  > of this website cannot be used in any misleading or objectionable
  > context or derogatory manner. However the permission to reproduce the
  > material available on the e-Courts website shall not extend to any
  > material which is identified as being copyright of a third party.
  > Authorization to reproduce such material must be obtained from the
  > Courts Concerned."

  Reproduction is therefore **permitted with a prominent acknowledgement of
  the source**, with two exclusions:
  - no use in a misleading, objectionable or derogatory context;
  - third-party copyright material.
- **Terms and conditions:** the documents are "for reference purposes only
  and do not purport to a legal document … should not be construed as a
  statement of law or used for any legal purposes"; verify with the
  eCommittee, Supreme Court of India.
- **Disclaimer (e-SCR):**
  - The Editorial Section of the Supreme Court prepares the English version.
  - **Hindi judgments "as published in Ucchtam Nyayalya Nirnay Patrika are
    reproduced under approval of Vidhi Sahitya Prakashan"**: plausibly
    third-party material.
  - Translations "shall have no legal effect".
- **About (e-SCR):** "Supreme Court Reports (SCR) is the official
  publication of Supreme Court of India … e-SCR is the digital version".
- **Access:** the search and PDF download use a CAPTCHA (`scr-home.html`).
  Neither portal offers a bulk download.

### 2.2 The AWS Open Data datasets (Dattam Labs)

Files: `aws-registry-sci.yaml`, `sci-dataset-README.md`,
`sci-dataset-LICENSE.md`, `aws-registry-hc.yaml`, `hc-dataset-README.md`,
`sci-download.py`.

- **Supreme Court dataset:**
  - registry licence "CC-BY-4.0", ManagedBy Dattam Labs, contact
    contact@dattam.in;
  - "downloaded from ecourts website", 1950–2025, about 35,000 English
    judgments, about 52 GB;
  - per-year PDFs and tar archives, raw JSON metadata and structured Parquet
    metadata.
- **High Court dataset:**
  - CC-BY-4.0, 25 High Courts, 17.8 million judgments, about 1.25 TiB;
  - **"Judgments from the website are further compressed"**: the PDFs are
    *not* the court's original bytes.
- **Licence file:** the standard CC BY 4.0 legal code. **It names no
  licensor**, and does not say what it covers (code, metadata, judgment
  files).
- **How the Supreme Court data was collected** (`sci-download.py`, lines
  494–600). The scraper:
  - **automatically solves the portal's CAPTCHA**: it downloads the image,
    reads it by OCR, evaluates math CAPTCHAs, and retries up to 10 times;
  - does the same for the PDF download CAPTCHA
    (`solve_pdf_download_captcha`);
  - makes requests with `verify=False` (TLS verification off).

  The README asks users not to scrape with high concurrency.
- **Raw metadata JSON per judgment** (from the code):
  - `raw_html` (the portal's result row);
  - `path`, `citation_year`, `nc_display` (neutral citation), `scraped_at`.
- **The Parquet columns** (from the README) add `title`, `petitioner`,
  `respondent`, `judge`, `citation`, `case_id`, `cnr`, `decision_date`,
  `disposal_nature`.

### 2.3 Indian Kanoon API

Files: `indiankanoon-api-*.html`, `indiankanoon-disclaimer.html`.

- **Paid, prepaid:**
  - INR 0.50 per search or original document;
  - INR 0.20 per document, 0.05 per fragment, 0.02 per metadata request;
  - Rs 500 free test credit;
  - Rs 10,000 a month for verified non-commercial use.
- **Attribution required** for every use, *including RAG context and
  fine-tuning*: a "powered by IKanoon" logo shown conspicuously.
- **Data:** "sourced through public websites"; HTML "enriched with various
  machine learned classifications" (Indian Kanoon's own work, not the
  court's). Provided "AS IS".
- **Disclaimer:** court orders are downloaded by a crawler. Victim and
  juvenile identities are redacted in certain categories, and orders are
  removed on court order.
- **Not stated** in the pages read: any right to *store* or *redistribute*
  documents outside the API's display use.

## 3. Secondary and unverified points (for a lawyer)

- **Copyright Act 1957, s. 52(1)(q)(iv)**, as reproduced by secondary
  sources: reproducing or publishing "any judgment or order of a Court,
  Tribunal or other judicial authority" is not infringement unless that
  court prohibits it. *Not checked against the official text*, because
  India Code timed out.
- **Whether reusing data that a third party collected by automated CAPTCHA
  solving is acceptable.** The content itself is reproducible under the
  portals' copyright policy; the collection method circumvented an access
  control the portal chose to use. This is an ethical and legal judgment for
  the owner, not something the evidence settles.
- **What CC-BY-4.0 covers**, and who the licensor is (section 2.2).
- **Publication bans and personal data** (victims, juveniles) in judgments,
  and the DPDP Act position. See `docs/phase7-prerequisites/PRIVACY_REVIEW_CHECKLIST.md`.

## 4. Assessment of the candidates

| Candidate | Authenticity | Reuse basis (verified) | Main concerns | Fit for a first corpus |
|---|---|---|---|---|
| **A. Official e-SCR PDFs, downloaded manually by a person** | Highest: the court's own official report | Copyright policy: reproduce with prominent acknowledgement | Manual effort; a CAPTCHA per download (solved by the person, as intended); "for reference only" | **Recommended**: small, authentic, no automation |
| B. The AWS Supreme Court dataset, targeted files | High, but not verified against the official copy | "CC-BY-4.0" (maintainer's statement); underlying content under the portal policy | **Collected by automated CAPTCHA solving**; licensor and scope unclear; regional versions possibly third-party | Possible after the owner decides on the collection-method question; check a sample against e-SCR |
| C. The AWS High Court dataset | PDFs re-compressed, not original bytes | As B | As B, plus very large and not the original files | Not for the first corpus |
| D. Indian Kanoon API | Copies plus Indian Kanoon's enrichments | Paid API terms; attribution logo required | Cost; storage and redistribution rights not stated; enrichments are not court content | Not recommended for a stored corpus |
| E. LexFlow scraping the portals | — | — | CAPTCHA and access controls; plan rule 11 | **Excluded** |

## 5. Recommendation: the initial corpus

**Option A, small and official.** The owner (or a lawyer) downloads
**20–40 English judgments of the Supreme Court of India** from e-SCR
(`https://scr.sci.gov.in`) **by hand**, through the ordinary search.

- **Topic:** chosen to match the fictional demo matter, so retrieval can be
  evaluated against it: trade marks, passing off, prior use and deceptive
  similarity. Suggested e-SCR search terms are "Trade Marks Act",
  "passing off", "prior user" and "deceptive similarity".
- **Not named here:** this report deliberately names no specific judgment.
  The selection is the person's, and recorded with who chose it and why.
- **English only:** exclude regional and Hindi versions, which are
  plausibly third-party material (2.1).
- **Metadata,** entered from the e-SCR record into a CSV:
  - title, court, decision date, SCR citation, neutral citation;
  - the official URL or the search route.

  Unknown values stay blank, never guessed.
- **Attribution** shown with every judgment in LexFlow: "Source: Supreme
  Court of India, Supreme Court Reports (e-SCR), scr.sci.gov.in. Reproduced
  with acknowledgement under the portal's copyright policy. For reference
  only; not a legal document." (The final wording is the owner's.)
- **Source record** (`judgment_sources`):
  - terms URL: the e-SCR copyright policy URL;
  - checked on 2026-10-25, by the owner's named reviewer;
  - permitted use: quoting the policy (2.1).

Option B can be considered later, for scale, once the owner decides on the
CAPTCHA-collection question and a sample is checked byte for byte against
e-SCR.

## 6. The action that needs approval

| Item | Detail |
|---|---|
| Action | The owner places the chosen e-SCR PDFs and a filled `selection.csv` in a local folder; `scripts/prepare_official_judgments.py` builds a manifest (no network); `python -m lexflow.cli.judgments import <manifest>` previews, then imports |
| Target database | First the **demo or evaluation database** (`lexflow_e2e`, or a dedicated `lexflow_eval_test`), for retrieval evaluation. **Not the live `lexflow`**, which stays at 0012 until a separate migration approval |
| Data | 20–40 public Supreme Court judgments (PDF, English); no client data |
| Cost | None (manual download, local import) |
| Risks | Personal data of parties in public judgments; publication bans; reliance on judgments "for reference only" |
| Verification | The import plan shows every file's SHA-256; provenance stored per judgment; a sample re-checked against e-SCR; "genuine" badge and attribution visible; the retrieval evaluation in `docs/verification/batch2/` |

**Until approval**, LexFlow ships the tooling (manifest v2 with provenance,
an import-run record, the CSV adapter, genuine and synthetic labelling, and
the evaluation framework) tested on fictional fixtures only.

## 7. Addendum (2026-10-25): automated acquisition from official links

The owner asked for automated acquisition wherever it is technically and
legally permitted. Findings:
- **e-SCR:** has only a CAPTCHA-protected search, so it was not used.
- **sci.gov.in judgment search** (by date, by case number, by neutral
  citation): also CAPTCHA-protected.
- **The Court's own PDF links are not CAPTCHA-protected.** That covers its
  "View Judgment" links (`/view-pdf/` → `/sci-get-pdf/`) and both archives
  on `api.sci.gov.in`.
- **robots.txt:** `www.sci.gov.in` disallows only `/wp-admin/`; the other
  hosts publish no robots rules.
- **sci.gov.in website policies:** the same copyright policy as e-SCR, plus
  terms saying the documents "are for reference purposes only and the same
  do not constitute legal document". Nothing on automated access.

**Result:**
- 14 on-topic judgments were fetched at addresses that web search found on
  the official host.
- No CAPTCHA was solved, and no address was guessed.
- Inventory, integrity, metadata method, caveats and the approval request:
  `CORPUS_sci-tm-v1.md`.
- Dry run: `import-preview-sci-tm-v1.md`.
- Access evidence: `acquisition-evidence/`.

**Recommendation update.** Option A stays the recommendation, now in two
parts:
1. this verified sci.gov.in set, under a new source profile
   (`sci-judgments`);
2. the remaining wanted judgments downloaded by hand, through the CAPTCHA,
   as the sites intend.

Nothing has been imported.
