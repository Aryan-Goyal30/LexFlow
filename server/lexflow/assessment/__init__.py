"""Outcome assessment (Phase 7): a synthetic-only engineering demonstration.

An assessment reads only what a lawyer accepted in one analysis run (Phase 6)
and the judgment passages behind the accepted precedent comparisons. It asks a
provider how those precedents bear on the position, checks every reference and
quote against those inputs, and keeps only what verifies. It is off by default
(``LEXFLOW_OUTCOME_ASSESSMENT``), allowed only with a test or e2e database, and
produced only by the scripted (non-AI) provider: no real model, no real law.

- ``inputs``: what an assessment may use, and the evidence gate;
- ``prompt`` and ``output``: the instructions and the JSON contract;
- ``validation``: the strict checks (``assessment-grounding-1``);
- ``provider`` and ``scripted``: the provider seam and the scripted double;
- ``service``: generating, storing and reviewing assessments.

See ``docs/PHASE7_PLAN.md`` and ``docs/adr/0021-outcome-assessment-demo.md``.
"""
