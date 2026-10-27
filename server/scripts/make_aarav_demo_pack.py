# ruff: noqa: E501 - document text and tables read better unwrapped
"""Build the FICTIONAL academic demonstration matter *Aarav Foods v. Sunrise Retail*.

    .venv\\Scripts\\python scripts/make_aarav_demo_pack.py

Writes seven documents to ``docs/demo-matter/aarav-foods-v-sunrise-retail/``,
for uploading through the normal LexFlow application (see the README there).
Every party, mark, event, figure and letter is invented; every page says so.
The legal authorities are genuine Supreme Court of India judgments from the
verified corpus (``docs/verification/batch2/``); the passages relied on were
checked against the stored judgment text, and the research memorandum gives
each judgment's official sci.gov.in source.

The prepared demonstration analysis (``lexflow/analysis/prepared/``) quotes
sentences of these documents; ``tests/test_prepared_analysis.py`` checks that
every quoted sentence is in the text LexFlow extracts from them.
"""

from __future__ import annotations

import io
import sys
import textwrap
from pathlib import Path
from typing import Any

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.document_fixtures import pdf_with_pages

OUT = Path(__file__).resolve().parents[2] / "docs" / "demo-matter" / "aarav-foods-v-sunrise-retail"
MARKING = (
    "ILLUSTRATIVE ACADEMIC MATERIAL - FICTIONAL. Parties, marks, events and figures are "
    "invented for a LexFlow demonstration. Not a filing, not legal advice, not genuine correspondence."
)
REF = "Internal matter ref. AF/TM/2026/01 (illustrative)"
CASE = "Aarav Foods Pvt. Ltd. v. Sunrise Retail Pvt. Ltd. (fictional)"

# ---------------------------------------------------------------------------- DOCX helpers


def _doc(title: str, subtitle: str) -> Any:
    d = docx.Document()
    style = d.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)
    for section in d.sections:
        header = section.header.paragraphs[0]
        header.text = f"{CASE}  |  {REF}"
        header.runs[0].font.size = Pt(8)
        footer = section.footer.paragraphs[0]
        footer.text = MARKING
        footer.runs[0].font.size = Pt(7.5)
        footer.runs[0].font.color.rgb = RGBColor(0x8A, 0x1C, 0x1C)
    banner = d.add_paragraph()
    run = banner.add_run("ILLUSTRATIVE ACADEMIC MATERIAL - FICTIONAL")
    run.bold = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x8A, 0x1C, 0x1C)
    d.add_heading(title, level=0)
    sub = d.add_paragraph(subtitle)
    sub.runs[0].italic = True
    return d


def _table(d: Any, rows: list[list[str]], widths_bold_first: bool = True) -> None:
    t = d.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Light Grid Accent 1"
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = t.cell(r, c)
            cell.text = value
            if r == 0 and widths_bold_first:
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.bold = True
    d.add_paragraph()


def _save(d: Any) -> bytes:
    end = d.add_paragraph(MARKING)
    end.alignment = WD_ALIGN_PARAGRAPH.CENTER
    end.runs[0].font.size = Pt(8)
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


# ----------------------------------------------------------------------------- PDF helper


def _pdf(title: str, paragraphs: list[str]) -> bytes:
    """Plain-text PDF pages (latin-1), wrapped at 88 characters, 46 lines a page."""
    lines = ["ILLUSTRATIVE ACADEMIC MATERIAL - FICTIONAL", CASE, REF, "", title.upper(), ""]
    for para in paragraphs:
        lines.extend(textwrap.wrap(para, 88, break_on_hyphens=False) if para else [""])
        lines.append("")
    pages, per = [], 46
    for start in range(0, len(lines), per):
        body = lines[start : start + per]
        page_no = start // per + 1
        pages.append("\n".join([*body, "", f"Page {page_no} - {MARKING[:86]}"]))
    return pdf_with_pages(pages)


# ------------------------------------------------------------------------------ documents


def intake_form() -> bytes:
    d = _doc(
        "Client Intake Form and Matter Summary",
        "Taken at the first meeting on 20 February 2026. Prepared by the reviewing advocate.",
    )
    d.add_heading("1. Client", level=1)
    _table(
        d,
        [
            ["Field", "Details (fictional)"],
            ["Client", "Aarav Foods Pvt. Ltd."],
            ["Registered office", "Plot 14, Hinjawadi Phase II, Pune 411057, Maharashtra"],
            ["Delhi sales office", "Okhla Industrial Area Phase II, New Delhi (since 2022)"],
            ["Instructing officer", "Ms. Kavya Deshmukh, Managing Director"],
            ["Other contact", "Mr. Rohan Mehta, Regional Sales Manager (North)"],
            ["E-mail", "legal@aaravfoods.example"],
            [
                "Business",
                "Baked millet snacks: ragi crisps, jowar masala puffs, bajra herb crackers",
            ],
        ],
    )
    d.add_heading("2. Opposing party", level=1)
    _table(
        d,
        [
            ["Field", "Details (fictional)"],
            ["Name", "Sunrise Retail Pvt. Ltd."],
            ["Registered office", "Sector 44, Gurugram, Haryana"],
            [
                "Business",
                "Operates 64 'Sunrise Fresh' supermarkets in the NCR, 22 of them in Delhi",
            ],
            ["Product complained of", "MILLETO baked millet crisps (private label), 70 g, Rs. 39"],
        ],
    )
    d.add_heading("3. Matter summary", level=1)
    d.add_paragraph(
        "Aarav Foods has sold baked millet snacks under the mark MILLETTA since 1 August 2019. "
        "In January 2026 Sunrise Retail began selling baked millet crisps under the mark MILLETO "
        "in a mustard-yellow pack with a green lower band. The client believes shoppers will take "
        "MILLETO for a MILLETTA product."
    )
    d.add_paragraph(
        "Client objective: to assess the merits and risks of seeking an interim injunction "
        "restraining Sunrise Retail from selling goods under the mark MILLETO, and to decide "
        "whether to send a cease-and-desist notice first."
    )
    d.add_heading("4. What the client says, and its status", level=1)
    _table(
        d,
        [
            ["Statement", "Status"],
            [
                "MILLETTA is registered as a word mark in Class 30",
                "Client's statement; not yet verified on the Trade Marks Registry e-register; no certificate in the file",
            ],
            ["Sales of Rs. 11.6 crore in FY 2024-25", "Management figures; unaudited"],
            ["First learned of MILLETO on 3 February 2026", "Client's account; may be disputed"],
            [
                "Two customers complained about 'MILLETTA' bought at Sunrise Fresh",
                "E-mails only; senders not contacted",
            ],
        ],
    )
    d.add_heading("5. Initial instructions and next steps", level=1)
    for step in [
        "Obtain the registration particulars of MILLETTA from the e-register.",
        "Collect dated photographs of both packs and purchase receipts.",
        "Preserve the two customer e-mails with their headers.",
        "Prepare a statement of facts and a chronology; then draft a cease-and-desist notice.",
    ]:
        d.add_paragraph(step, style="List Number")
    return _save(d)


STATEMENT_OF_FACTS = [
    "Prepared on 24 February 2026 from the client's instructions. Facts marked 'alleged' or "
    "'disputed' are not yet supported by documents in the file.",
    "1. The client. Aarav Foods Pvt. Ltd. is a company incorporated on 14 June 2017 with its "
    "registered office in Pune. It has had a sales office in New Delhi since 2022.",
    "2. The mark. Aarav Foods has sold baked millet snacks under the mark MILLETTA since "
    "1 August 2019. The client states that MILLETTA is registered as a word mark in Class 30 "
    "on an application filed on 12 March 2019; the registration particulars have not yet been "
    "verified.",
    "3. The packaging. MILLETTA packs are bright yellow with a green band across the lower "
    "third, an illustration of a millet stalk, and the word MILLETTA in dark green serif "
    "letters. A 75 g pack sells for Rs. 45.",
    "4. Sales and promotion. According to unaudited management figures, MILLETTA sales were "
    "Rs. 11.6 crore in FY 2024-25. The client spent about Rs. 1.4 crore on promotion in 2025, "
    "mostly in-store displays in Maharashtra, Karnataka and the NCR.",
    "5. The competing product. Sunrise Retail began selling baked millet crisps under the mark "
    "MILLETO in January 2026. MILLETO is sold in Sunrise Fresh stores and through "
    "quick-commerce apps. Its 70 g pack is mustard-yellow with a green lower band, and sells "
    "for Rs. 39.",
    "6. How the client learned of it. Mr. Rohan Mehta, the client's Regional Sales Manager, "
    "first saw MILLETO on 3 February 2026 at the Sunrise Fresh store in Saket, New Delhi. "
    "The client says it had no earlier knowledge of the product.",
    "7. Alleged confusion. On 10 February 2026 and 17 February 2026 the client's customer-care "
    "address received two e-mails complaining about stale 'MILLETTA' packs bought at Sunrise "
    "Fresh stores. Aarav Foods does not supply Sunrise Fresh. The senders have not been "
    "contacted and no receipts are available, so the complaints are unverified.",
    "8. The client's position. The client alleges that MILLETO is phonetically and visually "
    "similar to MILLETTA, that the packs share the same colour scheme, and that shoppers with "
    "an imperfect recollection of MILLETTA are likely to be confused.",
    "9. Points the other side is expected to raise. Sunrise Retail may say that 'millet' "
    "describes the product, that its SUNRISE house mark appears on every pack, and that "
    "MILLETO is sold only in its own stores.",
]

CHRONOLOGY = [
    "Updated on 20 March 2026. Source of each entry is given in brackets.",
    "14 June 2017 - Aarav Foods Pvt. Ltd. incorporated in Pune. (Intake form)",
    "12 March 2019 - Application for the word mark MILLETTA in Class 30, according to the "
    "client. Particulars not verified. (Statement of facts, para 2)",
    "1 August 2019 - First sale of MILLETTA baked millet snacks. (Statement of facts, para 2)",
    "2022 - Aarav Foods opens its New Delhi sales office. (Intake form)",
    "18-20 November 2025 - Annapoorna Food Expo, Mumbai. Sunrise Retail says it displayed "
    "MILLETO at stall B-17, opposite Aarav Foods' stall B-22. DISPUTED: the client says its "
    "stall was staffed by its distributor and that it did not learn of MILLETO there. "
    "(Reply of 16 March 2026)",
    "20 January 2026 - Sunrise Retail launches MILLETO in its Sunrise Fresh stores. "
    "(Reply of 16 March 2026)",
    "3 February 2026 - Mr. Rohan Mehta sees MILLETO at Sunrise Fresh, Saket, New Delhi. "
    "(Statement of facts, para 6)",
    "8 February 2026 - Screenshot said to show MILLETO on a quick-commerce app. Not yet "
    "authenticated. (Evidence index, item E-6)",
    "10 February 2026 and 17 February 2026 - Two customer e-mails about 'MILLETTA' bought at "
    "Sunrise Fresh. Unverified. (Statement of facts, para 7)",
    "20 February 2026 - First client meeting; intake form completed. (Intake form)",
    "2 March 2026 - Cease-and-desist notice sent to Sunrise Retail. (Notice)",
    "16 March 2026 - Sunrise Retail replies, denying infringement. (Reply)",
    "25 March 2026 - Legal research memorandum on an interim injunction. (Memorandum)",
    "Open points: the knowledge date (November 2025 or February 2026) and whether MILLETO is "
    "sold on quick-commerce apps are disputed and need evidence.",
]

NOTICE = [
    "2 March 2026. By e-mail and registered post (illustrative).",
    "To: Sunrise Retail Pvt. Ltd., Sector 44, Gurugram, Haryana.",
    "Subject: Infringement of the trade mark MILLETTA - cease and desist.",
    "1. We act for Aarav Foods Pvt. Ltd. (our client). Our client has sold baked millet snacks "
    "under the mark MILLETTA since 1 August 2019 and states that the mark is registered in "
    "Class 30.",
    "2. Our client has learned that you are selling baked millet crisps under the mark MILLETO "
    "in packs coloured yellow with a green lower band, in your Sunrise Fresh stores in Delhi "
    "and elsewhere in the NCR.",
    "3. MILLETO differs from MILLETTA only in its ending. Used for identical goods, sold to the "
    "same shoppers in a similar get-up, it is likely to cause confusion. Our client has already "
    "received complaints from shoppers who bought MILLETO believing it to be MILLETTA.",
    "4. We therefore call upon you, within 14 days of this notice, that is by 16 March 2026: "
    "(a) to stop making, selling and advertising any goods under the mark MILLETO or any mark "
    "similar to MILLETTA; (b) to withdraw existing stock; (c) to disclose your sales of MILLETO "
    "to date; and (d) to give a written undertaking to that effect.",
    "5. If you do not comply, our client reserves the right to bring proceedings, including an "
    "application for an interim injunction, without further notice.",
    "Advocates for Aarav Foods Pvt. Ltd. (illustrative; unsigned demonstration draft)",
]


def reply() -> bytes:
    d = _doc(
        "Reply to Notice dated 2 March 2026",
        "Draft reply on behalf of Sunrise Retail Pvt. Ltd., dated 16 March 2026 (illustrative).",
    )
    for para in [
        "1. We act for Sunrise Retail Pvt. Ltd. (our client) and reply to your notice of 2 March 2026. "
        "Every allegation in the notice is denied unless expressly admitted.",
        "2. Our client adopted the mark MILLETO honestly after a trade mark search in November 2025. "
        "The word is coined from 'millet', the grain from which the product is made, which no "
        "trader can claim for itself.",
        "3. Our client's SUNRISE house mark appears prominently on the top left of every MILLETO pack. "
        "No shopper buying from a Sunrise Fresh shelf could mistake the product for another trader's.",
        "4. MILLETO is sold only in Sunrise Fresh stores and on the Sunrise Fresh app; it is not "
        "listed on any third-party quick-commerce platform.",
        "5. Your client has known of MILLETO since the Annapoorna Food Expo in Mumbai on 18-20 "
        "November 2025, where it was displayed at stall B-17, directly opposite your client's "
        "stall B-22. Your client did nothing for over three months.",
        "6. Our client launched MILLETO in its stores on 20 January 2026. Yellow and green are "
        "common colours for snack packs and are not distinctive of your client.",
        "7. The so-called complaints are not identified. Our client calls upon your client to "
        "produce them, with the purchase receipts.",
        "8. Without prejudice, our client is willing to discuss enlarging the SUNRISE house mark on "
        "future print runs. It will not withdraw MILLETO.",
    ]:
        d.add_paragraph(para)
    d.add_paragraph(
        "Advocates for Sunrise Retail Pvt. Ltd. (illustrative; unsigned demonstration draft)"
    )
    return _save(d)


def evidence_index() -> bytes:
    d = _doc(
        "Evidence Index and Packaging Comparison",
        "As at 20 March 2026. Lists what is in the file, what it is offered to show, and its status.",
    )
    d.add_heading("1. Index of exhibits", level=1)
    _table(
        d,
        [
            ["No.", "Exhibit", "Offered to show", "Status"],
            [
                "E-1",
                "Registration-details sheet for MILLETTA (illustrative, prepared from the client's statement; not an official record)",
                "Ownership of a registered word mark in Class 30",
                "To be replaced by an e-register extract",
            ],
            [
                "E-2",
                "MILLETTA packs and price list, 2019-2026",
                "Continuous use since 1 August 2019",
                "Client documents; dated photographs needed",
            ],
            [
                "E-3",
                "MILLETO pack bought at Sunrise Fresh, Saket, on 3 February 2026",
                "The mark and get-up complained of",
                "Physical pack held; receipt kept",
            ],
            [
                "E-4",
                "Packaging comparison (section 2 below)",
                "Similarity of get-up",
                "Prepared by counsel; illustrative",
            ],
            [
                "E-5",
                "Customer e-mails of 10 and 17 February 2026",
                "Alleged actual confusion",
                "Unverified; senders not contacted",
            ],
            [
                "E-6",
                "Screenshot said to show MILLETO on a quick-commerce app, 8 February 2026",
                "Overlapping trade channels",
                "Not authenticated; contradicts the reply, para 4",
            ],
            [
                "E-7",
                "Unaudited sales and promotion figures",
                "Reputation and goodwill",
                "Auditor's certificate needed",
            ],
            [
                "E-8",
                "Notice of 2 March 2026 and reply of 16 March 2026",
                "Pre-suit correspondence",
                "In the file",
            ],
        ],
    )
    d.add_heading("2. Packaging comparison (illustrative)", level=1)
    _table(
        d,
        [
            ["Feature", "MILLETTA (Aarav Foods)", "MILLETO (Sunrise Retail)"],
            ["Word mark", "MILLETTA", "MILLETO"],
            ["Pack colour", "Bright yellow", "Mustard yellow"],
            ["Band", "Green band across the lower third", "Green lower band"],
            ["Illustration", "Millet stalk", "Bowl of millet crisps"],
            ["House mark", "AARAV FOODS, small, at the foot", "SUNRISE, top left"],
            ["Size and price", "75 g, Rs. 45", "70 g, Rs. 39"],
            [
                "Where sold",
                "General stores, supermarkets, own website",
                "Sunrise Fresh stores and app (disputed: also quick-commerce)",
            ],
        ],
    )
    d.add_paragraph(
        "The packaging comparison shows a shared colour scheme and a shared green lower band, "
        "but different illustrations and a prominent SUNRISE house mark on the MILLETO pack."
    )
    d.add_heading("3. Evidence still missing", level=1)
    for item in [
        "An extract from the Trade Marks Registry e-register for MILLETTA.",
        "Affidavits or verified statements from the two complaining customers, with receipts.",
        "Authentication of the quick-commerce screenshot (E-6), or fresh dated captures.",
        "Evidence of who staffed Aarav Foods' stall at the Annapoorna Food Expo in November 2025.",
        "Audited sales figures, and Sunrise Retail's sales of MILLETO.",
        "Sunrise Retail's November 2025 trade mark search report, which its reply mentions.",
    ]:
        d.add_paragraph(item, style="List Bullet")
    return _save(d)


AUTHORITIES = [
    (
        "Amritdhara Pharmacy v. Satyadeo Gupta",
        "Supreme Court of India, 27 April 1962; 1963 AIR 449",
        "https://api.sci.gov.in/jonew/judis/3855.pdf",
        "The question of deceptive similarity is approached from the point of view of a man of "
        "average intelligence and imperfect recollection; the overall structural and phonetic "
        "similarity of the two names is what matters.",
        "Supports Aarav Foods on issue 1: MILLETTA and MILLETO share their first six letters and "
        "most of their sound. Limitation: the marks there were compared for medicinal "
        "preparations; snack shoppers may pay less attention still, which helps Aarav, but the "
        "shared element here is the descriptive word 'millet'.",
    ),
    (
        "Parle Products (P) Ltd. v. J. P. & Co., Mysore",
        "Supreme Court of India, 28 January 1972; 1972 AIR 1359",
        "https://api.sci.gov.in/jonew/judis/6909.pdf",
        "The broad and essential features of the two marks are to be considered; they should "
        "not be placed side by side to find differences in detail.",
        "Relevant to issue 2 (get-up): the shared yellow pack and green lower band are the broad "
        "features a shopper remembers. Limitation: Sunrise Retail will point to the different "
        "illustration and its house mark, which a side-by-side comparison would highlight.",
    ),
    (
        "M/s. Nandhini Deluxe v. M/s. Karnataka Co-operative Milk Producers Federation Ltd.",
        "Supreme Court of India, 26 July 2018; no law-report citation recorded in the source",
        "https://api.sci.gov.in/supremecourt/2015/18014/18014_2015_Judgement_26-Jul-2018.pdf",
        "The proprietor of a trade mark cannot enjoy a monopoly over the entire class of goods, "
        "particularly where it does not use the mark for certain goods in that class.",
        "Sunrise Retail may rely on it to resist an over-broad claim. Limitation: there the goods "
        "differed (milk products and restaurant services); here both parties sell baked millet "
        "snacks, so the case is factually distinguishable on the goods.",
    ),
    (
        "Pernod Ricard India Private Limited & Another v. Karanveer Singh Chhabra",
        "Supreme Court of India, 14 August 2025; 2025 INSC 981",
        "https://api.sci.gov.in/supremecourt/2023/52688/52688_2023_8_1502_63274_Judgement_14-Aug-2025.pdf",
        "At the interim stage the court does not conduct a mini-trial: it determines whether a "
        "prima facie case exists, with the balance of convenience and potential irreparable "
        "injury, and does not adjudicate the ultimate rights of the parties.",
        "Frames issue 7. The judgment also discusses descriptive and common terms, the dominant "
        "feature test and the average consumer, and it states that it is confined to the "
        "interim-injunction application before it.",
    ),
    (
        "Indian Performing Rights Society Ltd. v. Sanjay Dalia & Anr.",
        "Supreme Court of India, 1 July 2015; no law-report citation recorded in the source",
        "https://api.sci.gov.in/jonew/judis/42728.pdf",
        "Read with the deeming explanation for corporations, the place of a subordinate office "
        "where the cause of action arises is the relevant place for filing, not the principal "
        "place of business.",
        "Relevant only to forum (issue 8): Aarav Foods' principal office is in Pune, but it has a "
        "Delhi sales office and the sales complained of include Sunrise Fresh stores in Delhi.",
    ),
]


def research_memo() -> bytes:
    d = _doc(
        "Legal Research Memorandum: Interim Injunction",
        "25 March 2026. Prepared for the reviewing advocate. Fictional facts; genuine authorities.",
    )
    d.add_heading("1. Question", level=1)
    d.add_paragraph(
        "Whether Aarav Foods should apply for an interim injunction restraining Sunrise Retail "
        "from using the mark MILLETO, and what the main risks are. This memorandum does not "
        "predict the outcome of any proceeding."
    )
    d.add_heading("2. Issues for determination", level=1)
    for issue in [
        "Is MILLETO deceptively similar to MILLETTA for an average shopper with imperfect recollection?",
        "Does the overall get-up add to the likelihood of confusion, and does the SUNRISE house mark dispel it?",
        "Is 'millet' descriptive, so that Aarav Foods cannot claim exclusivity over it?",
        "Do the trade channels and shoppers differ enough to reduce confusion?",
        "What weight can the two unverified customer e-mails carry?",
        "When did Aarav Foods learn of MILLETO, and does any delay matter?",
        "Prima facie case, balance of convenience and irreparable harm.",
        "Can the suit be brought in Delhi?",
    ]:
        d.add_paragraph(issue, style="List Number")
    d.add_heading("3. Authorities (genuine Supreme Court of India judgments)", level=1)
    d.add_paragraph(
        "Each passage below was checked against the judgment text stored in LexFlow. Supreme "
        "Court decisions bind every court in India, including the Delhi High Court; whether they "
        "decide this fictional dispute depends on its facts."
    )
    for title, court, url, principle, relevance in AUTHORITIES:
        d.add_heading(title, level=2)
        d.add_paragraph(court)
        d.add_paragraph(f"Official source: {url}")
        p = d.add_paragraph()
        p.add_run("Principle (paraphrased from the judgment): ").bold = True
        p.add_run(principle)
        p = d.add_paragraph()
        p.add_run("Relevance and limits (our interpretation): ").bold = True
        p.add_run(relevance)
    d.add_heading("4. Arguments", level=1)
    _table(
        d,
        [
            ["Point", "Aarav Foods", "Sunrise Retail"],
            [
                "Marks",
                "MILLETO differs from MILLETTA only in its ending",
                "Both are built on 'millet', a descriptive word",
            ],
            [
                "Get-up",
                "Same yellow pack and green lower band",
                "Different illustration; SUNRISE house mark on top",
            ],
            [
                "Channels",
                "Same shoppers; also on quick-commerce apps (disputed)",
                "Sold only in its own stores and app",
            ],
            ["Confusion", "Two customer complaints", "Complaints unidentified and unverified"],
            ["Delay", "Learned of MILLETO on 3 February 2026", "Knew in November 2025 at the expo"],
        ],
    )
    d.add_heading("5. Assessment and next steps", level=1)
    d.add_paragraph(
        "The marks are close in structure and sound, and the goods are identical, which supports "
        "Aarav Foods on similarity. The descriptive 'millet' element, the house mark and the "
        "disputed channels and knowledge date are real weaknesses. The unverified complaints "
        "should not be relied on until they are proved. No conclusion is expressed on how a "
        "court would rule."
    )
    for step in [
        "Obtain the e-register extract for MILLETTA before any filing.",
        "Secure affidavits from the complaining customers, or drop the point.",
        "Establish who staffed stall B-22 in November 2025.",
        "Capture dated evidence of any quick-commerce listing of MILLETO.",
    ]:
        d.add_paragraph(step, style="List Bullet")
    return _save(d)


DOCUMENTS: list[tuple[str, object]] = [
    ("01-client-intake-and-matter-summary.docx", intake_form),
    ("02-statement-of-facts.pdf", lambda: _pdf("Statement of Facts", STATEMENT_OF_FACTS)),
    ("03-chronology-of-events.pdf", lambda: _pdf("Chronology of Material Events", CHRONOLOGY)),
    ("04-cease-and-desist-notice.pdf", lambda: _pdf("Cease-and-Desist Notice (draft)", NOTICE)),
    ("05-reply-from-sunrise-retail.docx", reply),
    ("06-evidence-index-and-packaging-comparison.docx", evidence_index),
    ("07-legal-research-memorandum.docx", research_memo),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in DOCUMENTS:
        data = build()  # type: ignore[operator]
        (OUT / name).write_bytes(data)
        print(f"wrote {name} ({len(data):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
