"""A FICTIONAL trade mark dispute for demonstrations and repeatable tests (Milestone 1).

Every person, firm, brand, product, place, court, registration and case number
here is invented. None describes a real matter, and none may be cited. The
documents are built in code so the committed copies in
``tests/fixtures/demo-case/`` can be checked against this module
(``tests/test_demo_case.py``): PDFs and text files byte for byte, Word files
by their text (Word stores a timestamp in its zip entries).

The matter: Velorindra Foods LLP (mark KESORA, millet snacks) sues Tamsinwick
Snacks Private Limited (mark KESORRA) for infringement and passing off. One
material fact is deliberately contradicted by two of the plaintiff's own
evidence documents (see ``CONTRADICTION``): the date of the first commercial
sale, invoice VF/INV/0001.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.document_fixtures import docx_with, pdf_with_pages, text_file

DEMO_DIR = Path(__file__).resolve().parent / "fixtures" / "demo-case"
NOTICE = "FICTIONAL DOCUMENT - created for LexFlow demonstrations. Not a real legal record."
CASE_REF = "Case ref: FICT-TM-014/2026 (fictional)"

CASE = {
    "title": "Velorindra Foods LLP v. Tamsinwick Snacks Private Limited (FICTIONAL)",
    "practiceArea": "Intellectual Property",
    "courtName": "Commercial Court at Ambarnagar (fictional)",
    "opposingParty": "Tamsinwick Snacks Private Limited (fictional)",
    "description": (
        "FICTIONAL demonstration matter. Velorindra Foods LLP, owner of the registered trade "
        "mark KESORA for packaged millet snacks, sues Tamsinwick Snacks Private Limited for "
        "infringement and passing off over the deceptively similar mark KESORRA. Prior use, "
        "the date of first sale and honest adoption are in dispute."
    ),
}
CLIENT = {
    "name": "Velorindra Foods LLP (FICTIONAL)",
    "email": "legal@velorindra-foods.example",
    "phone": "+91 00000 14014",
    "company": "Velorindra Foods LLP (fictional)",
}

PLAINT = [
    "IN THE COMMERCIAL COURT AT AMBARNAGAR (FICTIONAL)\n"
    "Commercial Suit No. FICT-TM-014 of 2026\n"
    "Velorindra Foods LLP ... Plaintiff\n"
    "versus\n"
    "Tamsinwick Snacks Private Limited ... Defendant\n"
    "PLAINT UNDER SECTIONS 134 AND 135 OF THE TRADE MARKS ACT (as pleaded, fictional)\n"
    "Dated 15 April 2026\n"
    "1. The plaintiff makes and sells packaged millet snacks under the mark KESORA.\n"
    "2. The plaintiff first sold KESORA millet snacks on 14 March 2016, under invoice\n"
    "VF/INV/0001, and has used the mark continuously since that date.\n"
    "3. The mark KESORA is registered in Class 30 under registration No. FICT-5550123,\n"
    "registered on 9 July 2018 (fictional registration).",
    "4. On 3 February 2025 a field officer of the plaintiff found millet snack packs\n"
    "sold under the mark KESORRA in the Ambarnagar wholesale market.\n"
    "5. KESORRA differs from KESORA by one letter, is used on identical goods, and is\n"
    "sold in a saffron-coloured pack like that of the plaintiff. The marks are deceptively\n"
    "similar and use by the defendant is likely to cause confusion among buyers.\n"
    "6. On 10 February 2025 the plaintiff sent a cease-and-desist notice. The defendant\n"
    "replied on 28 February 2025 and refused to stop.",
    "PRAYER\n"
    "(a) a permanent injunction restraining infringement of the mark KESORA;\n"
    "(b) a permanent injunction restraining passing off;\n"
    "(c) delivery up of infringing packs, and costs.\n"
    "List of documents: Affidavit of the Head of Sales (Exhibit P-2); sales ledger\n"
    "extract (Exhibit P-3); notice of 10 February 2025 and reply of 28 February 2025.\n"
    "Verified at Ambarnagar on 15 April 2026. Signed for demonstration purposes only.",
]

AFFIDAVIT = [
    "EXHIBIT P-2: AFFIDAVIT OF RAVINDAR PELLOKAR (FICTIONAL)\n"
    "Head of Sales, Velorindra Foods LLP. Sworn on 10 April 2026.\n"
    "1. I have been Head of Sales of the plaintiff since 2015 and keep its sales records.\n"
    "2. The first commercial sale of KESORA millet snacks was made on 14 March 2016,\n"
    "under invoice VF/INV/0001, to Sundaram Provision Stores (fictional), Ambarnagar.\n"
    "3. Since then KESORA snacks have been sold without interruption in 4 districts.",
    "4. Annual sales of KESORA snacks were Rs. 38 lakh in the year 2024-25 (fictional).\n"
    "5. I first saw KESORRA packs in March 2025, after the report of the field officer.\n"
    "Verification: the contents of this affidavit are true to my knowledge.\n"
    "Deponent: Ravindar Pellokar (fictional). Signed for demonstration purposes only.",
]

LEDGER = (
    "EXHIBIT P-3: SALES LEDGER EXTRACT, KESORA MILLET SNACKS (FICTIONAL)\n"
    "Prepared from the plaintiff's accounting system on 8 April 2026.\n\n"
    "Invoice      | Date             | Buyer (fictional)                 | Amount\n"
    "VF/INV/0001  | 2 August 2017    | Sundaram Provision Stores         | Rs. 18,400\n"
    "VF/INV/0002  | 19 August 2017   | Meghvani Traders                  | Rs. 22,150\n"
    "VF/INV/0003  | 4 September 2017 | Sundaram Provision Stores         | Rs. 16,900\n"
    "VF/INV/0145  | 30 June 2018     | Ambarnagar Retail Cooperative     | Rs. 41,700\n\n"
    "Note: the ledger records no sale of KESORA products before 2 August 2017.\n"
    "Extract certified for demonstration purposes only.\n"
)

NOTICE_LETTER = (
    "CEASE-AND-DESIST NOTICE (FICTIONAL)\n"
    "Date: 10 February 2025\n"
    "From: Counsel for Velorindra Foods LLP (fictional)\n"
    "To: Tamsinwick Snacks Private Limited (fictional), Ambarnagar\n\n"
    "Our client owns the registered trade mark KESORA for millet snacks and has used it since\n"
    "2016. Your packs sold under the mark KESORRA imitate our client's mark and saffron pack.\n"
    "You are called upon to stop all use of KESORRA within 15 days and to confirm in writing.\n"
)

REPLY = [
    "REPLY TO NOTICE DATED 10 FEBRUARY 2025 (FICTIONAL)",
    "Date: 28 February 2025",
    "From: Tamsinwick Snacks Private Limited (fictional)",
    "1. Our client adopted the mark KESORRA honestly in June 2023. It is coined from the "
    "names of its founders, Kesar and Orra Tamsinwick (fictional).",
    "2. Our client has sold KESORRA millet snacks openly since June 2023 and denies any "
    "intention to imitate the mark KESORA.",
    "3. Your client's claim of use since 2016 is denied for want of proof.",
    "Our client will not stop using its mark.",
]

WRITTEN_STATEMENT = [
    "WRITTEN STATEMENT OF THE DEFENDANT (FICTIONAL)",
    "Commercial Suit No. FICT-TM-014 of 2026. Filed on 20 May 2026.",
    "1. The defendant adopted the mark KESORRA honestly in June 2023 and has used it "
    "continuously since then.",
    "2. The plaintiff's own sales ledger (Exhibit P-3) records its first sale on 2 August 2017, "
    "not on 14 March 2016 as the plaint and the affidavit say. The plaintiff's claim of prior "
    "use from 2016 is therefore disputed.",
    "3. The marks differ visually and phonetically, and the defendant's packs carry its "
    "company name prominently. Confusion is denied.",
    "4. The suit should be dismissed with costs.",
]


def _with_notice(pages: list[str]) -> list[str]:
    """Every PDF page ends with the fictional notice and the case reference.

    The notice is at the foot, not the head, of each page and document: each
    document starts with its own title (marked FICTIONAL), so passages and quotes
    taken from the start of a document differ from one document to the next."""
    return [f"{page}\n{NOTICE}\n{CASE_REF}" for page in pages]


def _with_footer(text: str) -> str:
    """The same for a text file: the notice and case reference at the end."""
    return f"{text}\n{NOTICE}\n{CASE_REF}\n"


# (file name, title, document date, kind, builder)
DOCUMENTS: list[tuple[str, str, str, str, Callable[[], bytes]]] = [
    (
        "01-plaint.pdf",
        "Plaint",
        "2026-04-15",
        "pleading",
        lambda: pdf_with_pages(_with_notice(PLAINT)),
    ),
    (
        "02-affidavit-head-of-sales.pdf",
        "Affidavit of the Head of Sales (Exhibit P-2)",
        "2026-04-10",
        "evidence",
        lambda: pdf_with_pages(_with_notice(AFFIDAVIT)),
    ),
    (
        "03-exhibit-p3-sales-ledger.txt",
        "Sales ledger extract (Exhibit P-3)",
        "2026-04-08",
        "evidence",
        lambda: text_file(_with_footer(LEDGER)),
    ),
    (
        "04-cease-and-desist-notice.txt",
        "Cease-and-desist notice",
        "2025-02-10",
        "correspondence",
        lambda: text_file(_with_footer(NOTICE_LETTER)),
    ),
    (
        "05-reply-to-notice.docx",
        "Defendant's reply to the notice",
        "2025-02-28",
        "correspondence",
        lambda: docx_with([*REPLY, NOTICE, CASE_REF]),
    ),
    (
        "06-written-statement.docx",
        "Written statement of the defendant",
        "2026-05-20",
        "pleading",
        lambda: docx_with([*WRITTEN_STATEMENT, NOTICE, CASE_REF]),
    ),
]

# The material fact two of the plaintiff's own evidence documents disagree on.
# "page" is the PDF page (1-based); null for documents without pages.
CONTRADICTION: dict[str, Any] = {
    "fact": "date of the first commercial sale of KESORA products (invoice VF/INV/0001)",
    "statements": [
        {
            "file": "02-affidavit-head-of-sales.pdf",
            "page": 1,
            "text": "The first commercial sale of KESORA millet snacks was made on 14 March 2016,",
        },
        {
            "file": "03-exhibit-p3-sales-ledger.txt",
            "page": None,
            "text": "VF/INV/0001  | 2 August 2017",
        },
    ],
    "also_pleaded": [
        {"file": "01-plaint.pdf", "page": 1, "text": "first sold KESORA millet snacks on 14 March"},
        {"file": "06-written-statement.docx", "page": None, "text": "records its first sale on 2"},
    ],
}

# Facts the tests check after real extraction: (file, page or None, exact text).
KEY_FACTS: list[tuple[str, int | None, str]] = [
    ("01-plaint.pdf", 1, "registered on 9 July 2018 (fictional registration)."),
    ("01-plaint.pdf", 2, "On 3 February 2025 a field officer of the plaintiff found millet snack"),
    ("01-plaint.pdf", 3, "(b) a permanent injunction restraining passing off;"),
    ("02-affidavit-head-of-sales.pdf", 2, "Annual sales of KESORA snacks were Rs. 38 lakh"),
    ("04-cease-and-desist-notice.txt", None, "stop all use of KESORRA within 15 days"),
    ("05-reply-to-notice.docx", None, "adopted the mark KESORRA honestly in June 2023"),
]

TIMELINE = [
    ("2016-03-14", "First sale of KESORA claimed by the plaintiff (plaint, affidavit)"),
    ("2017-08-02", "Earliest invoice in the plaintiff's own sales ledger (Exhibit P-3)"),
    ("2018-07-09", "KESORA registered in Class 30 (fictional registration)"),
    ("2023-06-01", "KESORRA adopted, according to the defendant (month only: June 2023)"),
    ("2025-02-03", "KESORRA packs found in the Ambarnagar market"),
    ("2025-02-10", "Cease-and-desist notice"),
    ("2025-02-28", "Defendant's reply refusing to stop"),
    ("2026-04-15", "Plaint filed"),
    ("2026-05-20", "Written statement filed"),
]


def manifest() -> dict[str, Any]:
    return {
        "name": "fictional-trademark-dispute-v1",
        "notice": (
            "FICTIONAL: every person, firm, brand, product, place, court, registration and "
            "case number in this pack is invented for LexFlow demonstrations and tests. It is "
            "not a real legal record and must never be cited."
        ),
        "client": CLIENT,
        "case": CASE,
        "documents": [
            {"file": name, "title": title, "date": date, "kind": kind}
            for name, title, date, kind, _ in DOCUMENTS
        ],
        "timeline": [{"date": d, "event": e} for d, e in TIMELINE],
        "contradiction": CONTRADICTION,
        "keyFacts": [{"file": f, "page": p, "text": t} for f, p, t in KEY_FACTS],
    }


def manifest_bytes() -> bytes:
    return (json.dumps(manifest(), indent=2, ensure_ascii=True) + "\n").encode("utf-8")
