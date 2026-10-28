"""실제 네트워크로 DOI·원문을 확인하는 시험. 기본 실행에서는 빠진다.

    pytest -m network

대상: Friedlingstein 외, "Global Carbon Budget 2023", Earth System Science Data (2023).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import verify_sources as vs  # noqa: E402

pytestmark = pytest.mark.network

GCB = {
    "id": "a-01",
    "region": "global",
    "kind": "paper",
    "role": "trigger",
    "topic": "배출량",
    "title": "Global Carbon Budget 2023",
    "publisher": "Earth System Science Data",
    "authors": ["Friedlingstein, Pierre"],
    "url": "https://essd.copernicus.org/articles/15/5301/2023/",
    "doi": "10.5194/essd-15-5301-2023",
    "published_at": "2023-12-05",
    "peer_reviewed": True,
    "tier": 1,
    "quote": "Accurate assessment of anthropogenic carbon dioxide (CO2) emissions and their redistribution among the atmosphere, ocean, and terrestrial biosphere",
    "claims": ["x"],
}


def run(item):
    return vs.verify_item(item, "2023-W49", vs.http_fetch, vs.crossref_lookup, today=date.today())


def test_real_paper_passes():
    v = run(dict(GCB))
    assert v["doi_ok"] is True, v["notes"]
    assert v["quote_match"] == "exact", v["notes"]
    assert v["verified"], v["notes"]


def test_real_doi_with_wrong_title_fails():
    v = run({**GCB, "title": "Global Carbon Budget 1999"})
    assert v["doi_ok"] is False and not v["verified"]


def test_nonexistent_doi_fails():
    v = run({**GCB, "doi": "10.5194/essd-99-9999-2099"})
    assert v["doi_ok"] is False and not v["verified"] and not v["needs_agent"]


def test_fabricated_quote_fails():
    v = run({**GCB, "quote": "Global emissions fell by half in 2023 according to this budget."})
    assert v["quote_match"] == "missing" and not v["verified"]
