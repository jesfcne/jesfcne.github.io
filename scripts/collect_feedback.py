"""독자 피드백 수집 (파이프라인 0단계).

    python scripts/collect_feedback.py 2026-W43 [--since 2026-10-19]

지난 실행 이후에 들어온 피드백을 모아 pipeline/<호>/feedback-raw.json 에 쓴다.
분류(정정·제안·스타일)는 feedback 에이전트가 이 파일을 읽고 한다.

    - GitHub 이슈와 이슈 댓글 (공개 API, 인증 없이 가능)
    - Discussions 댓글 = 각 호의 giscus 댓글 (GraphQL, 토큰 필요)

토큰은 GH_TOKEN / GITHUB_TOKEN 환경 변수나 `gh auth token` 에서 가져온다.
없으면 Discussions 는 건너뛰고 그렇다고 기록한다.
--since 를 생략하면 직전 호의 feedback-raw.json 수집 시점부터, 그것도 없으면 14일 전부터.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_json, write_json  # noqa: E402

REPO = "jesfcne/jesfcne.github.io"
API = "https://api.github.com"


def token() -> str | None:
    for k in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(k):
            return os.environ[k]
    if shutil.which("gh"):
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return None


def default_since(issue: str) -> str:
    prev = sorted(p for p in (ROOT / "pipeline").glob("*/feedback-raw.json") if p.parent.name < issue)
    if prev:
        return read_json(prev[-1])["collected_at"]
    return (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(timespec="seconds")


def _get(url: str, tok: str | None, params: dict | None = None) -> list | dict:
    import requests

    headers = {"Accept": "application/vnd.github+json"}
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def issues_and_comments(since: str, tok: str | None) -> list[dict]:
    out = []
    for it in _get(f"{API}/repos/{REPO}/issues", tok, {"state": "all", "since": since, "per_page": 100}):
        if "pull_request" in it:
            continue
        out.append({"source": "issue", "url": it["html_url"], "title": it["title"], "labels": [l["name"] for l in it["labels"]],
                    "author": it["user"]["login"], "created_at": it["created_at"], "body": it.get("body") or ""})
    for c in _get(f"{API}/repos/{REPO}/issues/comments", tok, {"since": since, "per_page": 100}):
        out.append({"source": "issue-comment", "url": c["html_url"], "author": c["user"]["login"],
                    "created_at": c["created_at"], "body": c.get("body") or ""})
    return out


DISCUSSIONS_QUERY = """
query($owner:String!, $name:String!) {
  repository(owner:$owner, name:$name) {
    discussions(first: 50, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes { title url updatedAt
        comments(last: 50) { nodes { url author { login } createdAt body
          replies(last: 20) { nodes { url author { login } createdAt body } } } } }
    }
  }
}"""


def discussion_comments(since: str, tok: str) -> list[dict]:
    import requests

    owner, name = REPO.split("/")
    r = requests.post(f"{API}/graphql", json={"query": DISCUSSIONS_QUERY, "variables": {"owner": owner, "name": name}},
                      headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    r.raise_for_status()
    out = []
    for d in r.json()["data"]["repository"]["discussions"]["nodes"]:
        for c in d["comments"]["nodes"]:
            for node in [c, *c["replies"]["nodes"]]:
                if node["createdAt"] >= since:
                    out.append({"source": "discussion", "discussion": d["title"], "url": node["url"],
                                "author": (node.get("author") or {}).get("login"), "created_at": node["createdAt"],
                                "body": node["body"]})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("issue")
    ap.add_argument("--since", help="ISO 날짜/시각")
    args = ap.parse_args(argv)

    since = args.since or default_since(args.issue)
    if len(since) == 10:
        since += "T00:00:00Z"
    tok = token()
    notes = []
    items = issues_and_comments(since, tok)
    if tok:
        items += discussion_comments(since, tok)
    else:
        notes.append("GitHub 토큰이 없어 Discussions(각 호 댓글)를 확인하지 못했습니다. gh auth login 후 다시 실행하세요.")
    notes.append("메일(jesfcne+notes@gmail.com)로 온 제보는 이 스크립트가 보지 못합니다. 사람이 확인해 feedback.md 에 옮깁니다.")

    out = ROOT / "pipeline" / args.issue / "feedback-raw.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, {"issue": args.issue, "since": since,
                     "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "items": sorted(items, key=lambda x: x["created_at"]), "notes": notes})
    print(f"{out.relative_to(ROOT).as_posix()}: {len(items)}건 (since {since})")
    for n in notes:
        print(f"  참고: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
