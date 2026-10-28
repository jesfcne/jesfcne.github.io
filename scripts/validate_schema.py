"""파이프라인 산출물이 형식을 지키는지 검사한다.

    python scripts/validate_schema.py pipeline/2026-W43/sources.json [다른 파일 ...]

파일 이름으로 종류를 정한다.
    sources.json, background.json,
    verified.json, background-verified.json  → scripts/schema/source-list.schema.json
    review.json                              → scripts/schema/review.schema.json

JSON 스키마로 표현하기 어려운 규칙(id 중복, 호 번호와 폴더 일치)은 여기서 따로 본다.
위반이 하나라도 있으면 exit code 1 로 끝나므로, 단계 사이에 넣어 다음 단계로
넘어가지 않게 할 수 있다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SCHEMA_DIR, ISSUE_RE, parse_partial_date, read_json  # noqa: E402

KINDS = {
    "sources.json": ("source-list", "sources"),
    "background.json": ("source-list", "background"),
    "verified.json": ("source-list", "verified"),
    "background-verified.json": ("source-list", "verified"),
    "review.json": ("review", None),
}


def _registry() -> Registry:
    resources = []
    for p in SCHEMA_DIR.glob("*.schema.json"):
        schema = read_json(p)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def _path_str(error) -> str:
    parts = [str(p) for p in error.absolute_path]
    return "/".join(parts) if parts else "(최상위)"


def validate_file(path: Path) -> list[str]:
    """위반 사항 목록을 돌려준다. 비어 있으면 통과."""
    path = Path(path)
    if path.name not in KINDS:
        return [f"알 수 없는 파일 종류입니다: {path.name} (가능: {', '.join(KINDS)})"]
    schema_id, expected_stage = KINDS[path.name]

    try:
        data = read_json(path)
    except Exception as e:  # noqa: BLE001
        return [f"JSON 을 읽을 수 없습니다: {e}"]

    registry = _registry()
    schema = registry.contents(schema_id)
    validator = Draft202012Validator(schema, registry=registry)
    errors = [f"{_path_str(e)}: {e.message}" for e in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))]
    if errors or not isinstance(data, dict):
        return errors

    if expected_stage and data.get("stage") != expected_stage:
        errors.append(f"stage 가 '{expected_stage}' 여야 합니다: {data.get('stage')}")

    # pipeline/<호>/파일 이면 폴더명과 issue 가 같아야 한다.
    folder = path.parent.name
    if ISSUE_RE.match(folder) and data.get("issue") != folder:
        errors.append(f"issue({data.get('issue')})가 폴더명({folder})과 다릅니다")

    if schema_id == "source-list":
        seen = set()
        for i, item in enumerate(data["items"]):
            if item["id"] in seen:
                errors.append(f"items/{i}: id 가 중복됩니다: {item['id']}")
            seen.add(item["id"])
            try:
                parse_partial_date(item["published_at"])
            except ValueError as e:
                errors.append(f"items/{i}: {e}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args(argv)

    failed = 0
    for f in args.files:
        errors = validate_file(f)
        if errors:
            failed += 1
            print(f"✗ {f}")
            for e in errors:
                print(f"    {e}")
        else:
            print(f"✓ {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
