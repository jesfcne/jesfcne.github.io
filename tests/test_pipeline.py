"""검증 스크립트의 통과·실패 사례. 네트워크 없이 돈다(가짜 fetch/Crossref 사용)."""

from __future__ import annotations

import copy
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_frontmatter  # noqa: E402
import make_references  # noqa: E402
import validate_schema  # noqa: E402
import verify_sources as vs  # noqa: E402
from common import issue_of, lookup_tier, publish_date, week_bounds  # noqa: E402

EXAMPLE = ROOT / "scripts" / "schema" / "examples" / "sources.json"
TODAY = date(2026, 10, 26)


def example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def write(tmp_path: Path, data: dict, name: str = "sources.json", folder: str = "2026-W43") -> Path:
    d = tmp_path / folder
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# ── 주차 ──────────────────────────────────────────────────────


def test_week_bounds_and_publish_date():
    assert week_bounds("2026-W43") == (date(2026, 10, 19), date(2026, 10, 25))
    assert publish_date("2026-W43") == date(2026, 10, 26)
    assert issue_of(date(2026, 10, 25)) == "2026-W43"
    # 연도가 걸친 주: 2026-12-28(월)~2027-01-03(일)은 2026-W53
    assert week_bounds("2026-W53") == (date(2026, 12, 28), date(2027, 1, 3))


# ── 화이트리스트 ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "url, tier",
    [
        ("https://public.wmo.int/en/media", 1),
        ("https://www.kma.go.kr/x", 1),
        ("https://www.nature.com/articles/s41558-026-00000-0", 1),   # 논문
        ("https://www.nature.com/articles/d41586-026-00000-0", 2),   # 뉴스
        ("https://www.nature.com/collections/xyz", 0),               # 경로가 어디에도 안 맞음
        ("https://egusphere.copernicus.org/preprints/2026/x", 2),    # 하위 도메인이 더 구체적
        ("https://essd.copernicus.org/articles/15/5301/2023/", 1),
        ("https://www.reuters.com/sustainability/x", 3),
        ("https://www.yna.co.kr/view/x", 3),
        ("https://example-blog.com/post", 0),
        ("https://notwmo.int/x", 0),                                 # 접미사만 같은 다른 도메인
    ],
)
def test_lookup_tier(url, tier):
    assert lookup_tier(url)[0] == tier


# ── 스키마 ────────────────────────────────────────────────────


def test_schema_example_passes(tmp_path):
    assert validate_schema.validate_file(write(tmp_path, example())) == []


@pytest.mark.parametrize(
    "mutate, expect",
    [
        (lambda d: d["items"][0].pop("quote"), "quote"),
        (lambda d: d["items"][2].pop("doi"), "doi"),                                   # 논문인데 DOI 없음
        (lambda d: d["items"][2].update(kind="preprint"), "False was expected"),       # 프리프린트인데 peer_reviewed true
        (lambda d: d["items"][1].update(id="g-01"), "중복"),
        (lambda d: d["items"][0].update(role="background"), "does not match"),         # background 인데 g- 접두어
        (lambda d: d["items"][0].update(published_at="2026-10"), "does not match"),    # trigger 는 일 단위 날짜 필요
        (lambda d: d["items"][0].update(published_at="2026-02-30"), "날짜"),
        (lambda d: d["items"][0].update(tier=5), "maximum"),
        (lambda d: d.update(issue="2026-W44"), "폴더명"),
        (lambda d: d["items"][0].update(extra="x"), "Additional properties"),
    ],
)
def test_schema_failures(tmp_path, mutate, expect):
    data = example()
    mutate(data)
    errors = validate_schema.validate_file(write(tmp_path, data))
    assert errors, "실패해야 하는데 통과했다"
    assert any(expect in e for e in errors), errors


def test_review_schema(tmp_path):
    ok = {"issue": "2026-W43", "round": 1, "verdict": "pass", "issues": []}
    assert validate_schema.validate_file(write(tmp_path, ok, "review.json")) == []
    bad = {**ok, "verdict": "revise"}  # 반려인데 지적이 없음
    assert validate_schema.validate_file(write(tmp_path, bad, "review.json"))
    bad2 = {**ok, "issues": [{"location": "이슈 1", "check": "수치", "detail": "x", "fix": "y"}]}  # 통과인데 지적이 있음
    assert validate_schema.validate_file(write(tmp_path, bad2, "review.json"))


# ── 출처 검증 ──────────────────────────────────────────────────

LONG = " 본문 내용이 이어진다." * 60


def fake_fetch(pages: dict):
    def fetch(url):
        return pages.get(url, vs.Page(404, url, ""))
    return fetch


def crossref_ok(doi):
    return {
        "title": ["An example study of extreme precipitation"],
        "author": [{"family": "Kim", "given": "Ara"}],
        "container-title": ["Nature Climate Change"],
        "published-online": {"date-parts": [[2026, 10, 20]]},
        "abstract": "<jats:p>We find that the frequency of extreme precipitation events increases in most regions.</jats:p>",
    }


def item(i):
    return copy.deepcopy(example()["items"][i])


def verify(it, pages, crossref=crossref_ok):
    return vs.verify_item(it, "2026-W43", fake_fetch(pages), crossref, today=TODAY)


def test_verify_pass():
    it = item(0)
    v = verify(it, {it["url"]: vs.Page(200, it["url"], LONG + it["quote"] + LONG)})
    assert v["verified"] and not v["needs_agent"], v
    assert v["quote_match"] == "exact" and v["date_in_window"] is True and v["tier_ok"]


def test_verify_quote_normalized():
    it = item(0)
    text = LONG + "Concentrations of the three main greenhouse  gases\nreached new highs in the example year." + LONG
    assert verify(it, {it["url"]: vs.Page(200, it["url"], text)})["verified"]


def test_verify_quote_missing_is_hard_fail():
    it = item(0)
    v = verify(it, {it["url"]: vs.Page(200, it["url"], LONG + "전혀 다른 내용" + LONG)})
    assert not v["verified"] and not v["needs_agent"]
    assert v["quote_match"] == "missing"


def test_verify_quote_approx_needs_agent():
    it = item(0)
    text = LONG + "Concentrations of the three main greenhouse gases reached record highs in the example year." + LONG
    v = verify(it, {it["url"]: vs.Page(200, it["url"], text)})
    assert v["quote_match"] == "approx" and v["needs_agent"] and not v["verified"]


def test_verify_404_is_hard_fail():
    it = item(0)
    v = verify(it, {})
    assert v["url_ok"] is False and not v["verified"] and not v["needs_agent"]


@pytest.mark.parametrize("status", [403, 429, 503])
def test_verify_blocked_needs_agent(status):
    it = item(0)
    v = verify(it, {it["url"]: vs.Page(status, it["url"], "")})
    assert v["needs_agent"] and not v["verified"]


def test_verify_dynamic_page_needs_agent():
    it = item(0)
    v = verify(it, {it["url"]: vs.Page(200, it["url"], "Loading...")})
    assert v["needs_agent"] and not v["verified"]


def test_verify_out_of_window_is_hard_fail():
    it = item(0)
    it["published_at"] = "2026-10-12"
    v = verify(it, {it["url"]: vs.Page(200, it["url"], LONG + it["quote"] + LONG)})
    assert v["date_in_window"] is False and not v["verified"] and not v["needs_agent"]


def test_verify_background_ignores_window():
    it = item(0)
    it.update(id="b-01", role="background", published_at="2019-03")
    v = verify(it, {it["url"]: vs.Page(200, it["url"], LONG + it["quote"] + LONG)})
    assert v["date_in_window"] is None and v["verified"]


def test_verify_tier_mismatch_needs_agent():
    it = item(0)
    it["tier"] = 2
    v = verify(it, {it["url"]: vs.Page(200, it["url"], LONG + it["quote"] + LONG)})
    assert not v["tier_ok"] and v["needs_agent"] and not v["verified"]


def test_verify_paper_via_crossref_abstract():
    # 논문 페이지가 페이월이어도 Crossref 초록으로 인용문을 확인할 수 있다.
    it = item(2)
    v = verify(it, {it["url"]: vs.Page(200, it["url"], LONG)})
    assert v["doi_ok"] and v["quote_match"] == "exact" and v["verified"], v


def test_verify_doi_not_found():
    it = item(2)
    v = verify(it, {it["url"]: vs.Page(200, it["url"], LONG + it["quote"])}, crossref=lambda doi: None)
    assert v["doi_ok"] is False and not v["verified"] and not v["needs_agent"]


def test_verify_doi_title_mismatch():
    it = item(2)
    it["title"] = "A completely different paper about glaciers"
    v = verify(it, {it["url"]: vs.Page(200, it["url"], LONG + it["quote"])})
    assert v["doi_ok"] is False and not v["verified"]


def test_verify_doi_author_mismatch():
    it = item(2)
    it["authors"] = ["Smith, John"]
    v = verify(it, {it["url"]: vs.Page(200, it["url"], LONG + it["quote"])})
    assert v["doi_ok"] is False


def test_verify_crossref_error_needs_agent():
    def boom(doi):
        raise ConnectionError("down")
    it = item(2)
    v = verify(it, {it["url"]: vs.Page(200, it["url"], LONG + it["quote"])}, crossref=boom)
    assert v["needs_agent"] and not v["verified"]


def test_run_writes_valid_verified_file(tmp_path):
    src = write(tmp_path, example())
    pages = {i["url"]: vs.Page(200, i["url"], LONG + i["quote"] + LONG) for i in example()["items"]}
    result = vs.run(src, fetch=fake_fetch(pages), crossref=crossref_ok, delay=0, today=TODAY)
    out = write(tmp_path, result, "verified.json")
    assert validate_schema.validate_file(out) == []
    assert all(i["verification"]["verified"] for i in result["items"])


# ── 호 검사와 references.json ─────────────────────────────────


def make_issue(tmp_path: Path, folder="2026-W43", **overrides) -> Path:
    d = tmp_path / folder
    shutil.copytree(ROOT / "issues" / "_sample", d)
    qmd = d / "index.qmd"
    text = qmd.read_text(encoding="utf-8")
    for old, new in overrides.items():
        text = text.replace(old, new)
    qmd.write_text(text, encoding="utf-8")
    return d


def test_issue_sample_passes(tmp_path):
    errors, _ = check_frontmatter.check_issue(make_issue(tmp_path))
    assert errors == []


@pytest.mark.parametrize(
    "folder, replace, expect",
    [
        ("2026-W44", {}, "폴더명"),
        ("2026-W43", {"start: 2026-10-19": "start: 2026-10-20"}, "period"),
        ("2026-W43", {"date: 2026-10-26": "date: 2026-10-24"}, "발행일"),
        ("2026-W43", {"[@g-02]": "[@g-99]"}, "g-99"),
        ("2026-W43", {"- 새 연구는": "- 하나 더\n- 새 연구는"}, "세 줄 요약"),
        ("2026-W43", {"regions: [global, korea]": "regions: [global, asia]"}, "regions"),
        ("2026-W43", {"## 정정": "<!-- 지울 것 -->\n## 정정"}, "주석"),
    ],
)
def test_issue_failures(tmp_path, folder, replace, expect):
    errors, _ = check_frontmatter.check_issue(make_issue(tmp_path, folder, **replace))
    assert any(expect in e for e in errors), errors


def test_citation_regex_ignores_email():
    ids = {i for c in check_frontmatter.CITE_RE.findall("문의 [jesfcne+notes@gmail.com] 그리고[@g-01; @k-02]. [-@a-01]")
           for i in check_frontmatter.CITE_ID_RE.findall(c)}
    assert ids == {"g-01", "k-02", "a-01"}


def test_make_references(tmp_path):
    issue_dir = tmp_path / "issues" / "2026-W43"
    issue_dir.mkdir(parents=True)
    (issue_dir / "index.qmd").write_text("---\ntitle: x\n---\n\n밝혔다[@g-01]. 연구[@a-01].\n", encoding="utf-8")
    data = example()
    for i in data["items"]:
        i["verification"] = {"checked_at": "2026-10-26", "checked_by": "script", "verified": True, "needs_agent": False, "notes": []}
    pipe = tmp_path / "pipeline" / "2026-W43"
    pipe.mkdir(parents=True)
    (pipe / "verified.json").write_text(json.dumps({**data, "stage": "verified"}, ensure_ascii=False), encoding="utf-8")

    refs, errors = make_references.build("2026-W43", root=tmp_path)
    assert errors == []
    assert [r["id"] for r in refs] == ["g-01", "a-01"]
    paper = refs[1]
    assert paper["type"] == "article-journal" and paper["DOI"] == "10.1038/s41558-026-00000-0"
    assert paper["author"][0] == {"family": "Kim", "given": "Ara"}
    assert paper["issued"] == {"date-parts": [[2026, 10, 20]]}

    # 검증을 통과하지 못한 출처를 인용하면 만들지 않는다.
    data["items"][2]["verification"]["verified"] = False
    (pipe / "verified.json").write_text(json.dumps({**data, "stage": "verified"}, ensure_ascii=False), encoding="utf-8")
    _, errors = make_references.build("2026-W43", root=tmp_path)
    assert any("a-01" in e for e in errors)

    # 검증 파일에 없는 출처
    (issue_dir / "index.qmd").write_text("---\ntitle: x\n---\n\n[@g-07]\n", encoding="utf-8")
    _, errors = make_references.build("2026-W43", root=tmp_path)
    assert any("g-07" in e for e in errors)
