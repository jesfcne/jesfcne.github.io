"""렌더링 산출물 폴더에 .nojekyll 을 만든다.

Jekyll 은 밑줄로 시작하는 경로를 무시한다. Quarto 가 만드는 `*_files/` 가
여기 걸려 CSS/JS 가 404 나므로, .nojekyll 로 Jekyll 처리 자체를 끈다.

출력 폴더가 프로파일마다 다르므로(docs/, preview/editorial/ ...) 경로를
하드코딩하지 않고 Quarto 가 넘겨주는 환경변수를 쓴다.
"""

import os
import sys
from pathlib import Path

out_dir = Path(os.environ.get("QUARTO_PROJECT_OUTPUT_DIR", "docs"))
if not out_dir.is_dir():
    print(f"출력 폴더가 없습니다: {out_dir}", file=sys.stderr)
    raise SystemExit(1)

(out_dir / ".nojekyll").touch()
