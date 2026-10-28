"""/newsletter 오케스트레이터가 쓰는 결정론적 도구 모음.

    python scripts/pipeline.py status [호]          # 단계별 진행 상황 (호 생략 시 직전 주)
    python scripts/pipeline.py default-issue        # 직전 주 호 번호
    python scripts/pipeline.py merge-sources 호     # sources-*.json → sources.json
    python scripts/pipeline.py new-issue 호         # 템플릿으로 issues/<호>/ 만들기
    python scripts/pipeline.py topics               # 발행된 호의 주제 목록 (중복 방지용)
    python scripts/pipeline.py pr-body 호           # PR 본문 → pipeline/<호>/pr-body.md
    python scripts/pipeline.py tier URL             # 화이트리스트 등급

판단이 필요 없는 일은 모두 여기서 한다. 에이전트는 이 결과를 읽고 판단만 한다.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_frontmatter import split_frontmatter  # noqa: E402
from common import ROOT, issue_of, lookup_tier, publish_date, read_json, week_bounds, write_json  # noqa: E402
from validate_schema import validate_file  # noqa: E402

RESEARCH_ROLES = ("global", "korea", "academic")

# (번호, 이름, 완료를 판단하는 파일). 파일이 있으면 그 단계는 끝난 것으로 본다.
STAGES = [
    (0, "피드백 수집", ["feedback.md"]),
    (1, "리서치", ["sources.json"]),
    (2, "출처 검증", ["verified.json"]),
    (3, "분석·선정", ["brief.md"]),
    (4, "자료 보강", ["background-verified.json"]),
    (5, "집필", ["../../issues/{issue}/index.qmd", "../../issues/{issue}/references.json"]),
    (6, "검수", ["review.json"]),
    (7, "PR", ["pr-body.md"]),
]


def default_issue(today: date | None = None) -> str:
    """직전 주. 월요일에 돌리면 어제 끝난 주가 된다."""
    today = today or date.today()
    return issue_of(today - timedelta(days=7))


def pipeline_dir(issue: str, root: Path = ROOT) -> Path:
    return root / "pipeline" / issue


# ── status ───────────────────────────────────────────────────


def status(issue: str, root: Path = ROOT) -> list[dict]:
    d = pipeline_dir(issue, root)
    out = []
    for num, name, files in STAGES:
        paths = [(d / f.format(issue=issue)).resolve() for f in files]
        done = all(p.exists() for p in paths)
        out.append({"stage": num, "name": name, "done": done, "files": [str(p.relative_to(root.resolve())) for p in paths]})
    return out


def next_stage(issue: str, root: Path = ROOT) -> int | None:
    for s in status(issue, root):
        if not s["done"]:
            return s["stage"]
    return None


def verification_summary(path: Path) -> dict:
    if not path.exists():
        return {}
    items = read_json(path)["items"]
    v = [i["verification"] for i in items]
    return {
        "total": len(items),
        "verified": sum(x["verified"] for x in v),
        "needs_agent": sum(x["needs_agent"] for x in v),
        "failed": sum(not x["verified"] and not x["needs_agent"] for x in v),
    }


# ── merge-sources ─────────────────────────────────────────────


def merge_sources(issue: str, root: Path = ROOT) -> tuple[Path, list[str]]:
    """리서치 에이전트가 따로 쓴 sources-<역할>.json 을 하나로 합친다. (결과 경로, 오류)."""
    d = pipeline_dir(issue, root)
    errors: list[str] = []
    items: list[dict] = []
    found = 0
    for role in RESEARCH_ROLES:
        p = d / f"sources-{role}.json"
        if not p.exists():
            errors.append(f"{p.name} 가 없습니다")
            continue
        found += 1
        errs = validate_file(p)
        if errs:
            errors += [f"{p.name}: {e}" for e in errs]
            continue
        items += read_json(p)["items"]
    ids = [i["id"] for i in items]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errors.append(f"리서치 결과끼리 id 가 겹칩니다: {', '.join(dup)}")
    out = d / "sources.json"
    if not errors:
        write_json(out, {"issue": issue, "stage": "sources", "items": items})
    return out, errors


# ── new-issue ─────────────────────────────────────────────────


def new_issue(issue: str, root: Path = ROOT) -> Path:
    """템플릿을 복사하고 호 번호·기간·발행일을 채운다. 이미 있으면 건드리지 않는다."""
    dest = root / "issues" / issue
    if dest.exists():
        return dest
    shutil.copytree(root / "issues" / "_template", dest)
    start, end = week_bounds(issue)
    qmd = dest / "index.qmd"
    text = qmd.read_text(encoding="utf-8")
    text = re.sub(r'^issue: "[^"]*"', f'issue: "{issue}"', text, count=1, flags=re.M)
    text = re.sub(r"^  start: \S+", f"  start: {start}", text, count=1, flags=re.M)
    text = re.sub(r"^  end: \S+", f"  end: {end}", text, count=1, flags=re.M)
    text = re.sub(r"^date: \S+", f"date: {publish_date(issue)}", text, count=1, flags=re.M)
    qmd.write_text(text, encoding="utf-8", newline="\n")
    (dest / "references.json").unlink(missing_ok=True)
    return dest


# ── topics ────────────────────────────────────────────────────


def published_topics(root: Path = ROOT) -> list[dict]:
    """발행된(=main 에 있는) 호들의 주제와 이슈 제목. 최신 호가 앞."""
    out = []
    for qmd in sorted((root / "issues").glob("*/index.qmd"), reverse=True):
        if qmd.parent.name.startswith("_"):
            continue
        fm, body = split_frontmatter(qmd.read_text(encoding="utf-8"))
        headlines = re.findall(r"^### (.+)$", body, flags=re.M)
        out.append({"issue": fm.get("issue"), "title": fm.get("title"), "topics": fm.get("topics", []), "headlines": headlines})
    return out


# ── pr-body ───────────────────────────────────────────────────


def pr_body(issue: str, root: Path = ROOT) -> str:
    d = pipeline_dir(issue, root)
    qmd = root / "issues" / issue / "index.qmd"
    fm, body = split_frontmatter(qmd.read_text(encoding="utf-8"))
    start, end = week_bounds(issue)
    lines = [f"## 기후·환경 주간 브리핑 {issue} ({start:%m.%d}–{end:%m.%d})", "", f"**{fm['title']}**", ""]

    lines += ["### 이번 호 이슈", ""]
    for h in re.findall(r"^### (.+)$", body, flags=re.M):
        lines.append(f"- {h}")

    lines += ["", "### 출처 검증", ""]
    for name, label in (("verified.json", "이번 주 출처"), ("background-verified.json", "배경·장기 자료")):
        s = verification_summary(d / name)
        if s:
            lines.append(f"- {label}: 전체 {s['total']} · 통과 {s['verified']} · 에이전트 확인 대기 {s['needs_agent']} · 제외 {s['failed']}")
    refs = root / "issues" / issue / "references.json"
    if refs.exists():
        lines.append(f"- 본문에서 인용한 출처: {len(read_json(refs))}개 (모두 검증 통과)")
    if fm.get("series_used"):
        lines.append(f"- 사용한 장기 자료: {', '.join(fm['series_used'])}")

    lines += ["", "### 검수", ""]
    review = d / "review.json"
    if review.exists():
        r = read_json(review)
        verdict = "통과" if r["verdict"] == "pass" else "**미해결 항목 있음**"
        lines.append(f"- 결과: {verdict} (반려 {fm.get('review_rounds', 0)}회)")
        for i in r["issues"]:
            lines.append(f"  - [{i['check']}] {i['location']}: {i['detail']}")
    else:
        lines.append("- 검수 결과 없음")

    lines += [
        "",
        "### 승인 전 체크리스트 (METHODOLOGY.md 7절)",
        "",
        "- [ ] 세 줄 요약이 본문 내용과 맞는가",
        "- [ ] 이슈마다 출처 링크를 하나 이상 직접 열어 보았는가 (무작위 2개 이상, 논문 1개 포함)",
        "- [ ] 수치에 단위, 기준 기간, 비교 대상이 있는가",
        "- [ ] 장기 자료 차트의 기간과 원천이 맞고, 본문 수치와 일치하는가",
        "- [ ] 필자의 해석과 출처의 주장이 구분되어 있는가",
        "- [ ] 검수 미해결 항목이 있다면 처리했는가",
        "- [ ] 미리보기 렌더링에서 차트와 레이아웃이 깨지지 않았는가",
        "- [ ] 정치적으로 한쪽에 치우친 표현은 없는가",
        "",
        "머지하면 발행됩니다. 단계별 산출물은 `pipeline/" + issue + "/` 에 있습니다.",
        "",
        "🤖 Generated with [Claude Code](https://claude.com/claude-code)",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("status", "merge-sources", "new-issue", "pr-body"):
        p = sub.add_parser(name)
        p.add_argument("issue", nargs="?" if name == "status" else None)
    sub.add_parser("default-issue")
    sub.add_parser("tier").add_argument("url")
    sub.add_parser("topics")
    args = ap.parse_args(argv)

    if args.cmd == "default-issue":
        print(default_issue())
    elif args.cmd == "status":
        issue = args.issue or default_issue()
        start, end = week_bounds(issue)
        print(f"{issue} ({start}~{end}, 발행 {publish_date(issue)})")
        for s in status(issue):
            print(f"  {'✓' if s['done'] else '·'} {s['stage']} {s['name']}")
        nxt = next_stage(issue)
        print(f"다음 단계: {nxt if nxt is not None else '없음 (완료)'}")
    elif args.cmd == "merge-sources":
        out, errors = merge_sources(args.issue)
        for e in errors:
            print(f"오류: {e}")
        if errors:
            return 1
        print(f"{out.relative_to(ROOT).as_posix()}: {len(read_json(out)['items'])}개 항목")
    elif args.cmd == "new-issue":
        print(new_issue(args.issue).relative_to(ROOT).as_posix())
    elif args.cmd == "tier":
        tier, org, blocked = lookup_tier(args.url)
        print(f"{tier}	{org or '목록 밖'}" + ("	차단" if blocked else ""))
    elif args.cmd == "topics":
        print(json.dumps(published_topics(), ensure_ascii=False, indent=2))
    elif args.cmd == "pr-body":
        out = pipeline_dir(args.issue) / "pr-body.md"
        out.write_text(pr_body(args.issue), encoding="utf-8", newline="\n")
        print(out.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
