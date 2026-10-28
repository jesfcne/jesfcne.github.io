"""원고가 인용한 출처로 references.json 을 만든다 (파이프라인 ⑤ 집필 단계의 마무리).

    python scripts/make_references.py 2026-W43

issues/<호>/index.qmd 의 [@id] 를 모두 찾고, pipeline/<호>/verified.json 과
background-verified.json 에서 그 id 를 찾아 CSL JSON 으로 바꿔
issues/<호>/references.json 에 쓴다.

검증을 통과하지 않은(verified: false) 출처를 인용했거나, 검증 파일에 없는 id 를
인용했으면 파일을 쓰지 않고 exit code 1 로 끝난다. 즉 원고는 검증된 출처만
인용할 수 있다.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_frontmatter import CITE_ID_RE, CITE_RE, split_frontmatter  # noqa: E402
from common import ROOT, parse_partial_date, read_json, write_json  # noqa: E402

CSL_TYPE = {
    "news": "article-newspaper",
    "official": "webpage",
    "report": "report",
    "paper": "article-journal",
    "preprint": "article",
    "dataset": "dataset",
}


def _names(authors: list[str]) -> list[dict]:
    out = []
    for a in authors:
        if "," in a:
            family, given = (s.strip() for s in a.split(",", 1))
            out.append({"family": family, "given": given})
        else:
            out.append({"literal": a})
    return out


def to_csl(item: dict) -> dict:
    kind = item["kind"]
    csl: dict = {
        "id": item["id"],
        "type": CSL_TYPE[kind],
        "title": item["title"],
        "URL": item["url"],
        "issued": {"date-parts": [list(parse_partial_date(item["published_at"]))]},
    }
    checked = item.get("verification", {}).get("checked_at")
    if checked:
        csl["accessed"] = {"date-parts": [list(parse_partial_date(checked))]}

    if item.get("authors"):
        csl["author"] = _names(item["authors"])
    if kind in ("paper", "preprint", "news"):
        csl["container-title"] = item["publisher"]
    else:
        csl["publisher"] = item["publisher"]
        csl.setdefault("author", [{"literal": item["publisher"]}])
    if kind == "preprint":
        csl["genre"] = "Preprint (동료심사 전)"
    if item.get("doi"):
        csl["DOI"] = item["doi"]
    if item.get("version"):
        csl["version"] = item["version"]
    return csl


def cited_ids(qmd: Path) -> list[str]:
    _, body = split_frontmatter(qmd.read_text(encoding="utf-8"))
    body = re.sub(r"```.*?```", "", body, flags=re.S)
    ids: list[str] = []
    for c in CITE_RE.findall(body):
        for i in CITE_ID_RE.findall(c):
            if i not in ids:
                ids.append(i)
    return ids


def build(issue: str, root: Path = ROOT) -> tuple[list[dict], list[str]]:
    """(references, 오류)."""
    pipeline = root / "pipeline" / issue
    pool: dict[str, dict] = {}
    for name in ("verified.json", "background-verified.json"):
        p = pipeline / name
        if p.exists():
            for item in read_json(p)["items"]:
                pool[item["id"]] = item

    errors = []
    refs = []
    for i in cited_ids(root / "issues" / issue / "index.qmd"):
        item = pool.get(i)
        if item is None:
            errors.append(f"[@{i}] 가 검증 파일에 없습니다")
        elif not item["verification"]["verified"]:
            errors.append(f"[@{i}] 는 검증을 통과하지 않았습니다: {'; '.join(item['verification']['notes']) or '사유 없음'}")
        else:
            refs.append(to_csl(item))
    return refs, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("issue", help="예: 2026-W43")
    args = ap.parse_args(argv)

    refs, errors = build(args.issue)
    if errors:
        for e in errors:
            print(f"오류: {e}")
        return 1
    out = ROOT / "issues" / args.issue / "references.json"
    write_json(out, refs)
    print(f"{out.relative_to(ROOT).as_posix()}: 출처 {len(refs)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
