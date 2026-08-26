"""노트 프론트매터를 읽어 인사이트 인덱스용 표를 만든다.

프론트매터 파싱은 check_frontmatter.py에서도 필요하므로 여기에 두고 재사용한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

# 인사이트 인덱스에 올라가는 상태. draft 이하는 주장이 아직 확정되지 않았다.
INDEXED_STATUSES = ("published", "watching")

CONFIDENCE_LABELS = {"low": "낮음", "medium": "보통", "high": "높음"}

STATUS_LABELS = {
    "seed": "씨앗",
    "probing": "탐색 중",
    "draft": "초고",
    "published": "발행",
    "watching": "감시 중",
    "retired": "폐기",
}


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def split_frontmatter(text: str) -> dict:
    """qmd 앞머리의 YAML 블록을 dict로 돌려준다. 없으면 빈 dict."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    loaded = yaml.safe_load(parts[1])
    return loaded if isinstance(loaded, dict) else {}


def iter_note_files(notes_dir: Path | None = None):
    """`notes/<슬러그>/index.qmd` 를 슬러그 순으로 훑는다.

    `_` 로 시작하는 디렉터리는 Quarto가 렌더링에서 제외하므로 여기서도 건너뛴다.
    """
    notes_dir = notes_dir or (project_root() / "notes")
    if not notes_dir.is_dir():
        return
    for path in sorted(notes_dir.glob("*/index.qmd")):
        if path.parent.name.startswith("_"):
            continue
        yield path


def load_notes(notes_dir: Path | None = None) -> list[dict]:
    """노트마다 프론트매터 + 경로 정보를 담은 dict 목록을 돌려준다."""
    notes = []
    for path in iter_note_files(notes_dir):
        meta = split_frontmatter(path.read_text(encoding="utf-8"))
        notes.append(
            {
                "path": path,
                "slug": path.parent.name,
                "href": f"notes/{path.parent.name}/",
                "meta": meta,
            }
        )
    return notes


def claims_frame(notes_dir: Path | None = None) -> pd.DataFrame:
    """발행·감시 상태 노트의 주장을 최신순 DataFrame으로 돌려준다.

    노트가 하나도 없어도 열 구성이 같은 빈 DataFrame을 돌려주므로
    호출부에서 분기 없이 다룰 수 있다.
    """
    columns = ["주장", "확신도", "상태", "노트", "href", "date"]
    rows = []
    for note in load_notes(notes_dir):
        meta = note["meta"]
        if meta.get("status") not in INDEXED_STATUSES:
            continue
        rows.append(
            {
                "주장": str(meta.get("claim", "")).strip(),
                "확신도": CONFIDENCE_LABELS.get(
                    meta.get("confidence"), meta.get("confidence") or "—"
                ),
                "상태": STATUS_LABELS.get(meta.get("status"), meta.get("status")),
                "노트": str(meta.get("title", note["slug"])),
                "href": note["href"],
                "date": str(meta.get("date", "")),
            }
        )
    frame = pd.DataFrame(rows, columns=columns)
    if not frame.empty:
        frame = frame.sort_values("date", ascending=False).reset_index(drop=True)
    return frame


def to_markdown_table(frame: pd.DataFrame) -> str:
    """DataFrame을 마크다운 표 문자열로 만든다.

    pandas의 to_markdown은 tabulate에 의존하므로 직접 조립해 의존성을 줄인다.
    """
    header = "| 주장 | 확신도 | 상태 | 노트 |"
    divider = "| --- | :---: | :---: | --- |"
    lines = [header, divider]
    for row in frame.itertuples(index=False):
        claim = row.주장.replace("|", r"\|").replace("\n", " ")
        lines.append(
            f"| {claim} | {row.확신도} | {row.상태} | [{row.노트}]({row.href}) |"
        )
    return "\n".join(lines)


def main() -> int:
    frame = claims_frame()
    if frame.empty:
        print("인덱싱할 주장이 없습니다.")
        return 0
    print(to_markdown_table(frame))
    return 0


if __name__ == "__main__":
    sys.exit(main())
