"""출처 검증 (파이프라인 ② 단계).

    python scripts/verify_sources.py pipeline/2026-W43/sources.json
    python scripts/verify_sources.py pipeline/2026-W43/background.json

sources.json → verified.json, background.json → background-verified.json 을 같은
폴더에 쓴다. 항목마다 다음을 확인하고 결과를 verification 에 남긴다.

    1. URL 이 응답하는가 (리디렉트 추적)
    2. 논문은 DOI 가 실제로 있고(Crossref), 제목·첫 저자·게재일이 기재 내용과 맞는가
    3. quote 가 원문(논문은 초록 포함)에 실제로 있는가
    4. trigger 자료의 발행일이 대상 주 안에 있는가
    5. tier 가 화이트리스트와 맞는가

판정
    verified     모든 확인을 통과. 다음 단계에서 쓸 수 있다.
    needs_agent  스크립트가 판정하지 못함(페이월, 차단, 동적 페이지, 인용문 근사 일치,
                 PDF 추출 실패, tier 불일치). verifier 에이전트가 직접 열어 확인한다.
    둘 다 false   확실한 실패(404, 존재하지 않는 DOI, 서지 불일치, 기간 밖). 쓰지 않는다.

이 스크립트는 기록을 고치지 않는다. 판정만 붙인다.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable
from urllib.parse import quote as urlquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import lookup_tier, parse_partial_date, read_json, week_bounds, write_json  # noqa: E402

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36 climate-brief-verifier"
)
TIMEOUT = 25
MIN_TEXT = 400          # 본문이 이보다 짧으면 동적 페이지나 차단으로 본다
APPROX_RATIO = 0.85     # 인용문의 이 비율 이상이 연속으로 일치하면 근사 일치
TITLE_RATIO = 0.85      # DOI 서지와 제목 유사도 기준
DATE_SLACK_DAYS = 3     # 온라인 게재일과 기재 발행일의 허용 차이


@dataclass
class Page:
    status: int | None          # None 이면 연결 실패
    final_url: str | None
    text: str                   # 본문 텍스트 (HTML/PDF 에서 추출)
    error: str | None = None


Fetcher = Callable[[str], Page]
CrossrefLookup = Callable[[str], "dict | None"]


# ── 원문 가져오기 ───────────────────────────────────────────────


def _html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    # 논문 사이트는 초록을 meta 태그에만 두는 경우가 있다.
    metas = [m.get("content", "") for m in soup.find_all("meta") if (m.get("name") or m.get("property") or "").lower()
             in {"description", "og:description", "dc.description", "citation_abstract"}]
    return " ".join(metas) + " " + soup.get_text(" ")


def _pdf_to_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return " ".join((p.extract_text() or "") for p in reader.pages[:60])


def http_fetch(url: str) -> Page:
    import requests

    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ko,en;q=0.8"},
                         timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException as e:
        return Page(None, None, "", error=type(e).__name__)
    ctype = r.headers.get("Content-Type", "").lower()
    try:
        if "pdf" in ctype or r.content[:5] == b"%PDF-":
            text = _pdf_to_text(r.content)
        else:
            text = _html_to_text(r.text)
    except Exception as e:  # noqa: BLE001 - 추출 실패는 판정 불가로 넘긴다
        return Page(r.status_code, r.url, "", error=f"본문 추출 실패: {type(e).__name__}")
    return Page(r.status_code, r.url, text)


def crossref_lookup(doi: str) -> dict | None:
    """Crossref 서지. DOI 가 없으면 None. 네트워크 오류는 예외로 올린다."""
    import requests

    r = requests.get(f"https://api.crossref.org/works/{urlquote(doi, safe='/')}",
                     headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()["message"]


# ── 비교 ──────────────────────────────────────────────────────

_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "`": "'",
                         "–": "-", "—": "-", "‐": "-", "‑": "-", "−": "-", "­": None})


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_QUOTES).lower()
    s = re.sub(r"<[^>]+>", " ", s)          # Crossref 초록의 JATS 태그
    return re.sub(r"\s+", " ", s).strip()


def match_quote(quote: str, text: str) -> str:
    """'exact' | 'approx' | 'missing'."""
    q, t = normalize(quote), normalize(text)
    if not q or not t:
        return "missing"
    if q in t:
        return "exact"
    # 가장 길게 일치하는 조각을 기준으로 원문에서 인용문 길이만큼을 잘라 비교한다.
    # 단어 한두 개가 다른 정도면 근사 일치로 보고 에이전트가 확인하게 한다.
    block = SequenceMatcher(None, q, t, autojunk=False).find_longest_match(0, len(q), 0, len(t))
    if block.size < max(12, len(q) // 5):
        return "missing"
    start = max(0, block.b - block.a)
    window = t[start:start + len(q) + 20]
    if SequenceMatcher(None, q, window, autojunk=False).ratio() >= APPROX_RATIO:
        return "approx"
    return "missing"


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def _crossref_date(msg: dict) -> tuple[int, ...] | None:
    for key in ("published-online", "published-print", "published", "issued"):
        parts = (msg.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return tuple(parts[0])
    return None


def check_doi(item: dict, msg: dict | None) -> tuple[bool, list[str], str]:
    """(통과 여부, 메모, Crossref 초록 텍스트)."""
    if msg is None:
        return False, [f"DOI 가 Crossref 에 없습니다: {item['doi']}"], ""
    notes = []
    ok = True
    titles = msg.get("title") or []
    if not titles or max(similar(item["title"], t) for t in titles) < TITLE_RATIO:
        ok = False
        notes.append(f"제목이 DOI 서지와 다릅니다: {titles[:1]}")
    authors = msg.get("author") or []
    if item.get("authors") and authors:
        first = normalize(item["authors"][0].split(",")[0])
        cr_first = normalize(authors[0].get("family") or authors[0].get("name") or "")
        if first and cr_first and first not in cr_first and cr_first not in first:
            ok = False
            notes.append(f"첫 저자가 DOI 서지와 다릅니다: {authors[0].get('family')}")
    cr_date = _crossref_date(msg)
    if cr_date and len(cr_date) == 3:
        try:
            mine = parse_partial_date(item["published_at"])
            if len(mine) == 3 and abs((date(*mine) - date(*cr_date)).days) > DATE_SLACK_DAYS:
                notes.append(f"게재일이 DOI 서지({'-'.join(map(str, cr_date))})와 다릅니다")
                ok = False
        except ValueError:
            pass
    containers = msg.get("container-title") or []
    if containers and not any(normalize(c) in normalize(item["publisher"]) or normalize(item["publisher"]) in normalize(c)
                              for c in containers):
        notes.append(f"참고: 학술지 이름이 서지({containers[0]})와 다르게 적혀 있습니다")
    return ok, notes, msg.get("abstract") or ""


# ── 항목 검증 ──────────────────────────────────────────────────


def verify_item(item: dict, issue: str, fetch: Fetcher, crossref: CrossrefLookup,
                today: date | None = None) -> dict:
    today = today or date.today()
    notes: list[str] = []
    hard_fail = False      # 확실한 실패
    unsure = False         # 사람이(에이전트가) 봐야 함

    # 1. URL
    page = fetch(item["url"])
    url_ok: bool | None
    if page.status is None:
        url_ok, unsure = None, True
        notes.append(f"연결 실패: {page.error}")
    elif page.status in (404, 410):
        url_ok, hard_fail = False, True
        notes.append(f"페이지가 없습니다 (HTTP {page.status})")
    elif page.status in (401, 402, 403, 429, 451) or page.status >= 500:
        url_ok, unsure = None, True
        notes.append(f"접근이 막혔습니다 (HTTP {page.status}). 페이월·차단일 수 있습니다")
    elif page.status >= 400:
        url_ok, hard_fail = False, True
        notes.append(f"HTTP {page.status}")
    else:
        url_ok = True
        if page.error:
            unsure = True
            notes.append(page.error)
        elif len(page.text) < MIN_TEXT:
            unsure = True
            notes.append("본문이 거의 없습니다. 동적 페이지이거나 차단되었을 수 있습니다")

    # 2. DOI
    doi_ok: bool | None = None
    abstract = ""
    if item.get("doi"):
        try:
            doi_ok, doi_notes, abstract = check_doi(item, crossref(item["doi"]))
            notes += doi_notes
            if not doi_ok:
                hard_fail = True
        except Exception as e:  # noqa: BLE001
            unsure = True
            notes.append(f"Crossref 조회 실패: {type(e).__name__}")
    elif item["kind"] == "paper":
        hard_fail = True
        notes.append("논문인데 DOI 가 없습니다")

    # 3. 인용문
    haystack = " ".join([page.text, abstract])
    quote_match = match_quote(item["quote"], haystack) if haystack.strip() else "unchecked"
    if quote_match == "unchecked":
        unsure = True
    elif quote_match == "approx":
        unsure = True
        notes.append("인용문이 원문과 조금 다릅니다. 원문 그대로 옮겼는지 확인이 필요합니다")
    elif quote_match == "missing":
        if url_ok and len(page.text) >= MIN_TEXT and not unsure:
            hard_fail = True
            notes.append("인용문이 원문에 없습니다")
        else:
            unsure = True
            notes.append("원문을 충분히 읽지 못해 인용문을 확인하지 못했습니다")

    # 4. 기간
    date_in_window: bool | None = None
    if item["role"] == "trigger":
        start, end = week_bounds(issue)
        try:
            parts = parse_partial_date(item["published_at"])
            date_in_window = len(parts) == 3 and start <= date(*parts) <= end
        except ValueError:
            date_in_window = False
        if not date_in_window:
            hard_fail = True
            notes.append(f"발행일 {item['published_at']} 이 대상 주({start}~{end}) 밖입니다")

    # 5. 등급
    tier_expected, org, blocked = lookup_tier(page.final_url or item["url"])
    if blocked:
        hard_fail = True
        notes.append("차단 목록에 있는 출처입니다")
    tier_ok = item["tier"] == tier_expected
    if not tier_ok:
        unsure = True
        notes.append(f"tier 가 {item['tier']} 로 적혀 있지만 화이트리스트로는 {tier_expected} 입니다"
                     + (f" ({org})" if org else " (목록 밖)"))
    if item["kind"] == "preprint" and urlparse(item["url"]).hostname and tier_expected == 1:
        notes.append("참고: 프리프린트인데 tier 1 도메인입니다. 동료심사 여부를 확인하세요")

    verified = not hard_fail and not unsure and url_ok is True and quote_match == "exact"
    return {
        "checked_at": today.isoformat(),
        "checked_by": "script",
        "http_status": page.status,
        "final_url": page.final_url,
        "url_ok": url_ok,
        "doi_ok": doi_ok,
        "quote_match": quote_match,
        "date_in_window": date_in_window,
        "tier_expected": tier_expected,
        "tier_ok": tier_ok,
        "verified": verified,
        "needs_agent": (not verified) and (not hard_fail),
        "notes": notes,
    }


def output_path(src: Path) -> Path:
    name = {"sources.json": "verified.json", "background.json": "background-verified.json"}.get(src.name)
    if not name:
        raise SystemExit(f"sources.json 이나 background.json 만 검증합니다: {src.name}")
    return src.with_name(name)


def run(src: Path, fetch: Fetcher = http_fetch, crossref: CrossrefLookup = crossref_lookup,
        delay: float = 1.0, today: date | None = None) -> dict:
    data = read_json(src)
    out_items = []
    last_host_at: dict[str, float] = {}
    for item in data["items"]:
        host = urlparse(item["url"]).hostname or ""
        wait = delay - (time.monotonic() - last_host_at.get(host, -1e9))
        if wait > 0:
            time.sleep(wait)   # 같은 사이트에 연달아 요청하지 않는다
        v = verify_item(item, data["issue"], fetch, crossref, today=today)
        last_host_at[host] = time.monotonic()
        out_items.append({**{k: val for k, val in item.items() if k != "verification"}, "verification": v})
    return {"issue": data["issue"], "stage": "verified", "items": out_items}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="sources.json 또는 background.json")
    args = ap.parse_args(argv)

    result = run(args.source)
    out = output_path(args.source)
    write_json(out, result)

    items = result["items"]
    ok = [i for i in items if i["verification"]["verified"]]
    agent = [i for i in items if i["verification"]["needs_agent"]]
    fail = [i for i in items if not i["verification"]["verified"] and not i["verification"]["needs_agent"]]
    print(f"{out}: 통과 {len(ok)} · 에이전트 확인 필요 {len(agent)} · 실패 {len(fail)} (전체 {len(items)})")
    for label, group in (("에이전트 확인 필요", agent), ("실패", fail)):
        for i in group:
            print(f"  [{label}] {i['id']} {i['title'][:40]}")
            for n in i["verification"]["notes"]:
                print(f"      - {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
