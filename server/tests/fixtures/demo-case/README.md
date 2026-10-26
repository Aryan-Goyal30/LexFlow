# FICTIONAL demo case pack

**Every file here is invented** for LexFlow demonstrations and tests: the
people, firms, brands, products, places, court, registration number and case
number are fictional. Nothing here is a real legal record, and nothing may be
cited.

Each document opens with its own title marked FICTIONAL. Every PDF page, and the
end of every other file, carries the full notice "FICTIONAL DOCUMENT - created
for LexFlow demonstrations. Not a real legal record." and the case reference.
(The notice is at the foot so that passages quoted from the start of each
document differ from one document to the next.)

The matter: *Velorindra Foods LLP v. Tamsinwick Snacks Private Limited
(FICTIONAL)*. The plaintiff owns the registered mark KESORA for millet snacks
and sues over the mark KESORRA for infringement and passing off.

| File | Kind | Date | Text |
|---|---|---|---|
| `01-plaint.pdf` | pleading | 15 Apr 2026 | 3 pages (PDF text layer) |
| `02-affidavit-head-of-sales.pdf` | evidence (Exhibit P-2) | 10 Apr 2026 | 2 pages |
| `03-exhibit-p3-sales-ledger.txt` | evidence (Exhibit P-3) | 8 Apr 2026 | plain text |
| `04-cease-and-desist-notice.txt` | correspondence | 10 Feb 2025 | plain text |
| `05-reply-to-notice.docx` | correspondence | 28 Feb 2025 | Word |
| `06-written-statement.docx` | pleading | 20 May 2026 | Word |
| `manifest.json` | the client, the case, the timeline, the key facts and the planted contradiction | | |

**The planted contradiction**, on a material fact:
- the affidavit (Exhibit P-2, page 1) says the first sale, invoice
  VF/INV/0001, was on **14 March 2016**;
- the plaintiff's own ledger (Exhibit P-3) dates the same invoice
  **2 August 2017** and records no earlier sale.

The plaint repeats 2016, and the written statement relies on 2017.

**Regenerate** with `server\.venv\Scripts\python server\scripts\make_demo_case.py`
(built by `server/tests/demo_case.py`). `server/tests/test_demo_case.py`
checks that:
- the files match the builder;
- each file reads with the real extractors;
- every key fact and both sides of the contradiction are on the stated
  page.

Whether an analysis *detects* the contradiction depends on the model. The
scripted test provider does not read meaning; it only places two passages
side by side.
