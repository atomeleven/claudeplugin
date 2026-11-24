"""Load saved Atom11 query_data answers and prove whether they are complete.

Every saved file must be a list of query_data answers (one per page) copied
exactly from the tool result, each keeping at least:
  rows, page, total_pages, total_count, has_next
A file is complete only when every page 1..total_pages is present and the
number of rows equals total_count. Plain lists of rows carry no proof, so they
count as incomplete: callers must then say "not checked", never "none".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_answers(path: str | None) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    """Return (rows, proof). rows is None when the file is missing or holds an error."""
    proof: dict[str, Any] = {"complete": False, "rows": 0, "total_count": None, "reason": ""}
    if not path or not Path(path).exists():
        proof["reason"] = "file not provided"
        return None, proof
    raw = json.loads(Path(path).read_text())
    answers = raw if isinstance(raw, list) else [raw]
    if answers and not all(isinstance(a, dict) and "rows" in a for a in answers):
        rows = [r for r in answers if isinstance(r, dict)]
        proof.update(rows=len(rows), reason="saved as plain rows without page/total_count, so completeness is unproven")
        return rows, proof
    rows: list[dict[str, Any]] = []
    pages: set[int] = set()
    totals: set[int] = set()
    total_pages: set[int] = set()
    for answer in answers:
        if answer.get("error"):
            proof["reason"] = f"tool error: {answer.get('error')}"
            return None, proof
        rows.extend(r for r in answer.get("rows", []) if isinstance(r, dict))
        if answer.get("page") is not None:
            pages.add(int(answer["page"]))
        if answer.get("total_count") is not None:
            totals.add(int(answer["total_count"]))
        if answer.get("total_pages") is not None:
            total_pages.add(int(answer["total_pages"]))
    proof["rows"] = len(rows)
    if len(totals) != 1 or len(total_pages) != 1:
        proof["reason"] = "total_count/total_pages missing or inconsistent between pages"
        return rows, proof
    total, tp = totals.pop(), total_pages.pop()
    proof["total_count"] = total
    if pages != set(range(1, tp + 1)) and not (tp == 0 and pages <= {1}):
        missing = sorted(set(range(1, tp + 1)) - pages)
        proof["reason"] = f"pages missing: {missing[:10]}{' …' if len(missing) > 10 else ''}"
        return rows, proof
    if len(rows) != total:
        proof["reason"] = f"{len(rows)} rows saved but the tool reported {total}"
        return rows, proof
    proof["complete"] = True
    return rows, proof


def describe(proof: dict[str, Any]) -> str:
    if proof.get("complete"):
        return f"complete ({proof['rows']} of {proof['total_count']} rows)"
    return f"incomplete ({proof.get('reason') or 'unknown reason'})"
