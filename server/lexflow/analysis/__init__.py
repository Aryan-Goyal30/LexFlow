"""AI case analysis (Phase 5).

The pieces, in the order a run uses them:

- ``evidence``: the passages a run may use, each with an opaque id (``D1`` for
  a case-document passage, ``J1`` for a judgment passage);
- ``prompt``: the versioned instructions and the rendering of the evidence;
- ``output``: the JSON shape the model is asked for, and its lenient parsing;
- ``provider``: the model behind an interface (``GeminiProvider``; the
  ``scripted`` test double lives in ``scripted``);
- ``validation``: checks every item against the evidence before anything is
  stored or shown;
- ``runs``: the queue of runs and the worker step that ties them together.

Model output is untrusted input throughout. Validation decides what is kept;
the model's own claims about its sources are never taken on trust.
"""
