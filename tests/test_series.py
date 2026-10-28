"""장기 연속자료 수집 시험. 원천별 정리 함수는 원파일 형식을 본뜬 조각으로 시험한다."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_series as fs  # noqa: E402
import validate_schema  # noqa: E402
from common import lookup_tier  # noqa: E402

REGISTRY = fs.load_registry()
TODAY = date(2026, 10, 28)

MLO = """# CO2 expressed as a mole fraction in dry air, micromol/mol, abbreviated as ppm
year,mean,unc
2023,421.08,0.12
2024,424.61,0.12
"""
AMY = """# description_site-code: amy
# data_fields: site year month value
AMY 2025 10   430.12
AMY 2025 11   -999.99
AMY 2025 12   437.02
"""
GISTEMP = """Land-Ocean: Global Means
Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec,J-D,D-N,DJF,MAM,JJA,SON
2024,1.24,1.44,1.39,1.31,1.18,1.23,1.20,1.30,1.22,1.33,1.30,1.27,1.28,1.29,1.35,1.29,1.24,1.28
2025,1.37,1.25,1.36,1.24,1.07,1.06,1.02,1.17,1.24,***,***,***,***,***,1.29,1.22,1.08,***
"""
NSIDC = """year, mo,source_dataset, region, extent,   area
2012,  9,    NSIDC-0051,      N,   3.57,   2.41
2013,  9,    NSIDC-0051,      N, -9999, -9999
2024,  9,    NSIDC-0803,      N,   4.35,   2.91
"""


def era5(days: list[tuple[str, float, float, str]]) -> str:
    head = "# This file contains daily global mean near-surface (2m) air temperature\ndate,2t,clim_91-20,ano_91-20,status\n"
    return head + "".join(f"{d},{t},0,{a},{s}\n" for d, t, a, s in days)


def test_registry_is_complete():
    required = {"title", "publisher", "landing_url", "download_url", "parser", "frequency", "columns", "unit", "region", "update", "quote"}
    for sid, spec in REGISTRY.items():
        assert required <= spec.keys(), (sid, required - spec.keys())
        assert spec["parser"] in fs.PARSERS, sid
        assert spec["region"] in ("global", "korea"), sid
        assert lookup_tier(spec["download_url"])[0] >= 1, f"{sid}: 원천이 화이트리스트 1·2등급이어야 한다"


def test_noaa_co2_annual():
    assert fs.noaa_co2_annual(MLO) == [{"year": 2023, "value": 421.08, "unc": 0.12}, {"year": 2024, "value": 424.61, "unc": 0.12}]


def test_noaa_flask_monthly_drops_missing():
    rows = fs.noaa_flask_monthly(AMY)
    assert [(r["year"], r["month"]) for r in rows] == [(2025, 10), (2025, 12)]


def test_gistemp_skips_incomplete_year():
    assert fs.gistemp_annual(GISTEMP) == [{"year": 2024, "anomaly": 1.28}]


def test_nsidc_drops_missing():
    assert fs.nsidc_monthly(NSIDC) == [{"year": 2012, "value": 3.57, "area": 2.41}, {"year": 2024, "value": 4.35, "area": 2.91}]


def test_era5_monthly_complete_months_only():
    days = [(f"2026-02-{d:02d}", 14.0, 0.5, "FINAL") for d in range(1, 29)]          # 2월 28일 전부
    days += [(f"2026-03-{d:02d}", 15.0, 0.7, "FINAL") for d in range(1, 31)]          # 3월은 30일만
    rows = fs.era5_monthly(era5(days))
    assert rows == [{"year": 2026, "month": 2, "value": 14.0, "anomaly": 0.5, "preliminary": False}]


def test_era5_monthly_marks_preliminary():
    days = [(f"2026-02-{d:02d}", 14.0, 0.5, "FINAL" if d < 28 else "PRELIMINARY") for d in range(1, 29)]
    assert fs.era5_monthly(era5(days))[0]["preliminary"] is True


def test_era5_annual_complete_years_only():
    from datetime import timedelta
    start = date(2024, 1, 1)
    days = [((start + timedelta(i)).isoformat(), 15.0, 0.72, "FINAL") for i in range(366 + 100)]  # 2024 전체 + 2025 일부
    assert fs.era5_annual(era5(days)) == [{"year": 2024, "value": 15.0, "anomaly": 0.72}]


def test_process_rejects_changed_format():
    spec = REGISTRY["co2-mlo-annual"]
    with pytest.raises(ValueError, match="quote"):
        fs.process("co2-mlo-annual", spec, MLO.replace("micromol/mol", "umol").encode(), TODAY)


def test_process_rejects_unsorted_rows():
    spec = REGISTRY["co2-mlo-annual"]
    text = MLO.replace("2023,421.08", "2025,421.08")
    with pytest.raises(ValueError, match="순서"):
        fs.process("co2-mlo-annual", spec, text.encode(), TODAY)


def test_fetch_writes_files_and_skips_same_week(tmp_path):
    calls = []

    def get(url):
        calls.append(url)
        return MLO.encode()

    reg = {"co2-mlo-annual": REGISTRY["co2-mlo-annual"]}
    res = fs.fetch(["co2-mlo-annual"], reg, get=get, today=TODAY, data_dir=tmp_path)
    assert res == [("co2-mlo-annual", "2행, 2023~2024")]
    d = tmp_path / "co2-mlo-annual"
    assert (d / "data.csv").read_text(encoding="utf-8").splitlines() == ["year,value,unc", "2023,421.08,0.12", "2024,424.61,0.12"]
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    assert meta["retrieved_at"] == "2026-10-28" and meta["first"] == "2023" and len(meta["raw_sha256"]) == 64

    # 같은 주에는 다시 받지 않는다. 다음 주에는 받는다. --force 면 받는다.
    fs.fetch(["co2-mlo-annual"], reg, get=get, today=date(2026, 11, 1), data_dir=tmp_path)
    assert len(calls) == 1
    fs.fetch(["co2-mlo-annual"], reg, get=get, today=date(2026, 11, 2), data_dir=tmp_path)
    assert len(calls) == 2
    fs.fetch(["co2-mlo-annual"], reg, get=get, force=True, today=date(2026, 11, 2), data_dir=tmp_path)
    assert len(calls) == 3


def test_fetch_downloads_shared_file_once(tmp_path):
    calls = []
    days = [(f"2026-02-{d:02d}", 14.0, 0.5, "FINAL") for d in range(1, 29)]

    def get(url):
        calls.append(url)
        return era5(days).encode()

    res = fs.fetch(["era5-global-monthly", "era5-global-annual"], REGISTRY, get=get, today=TODAY, data_dir=tmp_path)
    assert len(calls) == 1
    assert res[0][1].startswith("1행") and res[1][1].startswith("실패")  # 다 찬 해가 없으면 연평균은 실패


def test_fetch_failure_does_not_stop_others(tmp_path):
    def get(url):
        if "co2_annmean" in url:
            raise ConnectionError("down")
        return GISTEMP.encode()

    res = dict(fs.fetch(["co2-mlo-annual", "gistemp-global-annual"], REGISTRY, get=get, today=TODAY, data_dir=tmp_path))
    assert res["co2-mlo-annual"].startswith("실패") and res["gistemp-global-annual"].startswith("1행")


def test_as_source_is_valid_background_item(tmp_path):
    reg = {"co2-mlo-annual": REGISTRY["co2-mlo-annual"]}
    fs.fetch(["co2-mlo-annual"], reg, get=lambda u: MLO.encode(), today=TODAY, data_dir=tmp_path)
    item = fs.as_source("co2-mlo-annual", reg["co2-mlo-annual"], "s-01", data_dir=tmp_path)
    folder = tmp_path / "pipeline" / "2026-W43"
    folder.mkdir(parents=True)
    bg = folder / "background.json"
    fs.add_to_background(bg, item)
    fs.add_to_background(bg, item)  # 같은 id 는 덮어쓴다
    data = json.loads(bg.read_text(encoding="utf-8"))
    assert len(data["items"]) == 1 and data["items"][0]["tier"] == 1
    assert validate_schema.validate_file(bg) == []


@pytest.mark.network
@pytest.mark.parametrize("sid", list(REGISTRY))
def test_live_series(sid, tmp_path):
    """원천 주소와 형식이 아직 맞는지 실제로 받아 본다. pytest -m network"""
    res = dict(fs.fetch([sid], REGISTRY, force=True, data_dir=tmp_path))
    assert not res[sid].startswith("실패"), res[sid]
