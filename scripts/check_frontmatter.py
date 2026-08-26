"""노트 프론트매터가 스키마를 지키는지 검사한다.

위반이 하나라도 있으면 exit code 1로 끝나므로 렌더링 전 훅이나 CI에서 쓸 수 있다.
"""

from __future__ import annotations

import sys

from build_claims import load_notes

ALWAYS_REQUIRED = ("title", "description", "date", "categories", "status")

# published/watching 노트는 검증 가능한 주장과 반증 조건을 반드시 갖는다.
CLAIM_REQUIRED = ("claim", "confidence", "falsified_if")
CLAIM_STATUSES = ("published", "watching")

VALID_STATUSES = (
    "seed",
    "probing",
    "draft",
    "published",
    "watching",
    "retired",
)
VALID_CONFIDENCE = ("low", "medium", "high")

REQUIRES_KEYS = ("probes", "marts")
WATCH_KEYS = ("schedule", "metric", "expect_range")


def check_note(meta: dict) -> list[str]:
    problems = []

    for field in ALWAYS_REQUIRED:
        value = meta.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            problems.append(f"필수 필드 누락: {field}")

    if "categories" in meta and not isinstance(meta["categories"], list):
        problems.append("categories는 배열이어야 합니다")

    status = meta.get("status")
    if status is not None and status not in VALID_STATUSES:
        problems.append(
            f"status 값이 올바르지 않습니다: {status!r} "
            f"(허용: {', '.join(VALID_STATUSES)})"
        )

    if status in CLAIM_STATUSES:
        for field in CLAIM_REQUIRED:
            value = meta.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                problems.append(f"status가 {status}인 노트에는 {field}가 필요합니다")

        confidence = meta.get("confidence")
        if confidence is not None and confidence not in VALID_CONFIDENCE:
            problems.append(
                f"confidence 값이 올바르지 않습니다: {confidence!r} "
                f"(허용: {', '.join(VALID_CONFIDENCE)})"
            )

    requires = meta.get("requires")
    if requires is not None:
        if not isinstance(requires, dict):
            problems.append("requires는 probes/marts를 담은 맵이어야 합니다")
        else:
            for key, value in requires.items():
                if key not in REQUIRES_KEYS:
                    problems.append(f"requires에 알 수 없는 키: {key}")
                elif not isinstance(value, list):
                    problems.append(f"requires.{key}는 배열이어야 합니다")

    watch = meta.get("watch")
    if watch is not None:
        if not isinstance(watch, dict):
            problems.append("watch는 schedule/metric/expect_range를 담은 맵이어야 합니다")
        else:
            for key in WATCH_KEYS:
                if key not in watch:
                    problems.append(f"watch.{key}가 없습니다")
            for key in watch:
                if key not in WATCH_KEYS:
                    problems.append(f"watch에 알 수 없는 키: {key}")
            expect_range = watch.get("expect_range")
            if expect_range is not None and (
                not isinstance(expect_range, list) or len(expect_range) != 2
            ):
                problems.append("watch.expect_range는 [최소, 최대] 두 값이어야 합니다")

    return problems


def main() -> int:
    notes = load_notes()
    if not notes:
        print("검사할 노트가 없습니다. (notes/ 아래에 노트가 아직 없습니다)")
        return 0

    total_problems = 0
    for note in notes:
        problems = check_note(note["meta"])
        if problems:
            total_problems += len(problems)
            print(f"notes/{note['slug']}/index.qmd")
            for problem in problems:
                print(f"  - {problem}")

    checked = f"노트 {len(notes)}개 검사"
    if total_problems:
        print(f"\n{checked}, 위반 {total_problems}건.")
        return 1

    print(f"{checked}, 위반 없음.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
