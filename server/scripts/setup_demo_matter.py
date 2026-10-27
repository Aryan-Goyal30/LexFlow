"""Set up the FICTIONAL demonstration matter in the running main LexFlow app.

    .venv\\Scripts\\python scripts/setup_demo_matter.py

Uses only the app's normal HTTP API (http://127.0.0.1:8000), signed in as you:
your e-mail and password are asked for here (the password is not shown, stored
or printed). Every step goes through the application's own validation and
permissions. It is safe to run again: an existing client, case, document,
analysis or review is reused, never duplicated or changed.

Steps: add the client and case from docs/demo-matter/aarav-foods-v-sunrise-retail
(README), upload the seven documents and wait for their text, run the prepared
demonstration analysis (not AI; LEXFLOW_AI_PROVIDER=prepared), accept one fact
and one precedent comparison as a reviewer would, and export the case brief to
server/var/exports/ (git-ignored).
"""

from __future__ import annotations

import getpass
import sys
import time
from pathlib import Path
from typing import Any

import httpx

API = "http://127.0.0.1:8000/api"
APP_ORIGIN = "http://localhost:5173"
PACK = Path(__file__).resolve().parents[2] / "docs" / "demo-matter" / "aarav-foods-v-sunrise-retail"
EXPORTS = Path(__file__).resolve().parents[1] / "var" / "exports"
TITLE = "Aarav Foods Pvt. Ltd. v. Sunrise Retail Pvt. Ltd."
CLIENT = {
    "name": "Aarav Foods Pvt. Ltd.",
    "email": "legal@aaravfoods.example",
    "phone": "+91 20 0000 2019",
    "company": "Aarav Foods Pvt. Ltd. (fictional)",
}
CASE = {
    "title": TITLE,
    "practiceArea": "Intellectual Property",
    "status": "Open",
    "priority": "High",
    "courtName": "Delhi High Court (hypothetical forum)",
    "opposingParty": "Sunrise Retail Pvt. Ltd.",
    "description": (
        "FICTIONAL academic matter. Alleged infringement of the mark MILLETTA by MILLETO; "
        "deceptive similarity, get-up, descriptive element, channels, delay; client wants to "
        "assess an interim injunction."
    ),
}
DOCUMENTS = [
    "01-client-intake-and-matter-summary.docx",
    "02-statement-of-facts.pdf",
    "03-chronology-of-events.pdf",
    "04-cease-and-desist-notice.pdf",
    "05-reply-from-sunrise-retail.docx",
    "06-evidence-index-and-packaging-comparison.docx",
    "07-legal-research-memorandum.docx",
]
TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def ok(response: httpx.Response, what: str) -> Any:
    if response.status_code >= 400:
        detail = (
            response.json().get("detail")
            if "json" in response.headers.get("content-type", "")
            else ""
        )
        sys.exit(f"FAILED: {what}: HTTP {response.status_code} {detail}")
    return response.json() if "json" in response.headers.get("content-type", "") else response


def wait(check: Any, what: str, seconds: int = 180) -> Any:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(2)
    sys.exit(f"FAILED: timed out waiting for {what} (is the worker running?)")


def main() -> int:
    http = httpx.Client(
        base_url=API, headers={"x-lexflow-request": "1", "Origin": APP_ORIGIN}, timeout=60
    )
    health = ok(http.get("/health"), "API health")
    print(f"API: {health}")
    email = input("Your LexFlow e-mail: ").strip()
    ok(http.post("/auth/login", json={"email": email, "password": getpass.getpass()}), "sign-in")
    me = ok(http.get("/auth/me"), "who am I")
    print(f"Signed in as {me['name']} ({me['role']}).")

    clients = ok(http.get("/clients"), "client list")
    client = next((c for c in clients if c["name"] == CLIENT["name"]), None)
    if client is None:
        client = ok(http.post("/clients", json=CLIENT), "add client")
        print(f"Client created: {client['id']}")
    else:
        print(f"Client already exists: {client['id']}")

    cases = ok(http.get("/cases", params={"archived": "include"}), "case list")
    case = next((c for c in cases if c["title"] == TITLE), None)
    if case is None:
        if me["role"] == "Advocate":
            lead = me["id"]
        else:
            advocates = ok(http.get("/advocates"), "advocates")
            lead = next(
                (a["id"] for a in advocates if a["name"] == "Aryan Goyal"), advocates[0]["id"]
            )
        case = ok(
            http.post("/cases", json={**CASE, "clientId": client["id"], "leadAdvocateId": lead}),
            "create case",
        )
        print(f"Case created: {case['id']}")
    else:
        print(f"Case already exists: {case['id']}")
    case_id = case["id"]

    have = {d["name"] for d in ok(http.get(f"/cases/{case_id}"), "case")["documents"]}
    for name in DOCUMENTS:
        if name in have:
            continue
        path = PACK / name
        files = {"file": (name, path.read_bytes(), TYPES[path.suffix])}
        ok(http.post(f"/cases/{case_id}/documents", files=files), f"upload {name}")
        print(f"Uploaded {name}")

    def documents_ready() -> list[dict[str, Any]] | None:
        docs = [
            d
            for d in ok(http.get(f"/cases/{case_id}"), "case")["documents"]
            if d["name"] in DOCUMENTS
        ]
        states = {d["name"]: (d.get("processing") or {}).get("status") for d in docs}
        failed = [n for n, s in states.items() if s in ("failed", "unsupported")]
        if failed:
            sys.exit(f"FAILED: text extraction failed for {failed}")
        return (
            docs
            if len(docs) == len(DOCUMENTS) and all(s == "ready" for s in states.values())
            else None
        )

    docs = wait(documents_ready, "document text")
    print(f"All {len(docs)} documents are text-ready.")

    runs = ok(http.get(f"/cases/{case_id}/analysis-runs"), "analysis runs")["items"]
    run = next((r for r in runs if r["status"] == "ready" and r["provider"] == "prepared"), None)
    if run is None:
        started = ok(
            http.post(
                f"/cases/{case_id}/analysis-runs",
                json={"documentIds": [d["id"] for d in docs], "confirmTransmission": True},
            ),
            "start analysis",
        )
        run = {"id": started["id"]}
        print("Prepared analysis started.")

    def finished() -> dict[str, Any] | None:
        current = ok(http.get(f"/cases/{case_id}/analysis-runs/{run['id']}"), "analysis run")
        if current["status"] == "failed":
            sys.exit(f"FAILED: analysis failed: {current['reason']}")
        return current if current["status"] == "ready" else None

    result = wait(finished, "the analysis")
    r = result["result"]
    genuine = sum(not p["synthetic"] for p in r["precedents"])
    print(
        f"Analysis ({result['provider']}): {len(r['facts'])} facts, {len(r['issues'])} issues, "
        f"{len(r['precedents'])} precedent comparisons ({genuine} genuine), "
        f"{len(r['contradictions'])} contradictions, {r['removed']['count']} removed by validation."
    )

    for finding in ("F1", "P1"):
        put = http.put(
            f"/cases/{case_id}/analysis-runs/{run['id']}/reviews/{finding}",
            json={"status": "accepted", "expectedVersion": 0},
        )
        print(f"Review {finding}: {'accepted' if put.status_code < 400 else 'already reviewed'}")

    brief = ok(http.get(f"/cases/{case_id}/analysis-runs/{run['id']}/brief"), "brief export")
    EXPORTS.mkdir(parents=True, exist_ok=True)
    out = EXPORTS / f"aarav-foods-brief-{time.strftime('%Y%m%d-%H%M%S')}.docx"
    out.write_bytes(brief.content)
    print(f"Brief exported: {out} ({len(brief.content):,} bytes)")
    print(f"\nOpen the case: http://localhost:5173/app/cases/{case_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
