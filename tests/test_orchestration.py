"""/newsletter 오케스트레이터가 쓰는 결정론적 도구(scripts/pipeline.py) 시험."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_frontmatter  # noqa: E402
import pipeline as pl  # noqa: E402

EXAMPLE = json.loads((ROOT / "scripts" / "schema" / "examples" / "sources.json").read_text(encoding="utf-8"))


def fake_root(tmp_path: Path) -> Path:
    """issues/_template 만 있는 가짜 저장소."""
    (tmp_path / "issues").mkdir()
    shutil.copytree(ROOT / "issues" / "_template", tmp_path / "issues" / "_template")
    (tmp_path / "pipeline").mkdir()
    return tmp_path


def test_default_issue_is_previous_week():
    assert pl.default_issue(date(2026, 10, 26)) == "2026-W43"   # 월요일 → 어제 끝난 주
    assert pl.default_issue(date(2026, 10, 28)) == "2026-W43"   # 수요일에 돌려도 직전 주
    assert pl.default_issue(date(2026, 1, 5)) == "2026-W01"     # 2025-12-29(월)~2026-01-04(일)은 ISO 2026-W01


def test_status_and_next_stage(tmp_path):
    root = fake_root(tmp_path)
    assert pl.next_stage("2026-W43", root) == 0
    d = root / "pipeline" / "2026-W43"
    d.mkdir()
    for f in ("feedback.md", "sources.json", "verified.json"):
        (d / f).write_text("x", encoding="utf-8")
    assert pl.next_stage("2026-W43", root) == 3


def test_merge_sources(tmp_path):
    root = fake_root(tmp_path)
    d = root / "pipeline" / "2026-W43"
    d.mkdir()
    items = EXAMPLE["items"]
    parts = {"global": [items[0]], "korea": [items[1]], "academic": [items[2]]}
    for role, its in parts.items():
        (d / f"sources-{role}.json").write_text(json.dumps({"issue": "2026-W43", "stage": "sources", "items": its}, ensure_ascii=False), encoding="utf-8")
    out, errors = pl.merge_sources("2026-W43", root)
    assert errors == []
    assert [i["id"] for i in json.loads(out.read_text(encoding="utf-8"))["items"]] == ["g-01", "k-01", "a-01"]


def test_merge_sources_reports_missing_and_invalid(tmp_path):
    root = fake_root(tmp_path)
    d = root / "pipeline" / "2026-W43"
    d.mkdir()
    bad = dict(EXAMPLE["items"][0])
    bad.pop("quote")
    (d / "sources-global.json").write_text(json.dumps({"issue": "2026-W43", "stage": "sources", "items": [bad]}), encoding="utf-8")
    _, errors = pl.merge_sources("2026-W43", root)
    assert any("sources-korea.json" in e for e in errors)
    assert any("sources-global.json" in e and "quote" in e for e in errors)
    assert not (d / "sources.json").exists()


def test_new_issue_fills_dates_and_does_not_overwrite(tmp_path):
    root = fake_root(tmp_path)
    dest = pl.new_issue("2026-W44", root)
    fm, _ = check_frontmatter.split_frontmatter((dest / "index.qmd").read_text(encoding="utf-8"))
    assert fm["issue"] == "2026-W44"
    assert str(fm["period"]["start"]) == "2026-10-26" and str(fm["period"]["end"]) == "2026-11-01"
    assert str(fm["date"]) == "2026-11-02"
    (dest / "index.qmd").write_text("수정됨", encoding="utf-8")
    pl.new_issue("2026-W44", root)
    assert (dest / "index.qmd").read_text(encoding="utf-8") == "수정됨"


def test_new_issue_from_template_still_fails_check_until_written(tmp_path):
    # 템플릿을 복사만 한 상태로는 발행 검사를 통과하면 안 된다.
    root = fake_root(tmp_path)
    errors, _ = check_frontmatter.check_issue(pl.new_issue("2026-W44", root))
    assert any("주석" in e for e in errors) and any("자리 표시" in e for e in errors)


def test_published_topics_skips_underscore(tmp_path):
    root = fake_root(tmp_path)
    shutil.copytree(ROOT / "issues" / "_sample", root / "issues" / "2026-W43")
    topics = pl.published_topics(root)
    assert [t["issue"] for t in topics] == ["2026-W43"]
    assert topics[0]["headlines"][0].startswith("예시 국제기구")


def test_pr_body(tmp_path):
    root = fake_root(tmp_path)
    shutil.copytree(ROOT / "issues" / "_sample", root / "issues" / "2026-W43")
    d = root / "pipeline" / "2026-W43"
    d.mkdir()
    v = dict(EXAMPLE, stage="verified")
    v["items"] = [dict(i, verification={"checked_at": "2026-10-26", "checked_by": "script", "verified": n != 1,
                                        "needs_agent": False, "notes": []}) for n, i in enumerate(EXAMPLE["items"])]
    (d / "verified.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    review = {"issue": "2026-W43", "round": 3, "verdict": "revise",
              "issues": [{"location": "이슈 2", "check": "수치", "detail": "기준 기간 누락", "fix": "추가"}]}
    (d / "review.json").write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    body = pl.pr_body("2026-W43", root)
    assert "2026-W43 (10.19–10.25)" in body
    assert "전체 3 · 통과 2 · 에이전트 확인 대기 0 · 제외 1" in body
    assert "미해결 항목 있음" in body and "[수치] 이슈 2: 기준 기간 누락" in body
    assert "- 예시 국제기구" in body
    assert "Generated with [Claude Code]" in body
