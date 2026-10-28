"""장기 연속자료 수집 (파이프라인 ④ 자료 보강 단계).

    python scripts/fetch_series.py                      # 등록된 모든 자료
    python scripts/fetch_series.py co2-mlo-annual       # 일부만
    python scripts/fetch_series.py --force ...          # 이번 주에 받았어도 다시 받기
    python scripts/fetch_series.py co2-mlo-annual --add-to pipeline/2026-W43/background.json --id s-01

editorial/series-registry.yml 에 등록된 자료를 내려받아 정리한다.

    data/series/<id>/data.csv   정리된 표 (열은 레지스트리의 columns)
    data/series/<id>/meta.json  수집 기록: 원천 주소, 수집일, 원파일 해시, 기간, 행 수
    data/series/<id>/raw.*      원파일 (커밋하지 않음)

같은 주(ISO)에 이미 받은 자료는 다시 받지 않는다. 원파일에 레지스트리의 quote 가
없으면 원천 형식이 바뀌었을 수 있으므로 실패로 처리한다.

--add-to 를 주면 그 자료를 출처 항목(role: series)으로 background.json 에 더한다.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import io
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Callable

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, issue_of, read_json, write_json  # noqa: E402
from verify_sources import normalize  # noqa: E402

REGISTRY = ROOT / "editorial" / "series-registry.yml"
DATA_DIR = ROOT / "data" / "series"
USER_AGENT = "climate-brief-series-fetcher (+https://jesfcne.github.io)"

Row = dict[str, object]


# ── 원천별 정리 함수 ───────────────────────────────────────────
# 모두 원파일 텍스트를 받아 행 목록을 돌려준다. 결측값은 넣지 않는다.


def _data_lines(text: str, comment: str = "#") -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith(comment)]


def noaa_co2_annual(text: str) -> list[Row]:
    rows = []
    for r in csv.DictReader(io.StringIO("\n".join(_data_lines(text)))):
        rows.append({"year": int(r["year"]), "value": float(r["mean"]), "unc": float(r["unc"])})
    return rows


def noaa_flask_monthly(text: str) -> list[Row]:
    rows = []
    for ln in _data_lines(text):
        site, year, month, value = ln.split()[:4]
        v = float(value)
        if v > 0:  # GML 은 결측을 음수(-999.99)로 적는다
            rows.append({"year": int(year), "month": int(month), "value": v})
    return rows


def gistemp_annual(text: str) -> list[Row]:
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("Year,"))
    rows = []
    for r in csv.DictReader(io.StringIO("\n".join(lines[start:]))):
        v = r["J-D"].strip()
        if v and "*" not in v:  # 한 해가 다 차지 않으면 *** 로 적혀 있다
            rows.append({"year": int(r["Year"]), "anomaly": float(v)})
    return rows


def _era5_days(text: str):
    for r in csv.DictReader(io.StringIO("\n".join(_data_lines(text)))):
        d = date.fromisoformat(r["date"])
        yield d, float(r["2t"]), float(r["ano_91-20"]), r["status"].strip().upper() != "FINAL"


def era5_monthly(text: str) -> list[Row]:
    buckets: dict[tuple[int, int], list] = defaultdict(list)
    for d, t, a, prelim in _era5_days(text):
        buckets[(d.year, d.month)].append((t, a, prelim))
    rows = []
    for (y, m), vals in sorted(buckets.items()):
        if len(vals) < calendar.monthrange(y, m)[1]:
            continue  # 다 차지 않은 달
        rows.append({
            "year": y, "month": m,
            "value": round(sum(v[0] for v in vals) / len(vals), 3),
            "anomaly": round(sum(v[1] for v in vals) / len(vals), 3),
            "preliminary": any(v[2] for v in vals),
        })
    return rows


def era5_annual(text: str) -> list[Row]:
    buckets: dict[int, list] = defaultdict(list)
    for d, t, a, _ in _era5_days(text):
        buckets[d.year].append((t, a))
    rows = []
    for y, vals in sorted(buckets.items()):
        if len(vals) < (366 if calendar.isleap(y) else 365):
            continue  # 다 차지 않은 해
        rows.append({"year": y,
                     "value": round(sum(v[0] for v in vals) / len(vals), 3),
                     "anomaly": round(sum(v[1] for v in vals) / len(vals), 3)})
    return rows


def nsidc_monthly(text: str) -> list[Row]:
    rows = []
    reader = csv.reader(io.StringIO(text))
    next(reader)  # 머리글
    for r in reader:
        if not r or not r[0].strip():
            continue
        year, extent, area = int(r[0]), float(r[4]), float(r[5])
        if extent > 0:  # 결측은 -9999
            rows.append({"year": year, "value": extent, "area": area})
    return rows


PARSERS: dict[str, Callable[[str], list[Row]]] = {
    f.__name__: f for f in (noaa_co2_annual, noaa_flask_monthly, gistemp_annual, era5_monthly, era5_annual, nsidc_monthly)
}


# ── 수집 ──────────────────────────────────────────────────────


def load_registry(path: Path = REGISTRY) -> dict[str, dict]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("series") or {}


def http_get(url: str) -> bytes:
    import requests

    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    return r.content


def _period(rows: list[Row]) -> tuple[str, str]:
    def key(r):
        return f"{r['year']}-{r['month']:02d}" if "month" in r else str(r["year"])
    return key(rows[0]), key(rows[-1])


def process(sid: str, spec: dict, raw: bytes, today: date) -> tuple[list[Row], dict]:
    """원파일 → (행, meta). 문제가 있으면 ValueError."""
    text = raw.decode("utf-8", errors="replace")
    if normalize(spec["quote"]) not in normalize(text):
        raise ValueError(f"원파일에 레지스트리의 quote 가 없습니다. 원천 형식이 바뀌었는지 확인하세요: {spec['quote']}")
    rows = PARSERS[spec["parser"]](text)
    if not rows:
        raise ValueError("정리된 행이 없습니다")
    keys = [(r["year"], r.get("month", 0)) for r in rows]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise ValueError("행이 시간 순서가 아니거나 중복됩니다")
    first, last = _period(rows)
    meta = {
        "id": sid,
        "title": spec["title"],
        "publisher": spec["publisher"],
        "landing_url": spec["landing_url"],
        "download_url": spec["download_url"],
        "retrieved_at": today.isoformat(),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw),
        "rows": len(rows),
        "first": first,
        "last": last,
        "unit": spec["unit"],
        "baseline": spec.get("baseline"),
        "columns": spec["columns"],
    }
    return rows, meta


def write_series(sid: str, rows: list[Row], meta: dict, raw: bytes, data_dir: Path = DATA_DIR) -> Path:
    d = data_dir / sid
    d.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0].keys())
    with (d / "data.csv").open("w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (str(v).lower() if isinstance(v, bool) else v) for k, v in r.items()})
    write_json(d / "meta.json", meta)
    suffix = Path(meta["download_url"]).suffix or ".txt"
    (d / f"raw{suffix}").write_bytes(raw)
    return d


def fresh(sid: str, today: date, data_dir: Path = DATA_DIR) -> bool:
    """이번 주에 이미 받았는가."""
    p = data_dir / sid / "meta.json"
    if not p.exists():
        return False
    return issue_of(date.fromisoformat(read_json(p)["retrieved_at"])) == issue_of(today)


def fetch(ids: list[str], registry: dict, force: bool = False, get: Callable[[str], bytes] = http_get,
          today: date | None = None, data_dir: Path = DATA_DIR) -> list[tuple[str, str]]:
    """(id, 결과 메시지) 목록. 실패가 있으면 메시지가 '실패:' 로 시작한다."""
    today = today or date.today()
    cache: dict[str, bytes] = {}   # 같은 원파일을 쓰는 자료(ERA5 월·연)는 한 번만 받는다
    results = []
    for sid in ids:
        spec = registry.get(sid)
        if spec is None:
            results.append((sid, "실패: 레지스트리에 없는 자료입니다"))
            continue
        if not force and fresh(sid, today, data_dir):
            results.append((sid, "이번 주에 이미 받았습니다 (건너뜀)"))
            continue
        try:
            url = spec["download_url"]
            if url not in cache:
                cache[url] = get(url)
            rows, meta = process(sid, spec, cache[url], today)
            write_series(sid, rows, meta, cache[url], data_dir)
            results.append((sid, f"{meta['rows']}행, {meta['first']}~{meta['last']}"))
        except Exception as e:  # noqa: BLE001 - 한 자료의 실패가 나머지를 막지 않게 한다
            results.append((sid, f"실패: {e}"))
    return results


# ── 출처 항목 ──────────────────────────────────────────────────


def as_source(sid: str, spec: dict, source_id: str, data_dir: Path = DATA_DIR) -> dict:
    """background.json 에 넣을 출처 항목(role: series)."""
    meta = read_json(data_dir / sid / "meta.json")
    tier_publisher = spec["publisher"]
    from common import lookup_tier

    return {
        "id": source_id,
        "region": spec["region"],
        "kind": "dataset",
        "role": "series",
        "topic": spec["title"][:40],
        "title": spec["title"],
        "publisher": tier_publisher,
        "url": spec["download_url"],
        "published_at": meta["retrieved_at"],
        "version": f"{meta['last']}까지, sha256 {meta['raw_sha256'][:12]}",
        "tier": lookup_tier(spec["download_url"])[0],
        "quote": spec["quote"],
        "claims": [f"{spec['title']}: {meta['first']}~{meta['last']}, 단위 {spec['unit']}"
                   + (f", 기준 기간 {spec['baseline']}" if spec.get("baseline") else "")],
    }


def add_to_background(path: Path, item: dict) -> None:
    path = Path(path)
    issue = path.parent.name
    data = read_json(path) if path.exists() else {"issue": issue, "stage": "background", "items": []}
    data["items"] = [i for i in data["items"] if i["id"] != item["id"]] + [item]
    write_json(path, data)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="자료 id (생략하면 전부)")
    ap.add_argument("--force", action="store_true", help="이번 주에 받았어도 다시 받는다")
    ap.add_argument("--add-to", type=Path, help="출처 항목을 더할 background.json")
    ap.add_argument("--id", dest="source_id", help="--add-to 에 쓸 출처 id (예: s-01)")
    args = ap.parse_args(argv)

    registry = load_registry()
    ids = args.ids or list(registry)
    results = fetch(ids, registry, force=args.force)
    failed = False
    for sid, msg in results:
        print(f"{'✗' if msg.startswith('실패') else '✓'} {sid}: {msg}")
        failed |= msg.startswith("실패")

    if args.add_to:
        if len(ids) != 1 or not args.source_id:
            print("--add-to 는 자료 하나와 --id 를 함께 줘야 합니다")
            return 1
        item = as_source(ids[0], registry[ids[0]], args.source_id)
        add_to_background(args.add_to, item)
        print(f"{args.add_to}: {args.source_id} 추가")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
