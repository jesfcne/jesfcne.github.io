# pipeline/

주차별 파이프라인 산출물을 남기는 곳입니다. 폴더 하나가 한 호(`2026-W43/`)이며,
나중에 "이 수치는 어디서 나왔나"를 추적할 수 있도록 모두 커밋합니다.

| 파일 | 단계 | 형식 |
| --- | --- | --- |
| `feedback.md` | 0 피드백 수집 | 마크다운 |
| `sources.json` | ① 리서치 | `scripts/schema/source-list.schema.json` |
| `verified.json` | ② 출처 검증 | 같은 스키마 + `verification` |
| `brief.md` | ③ 분석·선정 | 마크다운 |
| `background.json` | ④ 자료 보강 | `source-list` |
| `background-verified.json` | ④ 자료 보강 검증 | 같은 스키마 + `verification` |
| `review.json` | ⑥ 검수 | `scripts/schema/review.schema.json` |

작성 예시는 `scripts/schema/examples/sources.json`에 있습니다.

```bash
python scripts/validate_schema.py pipeline/2026-W43/sources.json   # 형식 검사
python scripts/verify_sources.py pipeline/2026-W43/sources.json    # 출처 검증 → verified.json
python scripts/make_references.py 2026-W43                         # 원고의 인용 → references.json
python scripts/check_frontmatter.py issues/2026-W43                # 호 형식 검사
```
