"""각 호가 형식을 지키는지 검사한다. CI 의 PR 점검에서도 돈다.

    python scripts/check_frontmatter.py              # issues/ 아래 모든 호
    python scripts/check_frontmatter.py issues/2026-W43 issues/_sample

검사 항목
    - 프론트매터 필수 필드와 형식
    - 폴더명 = issue, period = 대상 주(월~일), date ≥ 다음 월요일
    - 본문의 모든 [@id] 가 references.json 에 있는가
    - 세 줄 요약이 정확히 3줄인가
    - 템플릿 안내 주석이나 자리 표시가 남아 있지 않은가
    - series_used 가 장기 자료 레지스트리에 있는가 (레지스트리가 있을 때)

오류가 있으면 exit code 1. 경고는 출력만 한다.
_ 로 시작하는 폴더(템플릿·견본)는 기본 검사 대상이 아니며, 직접 지정하면
폴더명 검사만 건너뛰고 나머지를 본다.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ISSUE_RE, ROOT, publish_date, read_json, week_bounds  # noqa: E402

ISSUES = ROOT / "issues"
REGISTRY = ROOT / "editorial" / "series-registry.yml"

REQUIRED = ("title", "description", "issue", "period", "date", "topics", "regions", "series_used", "review_rounds", "bibliography")
REGIONS = {"global", "korea"}
TITLE_MAX = 40
# [@g-01] [@g-01; @k-02] [-@a-01] 등. 이메일 주소(foo@bar)와 구분하려고 대괄호 안만 본다.
CITE_RE = re.compile(r"\[[^\]]*?@[^\]]*\]")
# @ 앞이 대괄호 시작이나 공백·세미콜론이어야 인용으로 본다. [메일 foo@bar.com] 은 제외.
CITE_ID_RE = re.compile(r"(?:^\[|[\s;])-?@([A-Za-z0-9_:.\-]*[A-Za-z0-9_])")
PLACEHOLDERS = ("<series-id>", "이슈 제목: 무엇이 일어났는지", "이번 주 가장 큰 이슈를 담은 제목")


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        raise ValueError("프론트매터(--- ... ---)가 없습니다")
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def _as_date(v) -> date | None:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None


def check_issue(folder: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    qmd = folder / "index.qmd"
    if not qmd.exists():
        return [f"{qmd} 가 없습니다"], []
    try:
        fm, body = split_frontmatter(qmd.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return [str(e)], []

    for k in REQUIRED:
        if k not in fm:
            errors.append(f"프론트매터에 {k} 가 없습니다")
    if errors:
        return errors, warnings

    # 제목·설명
    title = str(fm["title"])
    if len(title) > TITLE_MAX:
        warnings.append(f"제목이 {len(title)}자입니다 ({TITLE_MAX}자 이내 권장)")
    if not str(fm["description"]).strip():
        errors.append("description 이 비어 있습니다")

    # 호 번호와 기간
    issue = str(fm["issue"])
    if not ISSUE_RE.match(issue):
        errors.append(f"issue 형식이 아닙니다(YYYY-Www): {issue}")
    else:
        if not folder.name.startswith("_") and folder.name != issue:
            errors.append(f"폴더명({folder.name})과 issue({issue})가 다릅니다")
        start, end = week_bounds(issue)
        period = fm["period"] if isinstance(fm["period"], dict) else {}
        p_start, p_end = _as_date(period.get("start")), _as_date(period.get("end"))
        if (p_start, p_end) != (start, end):
            errors.append(f"period 가 {issue} 의 기간({start}~{end})과 다릅니다: {period.get('start')}~{period.get('end')}")
        d = _as_date(fm["date"])
        if d is None:
            errors.append(f"date 형식이 아닙니다: {fm['date']}")
        elif d < publish_date(issue):
            errors.append(f"발행일 {d} 이 대상 주가 끝나기 전입니다 (가장 이른 발행일 {publish_date(issue)})")

    # 목록형 필드
    for k in ("topics", "regions", "series_used"):
        if not isinstance(fm[k], list):
            errors.append(f"{k} 는 목록이어야 합니다")
    if isinstance(fm["regions"], list) and not set(fm["regions"]) <= REGIONS:
        errors.append(f"regions 는 {sorted(REGIONS)} 중에서: {fm['regions']}")
    if not isinstance(fm["review_rounds"], int) or fm["review_rounds"] < 0:
        errors.append("review_rounds 는 0 이상의 정수여야 합니다")
    if isinstance(fm["series_used"], list) and fm["series_used"] and REGISTRY.exists():
        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
        known = set((registry.get("series") or {}).keys())
        for s in fm["series_used"]:
            if s not in known:
                errors.append(f"series_used 의 {s} 가 레지스트리에 없습니다")

    # 출처
    if fm["bibliography"] != "references.json":
        errors.append("bibliography 는 references.json 이어야 합니다")
    refs_path = folder / "references.json"
    ref_ids: set[str] = set()
    if not refs_path.exists():
        errors.append("references.json 이 없습니다")
    else:
        try:
            refs = read_json(refs_path)
            ref_ids = {r["id"] for r in refs}
            for r in refs:
                for k in ("id", "type", "title"):
                    if not r.get(k):
                        errors.append(f"references.json 의 {r.get('id', '?')} 에 {k} 가 없습니다")
        except Exception as e:  # noqa: BLE001
            errors.append(f"references.json 을 읽을 수 없습니다: {e}")

    prose = re.sub(r"```.*?```", "", body, flags=re.S)
    cited = {m for c in CITE_RE.findall(prose) for m in CITE_ID_RE.findall(c)}
    for c in sorted(cited - ref_ids):
        errors.append(f"본문에서 인용한 [@{c}] 가 references.json 에 없습니다")
    for r in sorted(ref_ids - cited):
        warnings.append(f"references.json 의 {r} 를 본문에서 인용하지 않았습니다")

    # 세 줄 요약
    m = re.search(r":::\s*\{\.summary[^}]*\}\s*\n(.*?)\n:::", body, re.S)
    if not m:
        errors.append("세 줄 요약 블록(::: {.summary})이 없습니다")
    else:
        bullets = [ln for ln in m.group(1).splitlines() if re.match(r"\s*[-*]\s+\S", ln)]
        if len(bullets) != 3:
            errors.append(f"세 줄 요약이 {len(bullets)}줄입니다 (3줄이어야 함)")

    # 남은 안내 문구
    if "<!--" in body and not folder.name.startswith("_"):
        errors.append("템플릿 안내 주석(<!-- -->)이 남아 있습니다")
    for p in PLACEHOLDERS:
        if p in body or p in title:
            errors.append(f"템플릿 자리 표시가 남아 있습니다: {p}")

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folders", nargs="*", type=Path)
    args = ap.parse_args(argv)

    folders = args.folders or sorted(p for p in ISSUES.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))
    if not folders:
        print("검사할 호가 없습니다.")
        return 0

    failed = 0
    for f in folders:
        errors, warnings = check_issue(f)
        mark = "✗" if errors else "✓"
        print(f"{mark} {f.as_posix()}")
        for e in errors:
            print(f"    오류: {e}")
        for w in warnings:
            print(f"    경고: {w}")
        failed += bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
