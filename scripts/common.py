"""파이프라인 스크립트가 함께 쓰는 도구: 주차 계산, 화이트리스트 조회, 파일 입출력."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
WHITELIST = ROOT / "editorial" / "source-whitelist.yml"

ISSUE_RE = re.compile(r"^(\d{4})-W(\d{2})$")

# Windows 콘솔(cp949)에서도 한글과 ✓/✗ 가 깨지지 않게 한다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


# ── 주차 ──────────────────────────────────────────────────────
# 호 번호는 대상 주의 ISO 주차다. 2026-W43 은 10월 19일(월)~25일(일)을 다루고
# 다음 월요일(10월 26일)에 발행한다.


def week_bounds(issue: str) -> tuple[date, date]:
    """'2026-W43' → (월요일, 일요일)."""
    m = ISSUE_RE.match(issue)
    if not m:
        raise ValueError(f"호 번호 형식이 아닙니다(YYYY-Www): {issue}")
    year, week = int(m.group(1)), int(m.group(2))
    start = date.fromisocalendar(year, week, 1)
    return start, start + timedelta(days=6)


def publish_date(issue: str) -> date:
    """대상 주 다음 월요일."""
    return week_bounds(issue)[1] + timedelta(days=1)


def issue_of(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def parse_partial_date(s: str) -> tuple[int, ...]:
    """'2026-10-21' / '2026-10' / '2026' → (2026, 10, 21) 등. 형식이 틀리면 ValueError."""
    m = re.fullmatch(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", s)
    if not m:
        raise ValueError(f"날짜 형식이 아닙니다: {s}")
    parts = tuple(int(p) for p in m.groups() if p is not None)
    if len(parts) == 3:
        try:
            date(*parts)
        except ValueError:
            raise ValueError(f"존재하지 않는 날짜입니다: {s}") from None
    return parts


# ── 화이트리스트 ───────────────────────────────────────────────


@lru_cache(maxsize=None)
def load_whitelist(path: Path = WHITELIST) -> tuple[list[dict], set[str]]:
    """(항목 목록, 차단 도메인). 항목: {tier, group, name, domains, paths}."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = []
    for tier, groups in data["tiers"].items():
        for group, items in groups.items():
            for e in items:
                entries.append(
                    {
                        "tier": int(tier),
                        "group": group,
                        "name": e["name"],
                        "domains": [d.lower() for d in e["domains"]],
                        "paths": e.get("paths", []),
                    }
                )
    blocked = {b["domain"].lower() if isinstance(b, dict) else str(b).lower() for b in data.get("blocked") or []}
    return entries, blocked


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def lookup_tier(url: str, path: Path = WHITELIST) -> tuple[int, str | None, bool]:
    """URL 의 (등급, 기관 이름, 차단 여부). 목록 밖이면 (0, None, False).

    같은 도메인에 paths 를 가진 항목이 여럿이면 경로가 맞는 항목만 고른다.
    paths 를 가진 항목만 있는 도메인에서 경로가 하나도 맞지 않으면 목록 밖으로 본다.
    """
    entries, blocked = load_whitelist(path)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    url_path = parsed.path or "/"
    if any(_host_matches(host, b) for b in blocked):
        return 0, None, True

    candidates = [e for e in entries if any(_host_matches(host, d) for d in e["domains"])]
    with_path = [e for e in candidates if e["paths"] and any(url_path.startswith(p) for p in e["paths"])]
    if with_path:
        best = min(with_path, key=lambda e: e["tier"])
        return best["tier"], best["name"], False
    without_path = [e for e in candidates if not e["paths"]]
    if without_path:
        # 더 구체적인(긴) 도메인을 우선한다. 예: egusphere.copernicus.org(2) > copernicus.org(1)
        best = max(without_path, key=lambda e: max(len(d) for d in e["domains"] if _host_matches(host, d)))
        return best["tier"], best["name"], False
    return 0, None, False


# ── 파일 ──────────────────────────────────────────────────────


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
