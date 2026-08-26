"""감시 지표 함수 등록소.

`status: watching` 인 노트는 프론트매터의 `watch.metric` 에 지표 이름을 적는다.
그 이름으로 여기서 함수를 찾아 실행하고, 결과가 `watch.expect_range` 를 벗어나면
해당 노트를 다시 검토한다.

지표 함수는 인자 없이 float 하나를 돌려주며, `data/marts/` 의 집계 파일만 읽는다.
원자료를 직접 받지 않는 이유는 감시가 수집 성공 여부에 묶이면
"주장이 흔들렸는지" 와 "수집이 실패했는지" 를 구분할 수 없게 되기 때문이다.
"""

from __future__ import annotations

from typing import Callable

# 지표 이름 → 무인자 호출 가능 객체. 수집 계층이 생기기 전까지는 비어 있다.
METRICS: dict[str, Callable[[], float]] = {}


def register(name: str) -> Callable[[Callable[[], float]], Callable[[], float]]:
    """지표 함수를 이름으로 등록하는 데코레이터."""

    def decorator(func: Callable[[], float]) -> Callable[[], float]:
        if name in METRICS:
            raise ValueError(f"이미 등록된 지표 이름입니다: {name}")
        METRICS[name] = func
        return func

    return decorator


def get(name: str) -> Callable[[], float]:
    """등록된 지표를 이름으로 가져온다. 없으면 KeyError."""
    if name not in METRICS:
        known = ", ".join(sorted(METRICS)) or "(등록된 지표 없음)"
        raise KeyError(f"알 수 없는 지표: {name}. 등록된 지표: {known}")
    return METRICS[name]


def in_range(value: float, expect_range: list[float]) -> bool:
    """관측값이 노트가 기대한 범위 안에 있는지. 경계값은 범위 안으로 본다."""
    low, high = expect_range
    return low <= value <= high
