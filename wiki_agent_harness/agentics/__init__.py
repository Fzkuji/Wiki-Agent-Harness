"""Agentic entry points for the wiki harness.

Exposes a single ``@agentic_function`` — :func:`wiki_agent` — that
dispatches a natural-language wiki request to the right internal
operation (ingest / enrich / browse / lint / search). The dispatcher
itself uses :func:`openprogram.agentic_programming.decision.make` to
route; the per-branch handlers are plain Python that call into
:class:`wiki_agent_harness.Wiki`.

Import is conditional on openprogram being installed; absent
openprogram, the harness still works through the plain Python ``Wiki``
class.
"""
from __future__ import annotations

try:
    from .wiki_agent import wiki_agent
    AGENTIC_FUNCTIONS = [wiki_agent]
except ImportError:
    AGENTIC_FUNCTIONS = []

__all__ = ["AGENTIC_FUNCTIONS"]
