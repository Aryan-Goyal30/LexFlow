# Candidate judgment source: Indian Supreme Court Judgments (open dataset)

Status: **candidate only (2026-10-25). Not approved, not downloaded, not
imported.**
- No licence terms were accepted.
- This is a desk review of public pages, not legal advice. Whether LexFlow
  may store and search the corpus is for the owner to decide, ideally with
  a lawyer's review (Phase 4 plan, Gate 2; register R4).

## 1. What was checked, and how

Read on 2026-10-25 with a web fetch; nothing was downloaded from the bucket.

| Source | Kind | Result |
|---|---|---|
| <https://registry.opendata.aws/indian-supreme-court-judgments/> | AWS Open Data registry entry | read |
| <https://github.com/vanga/indian-supreme-court-judgments> (README) | maintainer's repository | read |
| `.../blob/main/LICENSE.md` | licence file | read |
| `.../blob/main/opendata/docs/dataset.md` | dataset documentation (marked "OUTDATED" by the maintainer) | read |
| <https://scr.sci.gov.in/> | the upstream portal named as the source | home page read. Its "Terms and Conditions", "Copyright Policy" and "Disclaimer" pages were **not** read |
| <https://www.sci.gov.in/website-policies/> | Supreme Court website policies | **HTTP 403**, not read |
| India Code (Copyright Act 1957, s. 52); copyright.gov.in exceptions page | statute (primary) | **HTTP 403** and a redirect, not read |

## 2. Verified facts (from the pages above)

- **Name and steward:** "Indian Supreme Court Judgments". The registry
  names Dattam Labs (dattam.in, contact@dattam.in) as manager. The code and
  documentation are in the GitHub account `vanga`.
- **Stated origin:** "downloaded from ecourts website". The dataset
  documentation links <https://scr.sci.gov.in>. That portal, "Judgements and
  Orders, Supreme Court and High courts of India", says it is "designed,
  hosted and maintained by National Informatics Centre (NIC)". Its search
  form has a CAPTCHA.
- **Licence statement:** the registry says "CC-BY-4.0". The README says "The
  data is licensed under Creative Commons Attribution 4.0 (CC-BY-4.0)".
  `LICENSE.md` appears to be the standard CC BY 4.0 legal code, with no
  additions. It **names no licensor**, and it does not say whether it covers
  the code, the metadata, the judgment files, or all three.
- **Requested citation (registry):** "Indian Supreme Court Judgments was
  accessed on DATE from
  https://registry.opendata.aws/indian-supreme-court-judgments."
- **Coverage:**
  - judgments from 1950 to 2025 (the README says "1950 to Present");
  - about 35,000 judgments in English, some with regional-language
    versions;
  - about 52.24 GB in total.
- **Updates:** "Bi-monthly" (registry); "Twice every month" (dataset
  documentation).
- **Access:** a public S3 bucket, `arn:aws:s3:::indian-supreme-court-judgments`
  (`ap-south-1`), with no AWS account needed. The maintainers recommend the
  per-year tar archives and parquet files for bulk use.
- **Layout per year:**
  - `data/pdf/year=YYYY/english/*.pdf` and `.../regional/*.pdf`;
  - `data/tar/year=YYYY/english/english.tar` (or `part-*.tar`), with
    `*.index.json` describing each tar's contents;
  - `metadata/json/year=YYYY/*.json` (raw metadata);
  - `metadata/parquet/year=YYYY/metadata.parquet`.
- **Parquet columns (README):** `title`, `petitioner`, `respondent`,
  `description`, `judge`, `author_judge`, `citation`, `case_id`, `cnr`,
  `decision_date`, `disposal_nature`, `court`, `available_languages`,
  `raw_html`, `path`, `nc_display`, `scraped_at`, `year`.
- **Maintainers' request:** "Avoid scraping with high concurrency" (of the
  eCourts site). An older version of the data is on Kaggle.
- **Not stated anywhere read:** known data-quality issues, de-duplication
  rules, redaction or anonymisation, any privacy statement, or a
  disclaimer.

## 3. Secondary information (not verified against the primary text)

- **Copyright Act 1957, s. 52(1)(q)(iv)**, as reproduced by secondary
  sources: reproducing or publishing "any judgment or order of a Court,
  Tribunal or other judicial authority" is not infringement, unless that
  court or authority has prohibited it. The Supreme Court in *Eastern Book
  Company v. D.B. Modak* (2008) is reported to hold that anyone may publish
  judgments, while a publisher's own editorial additions (headnotes and the
  like) can attract copyright.
- **Bharatiya Nyaya Sanhita s. 73** (formerly IPC s. 228A), as reported: it
  restricts publishing proceedings that identify victims of certain sexual
  offences, but printing a High Court or Supreme Court judgment is said not
  to be an offence under that section.

A lawyer should confirm both points against the official text.

## 4. Unresolved questions (legal or factual; for the owner and a lawyer)

1. **What does CC BY 4.0 cover here?** A licence can only grant rights the
   licensor holds. If the judgment texts themselves may be reproduced under
   s. 52(1)(q)(iv), the licence matters mainly for the compiled metadata and
   any work the maintainers added. Who is the licensor: Dattam Labs, or the
   repository owner?
2. **Upstream terms.** Do the terms, copyright policy and disclaimer of
   scr.sci.gov.in or sci.gov.in restrict reuse, bulk storage or commercial
   use, or require attribution? (The sci.gov.in copyright policy reportedly
   begins "The contents on this website shall not be reproduced partially or
   fully, without duly & prominently a…", cut off in the snippet; the full
   text was not read.) Was the collection made in line with those terms (the
   portal uses a CAPTCHA)?
3. **Court prohibitions.** The s. 52 exception does not apply where a court
   has prohibited publication. How would LexFlow detect and exclude such
   judgments, or ones later withdrawn or corrected?
4. **Personal data in judgments.** Judgments name parties, witnesses and,
   in older cases, sometimes victims or minors. How does storing and
   showing them inside LexFlow fit the DPDP Act 2023 and its rules (including
   any exemption for publicly available data) and court directions on
   anonymity? See `PRIVACY_REVIEW_CHECKLIST.md`.
5. **Commercial use.** If LexFlow is used in a paid practice, does anything
   in the upstream terms limit that?
6. **Authenticity and fidelity.** Are the PDFs the Court's own documents,
   unmodified? Do the `citation` and `nc_display` (neutral citation) fields
   match the official reports? (Check on a sample.)
7. **Attribution in LexFlow.** Is the registry citation plus a CC BY notice
   (licence link, licensor, "changes made", e.g. text extraction and
   chunking) enough? Should it appear on every passage, on the judgment page,
   or in an "about the collection" page?

## 5. Suitability for LexFlow (engineering view)

**Fits:**
- `path`, `cnr`, `case_id`, `decision_date` and `scraped_at` give per-judgment
  provenance and a natural de-duplication key (`cnr`). This fits the Phase 4
  importer, which already requires a terms URL, the date checked, who
  checked and the permitted use (`judgment_sources`), and de-duplicates by
  citation and SHA-256.
- PDFs go through the existing Phase 3 extractors.
- English text suits the current English full-text configuration and the
  local `bge-small-en` model.

**Limits:**
- **Supreme Court only.** Many matters a practice handles turn on High Court
  and trial-court law. A separate High Court dataset on the same registry
  would need its own review.
- About 35,000 judgments is far more than the brief's first set ("a few
  hundred judgments in one or two areas"). A subset by practice area would
  have to be chosen, and the metadata has no practice-area field (the
  `description` or `disposal_nature` fields might help; unverified).
- Scanned or old PDFs may extract poorly. Regional-language versions are out
  of scope for the current search.

**Process limit:** the Phase 4 plan says LexFlow does not crawl or download;
the owner supplies files and a manifest. If approved, the owner would fetch
**only the chosen subset** (for example one year's parquet file, then the
named PDFs) and place it locally for the importer.

## 6. Recommendation

- **Keep it as the leading candidate.** It is openly published, says which
  licence it uses, and carries the provenance fields LexFlow needs.
- **Do not approve it until questions 1–4 are answered** by the owner with a
  lawyer's review, and the upstream portal's terms are read in full and
  recorded (URL, date, reader, what they permit) in the form
  `judgment_sources` needs.
- Then pilot with one practice area and a small subset (a few hundred
  judgments, per the brief), recording the attribution decided in question
  7.
- Until then the live collection keeps only the 3 labelled SYNTHETIC demo
  judgments.
