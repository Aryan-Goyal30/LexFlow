# Candidate corpus `sci-tm-v1`: genuine Supreme Court trade mark judgments

**Date:** 2026-10-25.

**Status:** acquired and checked; **not imported** anywhere. Importing waits
for the owner's approval of this specific dataset (section 8).

This is not legal advice. Every metadata value below is copied from the
judgment's own text, or left blank.

## 1. Summary

- **14 judgments of the Supreme Court of India** on trade marks, passing
  off, prior use and deceptive similarity, decided from 1962 to 2025:
  - **10 directly on point**;
  - **4 on related trade mark law:** jurisdiction for a suit, arbitrability
    of a trade mark assignment, registration, and a trade mark
    assignment/injunction.
- **Where from:** downloaded automatically from the Court's own website
  (`api.sci.gov.in`), at addresses that web search found on the official
  host. **No CAPTCHA was solved or avoided:** no addresses were guessed or
  enumerated, and nothing came from a third-party site.
- **Not e-SCR:** e-SCR offers only a CAPTCHA-protected search, so it was not
  used (section 2). These are the Court's own judgment copies from
  sci.gov.in, under that website's copyright policy, which matches e-SCR's.
- **Below the 20–40 target.** Section 6 lists what could not be obtained,
  and the safest way to obtain it.
- **Location:** the corpus is outside Git, in `server/var/judgments/sci-tm-v1/`:
  - the PDFs;
  - `original/` (the bytes exactly as served);
  - `selection.csv`, `manifest.json` and `inventory.json`;
  - the fetch logs.

  No document was sent to any AI provider or other service.

## 2. What is accessible, and what was not used

The evidence is in `acquisition-evidence/` (raw pages, SHA-256 in
`evidence-manifest.json`).

| Route | Access | Used? |
|---|---|---|
| e-SCR search (`scr.sci.gov.in/scrsearch/`) | Securimage CAPTCHA on every search; no browse or list without it | **No** (CAPTCHA) |
| sci.gov.in judgment search (by date, by case number, by neutral citation) | CAPTCHA | **No** (CAPTCHA) |
| sci.gov.in "Landmark Judgment Summaries", 2017–2026 | Open; each row links "View Judgment" to `/view-pdf/`, which loads `/sci-get-pdf/` with no CAPTCHA | Index read (27 year pages, 125 rows); **no trade mark judgment listed** (one copyright/design case) |
| `api.sci.gov.in/supremecourt/…_Judgement_….pdf` and `api.sci.gov.in/jonew/judis/N.pdf` | Direct PDF, no CAPTCHA, no login | **Yes**, only addresses found by web search on the official host |
| `digiscr.sci.gov.in` | Did not respond | No |

**Limits kept:**
- **robots.txt:** `www.sci.gov.in/robots.txt` disallows only `/wp-admin/`.
  `scr.sci.gov.in` and `api.sci.gov.in` publish no robots rules.
- **Terms:** the policy pages read contain no terms on automated access.
- **No guessing:** no diary number or archive id was guessed or enumerated.
- **Pace:** one request at a time, at least 3 seconds apart, with an
  ordinary browser user agent.
- **Volume:** 40 candidate files, plus a second fetch of 17 of them.

## 3. Integrity

- **Re-fetched and identical:** every selected file was fetched twice. Both
  fetches gave **identical bytes** (`refetch-log.tsv`).
- **Legacy archive prefix:** 6 of the 14 come from the legacy JUDIS archive.
  It serves each PDF with a **4-byte little-endian length prefix**, whose
  value equals the length of the PDF that follows (checked for all 13 such
  candidates).
  - The import copy is the PDF without those 4 bytes.
  - The original as served is kept in `original/`.
  - Both SHA-256 values and the transformation are recorded in each
    judgment's provenance.
- **Extraction:** all 14 extract with the real extractor, with **no empty
  pages** (888,450 characters).

## 4. Metadata: how each value was obtained

- **Title:**
  - as printed on page 1;
  - a script checked that both parties' names occur in the text.
  - For the Coca-Cola judgment, the archive header reads "GUJARAT
    **P**OTTLING CO.LTD.", while the judgment's text names "Gujarat
    Bottling Company Ltd.". The title follows the judgment text.
- **Decision date:**
  - legacy archive: the header's "DATE OF JUDGMENT";
  - current archive: the date on the signature line at the end. It was
    checked against the date in the official file name, and **all 8**
    current-archive files with a date in the name **match**.
- **Neutral citation:** as printed at the head of page 1 (3 judgments). It
  is left blank where none is printed.
- **Other citations:** copied verbatim from the legacy archive's
  "CITATION:" header (3 judgments). These are parallel citations to law
  reports, including third-party reports; only the strings are stored.
- **Left blank as unknown:** bench, and any citation for the 8 judgments
  that print none.
- **Topic tags:** "Intellectual property; Trade marks" is a LexFlow tag,
  not court metadata. The selection reason records the term counts behind
  each choice.

## 5. Inventory

| # | Judgment (as printed) | Decided | Neutral citation | Citation printed in the archive copy | Tier | Archive | Pages | Original SHA-256 (as served) | Import SHA-256 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [Amritdhara Pharmacy v. Satyadeo Gupta](https://api.sci.gov.in/jonew/judis/3855.pdf) | 1962-04-27 | — | 1963 AIR 449 | core | legacy JUDIS | 10 | `8c8f59e1bf9e0aaf…` | `ab93f027284b90a8…` (prefix removed) |
| 2 | [Parle Products (P) Ltd. v. J. P. & Co., Mysore](https://api.sci.gov.in/jonew/judis/6909.pdf) | 1972-01-28 | — | 1972 AIR 1359 1972 SCR (3) 289 1972 SCC (1) 618 | core | legacy JUDIS | 6 | `a47c46f16161ccd7…` | `843dab1e08d0d71a…` (prefix removed) |
| 3 | [M/s Gujarat Bottling Co. Ltd. & Ors. v. The Coca Cola Co. & Ors.](https://api.sci.gov.in/jonew/judis/10657.pdf) | 1995-08-04 | — | 1995 AIR 2372 1995 SCC (5) 545 JT 1995 (6) 3 1995 SCALE (4)635 | related | legacy JUDIS | 26 | `5f2130853086d499…` | `d066def12c140e00…` (prefix removed) |
| 4 | [Whirlpool Corporation v. Registrar of Trade Marks, Mumbai & Ors.](https://api.sci.gov.in/jonew/judis/12950.pdf) | 1998-10-26 | — | — | core | legacy JUDIS | 19 | `acc9ad97c1cfdf21…` | `75afcfade16dfba7…` (prefix removed) |
| 5 | [Milmet Oftho Industries & Ors. v. Allergan Inc.](https://api.sci.gov.in/jonew/judis/26196.pdf) | 2004-05-07 | — | — | core | legacy JUDIS | 3 | `912732815d429f7f…` | `3493637ea535eb5f…` (prefix removed) |
| 6 | [Indian Performing Rights Society Ltd. v. Sanjay Dalia & Anr.](https://api.sci.gov.in/jonew/judis/42728.pdf) | 2015-07-01 | — | — | related | current | 50 | `159d60f9ef82b310…` | `9db7ac8cefd50d2e…` (prefix removed) |
| 7 | [Royal Orchid Hotels Ltd. v. Kamat Hotels (India) Ltd. & Ors.](https://api.sci.gov.in/supremecourt/2015/5357/5357_2015_Judgement_14-Dec-2017.pdf) | 2017-12-14 | — | — | related | current | 10 | `3b1bd8736b1bf78d…` | `3b1bd8736b1bf78d…` |
| 8 | [M/s. Nandhini Deluxe v. M/s. Karnataka Co-operative Milk Producers Federation Ltd.](https://api.sci.gov.in/supremecourt/2015/18014/18014_2015_Judgement_26-Jul-2018.pdf) | 2018-07-26 | — | — | core | current | 47 | `624744063b0e2ff8…` | `624744063b0e2ff8…` |
| 9 | [Wockhardt Limited v. Torrent Pharmaceuticals Ltd. and Anr.](https://api.sci.gov.in/supremecourt/2018/13692/13692_2018_Judgement_12-Sep-2018.pdf) | 2018-09-12 | — | — | core | current | 15 | `da4c1b6c26dc790b…` | `da4c1b6c26dc790b…` |
| 10 | [Renaissance Hotel Holdings Inc. v. B. Vijaya Sai and Others](https://api.sci.gov.in/supremecourt/2019/25790/25790_2019_35_1501_32774_Judgement_19-Jan-2022.pdf) | 2022-01-19 | — | — | core | current | 61 | `dbcbb6d4167b11c6…` | `dbcbb6d4167b11c6…` |
| 11 | [Shyam Sel and Power Limited and Another v. Shyam Steel Industries Limited](https://api.sci.gov.in/supremecourt/2020/10268/10268_2020_35_1501_34100_Judgement_14-Mar-2022.pdf) | 2022-03-14 | — | — | core | current | 46 | `21ce7ca3b2ca6e91…` | `21ce7ca3b2ca6e91…` |
| 12 | [K. Mangayarkarasi & Anr. v. N.J. Sundaresan & Anr.](https://api.sci.gov.in/supremecourt/2025/18603/18603_2025_13_29_61686_Judgement_09-May-2025.pdf) | 2025-05-09 | 2025 INSC 687 | — | related | current | 28 | `255caf9f3b8fbc58…` | `255caf9f3b8fbc58…` |
| 13 | [Pernod Ricard India Private Limited & Another v. Karanveer Singh Chhabra](https://api.sci.gov.in/supremecourt/2023/52688/52688_2023_8_1502_63274_Judgement_14-Aug-2025.pdf) | 2025-08-14 | 2025 INSC 981 | — | core | current | 97 | `e99e0ddaf457cdcb…` | `e99e0ddaf457cdcb…` |
| 14 | [Lifestyle Equities C.V. & Anr. v. Amazon Technologies Inc.](https://api.sci.gov.in/supremecourt/2025/38535/38535_2025_8_1502_64828_Judgement_07-Oct-2025.pdf) | 2025-10-07 | 2025 INSC 1190 | — | core | current | 74 | `9742b9dfa980ab56…` | `9742b9dfa980ab56…` |

**File hashes:**
- `selection.csv`: `c777ea24…498f`;
- `manifest.json`: `cb8c0f79…39b1`;
- `inventory.json`: `ed32e34e…c6ae6`.

**Excluded:**
- **3 peripheral judgments,** where trade marks appear only as background:
  - *Asian Paints v. Ram Babu* (criminal procedure);
  - *Ajanta LLP v. Casio* (correcting a consent decree);
  - *Canara Bank v. N.G. Subbaraya Setty* (res judicata).

  The owner may add them as near-miss distractors for evaluation.
- **23 off-topic candidates:** tax, power, service and other matters that
  web search had wrongly associated with trade mark queries. They were
  checked from their text and discarded.

## 6. Not obtained

These were searched for by name, on the official hosts only, and **no
official copy was found** without the CAPTCHA-protected search.

**Cited by judgments in this corpus** (16), so a court record of the name
exists here:
- *Cadila Health Care v. Cadila Pharmaceuticals*
- *Laxmikant V. Patel v. Chetanbhai Shah*
- *Midas Hygiene Industries v. Sudhir Bhatia*
- *S. Syed Mohideen v. P. Sulochana Bai*
- *Neon Laboratories v. Medical Technologies*
- *Kaviraj Pandit Durga Dutt Sharma v. Navaratna Pharmaceutical Laboratories*
- *Corn Products Refining Co. v. Shangrila Food Products*
- *Satyam Infoway v. Sifynet Solutions*
- *Heinz Italia v. Dabur India*
- *Khoday Distilleries v. Scotch Whisky Association*
- *N.R. Dongre v. Whirlpool Corporation*
- *Ruston & Hornsby v. Zamindara Engineering*
- *S.M. Dyechem v. Cadbury*
- *Power Control Appliances v. Sumeet Machines*
- *T.V. Venugopal v. Ushodaya Enterprises*
- *National Bell Co. v. Metal Goods Mfg. Co.*

**Searched by name only** (4), not confirmed from any official text here:
- *Toyota Jidosha Kabushiki Kaisha v. Prius Auto Industries*
- *K.R. Chinna Krishna Chettiar v. Sri Ambal*
- *Ramdev Food Products v. Arvindbhai Rambhai Patel*
- *Mahendra & Mahendra Paper Mills v. Mahindra & Mahindra*

**Safest way to complete the corpus:** the owner downloads the wanted
judgments by hand from e-SCR or sci.gov.in, solving each CAPTCHA as the
site intends, into the same folder, and adds a row to `selection.csv`.
- For a hand download, the retrieval columns may stay blank, or be filled
  in.
- The adapter and the preview then run unchanged.
- About 10 to 20 judgments would bring the corpus to the 20–40 target.

## 7. Licensing, privacy and other caveats (for the owner and a lawyer)

1. **Reuse basis.** The sci.gov.in copyright policy allows reproduction only
   when the source is "duly & prominently" acknowledged. It excludes:
   - use in a misleading, objectionable or derogatory context;
   - material identified as third-party copyright.

   The attribution text is shown with every judgment (preview, line
   "Attribution"); its final wording is the owner's.
2. **Not a legal document.** The terms say the documents are "for reference
   purposes only and the same do not constitute legal document". LexFlow
   already labels results as text matches, not legal advice.
3. **Headnotes in the legacy archive files** (4 of the 6 carry a
   `HEADNOTE:` block). The file does not say who wrote them. A lawyer
   should confirm they are court or official-report material, not a
   third-party publisher's.
4. **Third-party citations.** Several judgments cite SCC OnLine, AIR and
   SCC reports as citations. Only the citation strings appear; no
   third-party text was found by the scan.
5. **Personal data.**
   - The parties are mainly companies. At least six individuals are
     named as parties in the titles, all in commercial disputes.
   - A keyword scan found no sensitive categories (minors, victims, sexual
     offences, health, caste, contact details). Every hit was examined and
     was figurative or legal ("minor differences").
   - This is a keyword scan, not a full privacy review
     (`PRIVACY_REVIEW_CHECKLIST.md`).
6. **Collection method.** Public addresses on the Court's own host were
   fetched directly. The Court itself links judgments this way
   (`/view-pdf/` and `/sci-get-pdf/`, which need no CAPTCHA).
   - The CAPTCHA protects only the search.
   - No search was run and no address was guessed.

   Whether this collection method is acceptable is the owner's decision.
   The evidence is in section 2.
7. **Redistribution.** The corpus stays outside Git and is not
   redistributed. Displaying the text inside LexFlow, with attribution,
   is the intended use.
8. **Who checked the terms.** The source record names "Claude Code (AI
   assistant)" as the reader of the policy pages. The owner may replace it
   with a named human reviewer before import.

## 8. Approval requested

| Item | Detail |
|---|---|
| Action | Import the 14 judgments of `server/var/judgments/sci-tm-v1/manifest.json` (SHA-256 `cb8c0f79…`) with `python -m lexflow.cli.judgments import … --confirm 14` |
| Target | `lexflow_e2e` (the marked demo database); later the evaluation database. **Never the live `lexflow`** (still at 0012) |
| Data | 14 public Supreme Court judgments (PDF, English); no client data; nothing sent to an external service |
| Preview | `import-preview-sci-tm-v1.md`: 14 new, 0 duplicate, 0 invalid; read-only, rolled back |
| Cost | None |
| Reversal | `python -m lexflow.cli.judgments remove --source sci-judgments` |
| Open decisions | Add the 3 peripheral judgments? Complete the corpus by hand (section 6)? Final attribution wording, and a named terms reviewer |
