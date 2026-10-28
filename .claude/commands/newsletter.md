---
description: 기후·환경 주간 브리핑 한 호를 만든다 (피드백 → 리서치 → 검증 → 선정 → 보강 → 집필 → 검수 → PR)
argument-hint: "[호, 예: 2026-W43] [--from 단계번호]"
---

# /newsletter

기후·환경 주간 브리핑 한 호를 파이프라인에 따라 만들고 PR 을 연다.
운영 기준은 `METHODOLOGY.md`, 단계별 산출물 형식은 `pipeline/README.md` 에 있다.

인자: `$ARGUMENTS`
- 호: 생략하면 `python scripts/pipeline.py default-issue` (직전 주)
- `--from N`: N 단계부터 다시. 생략하면 `pipeline.py status` 의 "다음 단계"부터 이어서

## 오케스트레이터의 원칙

- 당신(메인 세션)은 **조율만** 한다. 리서치·집필·검수를 직접 하지 않고 에이전트에게 맡긴다.
- 에이전트에게는 **호 번호와 파일 경로만** 넘긴다. 이전 단계의 내용을 요약해 덧붙이지 않는다
  (특히 reviewer 에게는 brief 나 집필 의도를 절대 전하지 않는다).
- 큰 JSON 파일을 직접 읽지 않는다. 상태는 스크립트 출력으로 판단한다.
- 단계마다 형식 검사가 통과해야 다음 단계로 간다. 실패하면 같은 에이전트에게 오류 메시지를 주고 고치게 한다(최대 2회). 그래도 안 되면 멈추고 사용자에게 알린다.
- 동시에 띄우는 에이전트는 최대 3개(리서치 단계만).
- 단계가 끝날 때마다 커밋한다: `git add pipeline/<호> issues/<호> _freeze/issues/<호> data/series && git commit -m "뉴스레터 <호>: <단계 이름>"`
- 각 단계를 시작·끝낼 때 사용자에게 한 줄로 알린다.

## 0. 준비

1. `python scripts/pipeline.py status <호>` 로 진행 상황과 대상 주를 확인한다.
2. 작업 트리가 깨끗한지 본다 (`git status --short`). 아니면 멈추고 사용자에게 묻는다.
3. 브랜치: `issue/<호>` 가 있으면 그리로 전환(이어서 하기). 없으면 최신 main 에서 만든다:
   `git switch main && git pull --ff-only && git switch -c issue/<호>`
4. `--from N` 이면 N 단계 이후의 산출물은 새로 만든다(덮어쓰기). 그 전 단계 산출물은 그대로 쓴다.

## 단계

### 0 피드백 수집
`feedback` 에이전트: "호 <호>의 피드백을 수집해 pipeline/<호>/feedback.md 를 써라."

### 1 리서치 (병렬 3)
`researcher` 에이전트 셋을 **한 번에** 띄운다. 각각:
"호 <호>, 역할 <global|korea|academic>. 결과를 pipeline/<호>/sources-<역할>.json 에 써라."

모두 끝나면 `python scripts/pipeline.py merge-sources <호>`. 오류가 난 역할만 다시 맡긴다.

### 2 출처 검증
1. `python scripts/verify_sources.py pipeline/<호>/sources.json`
2. "에이전트 확인 필요"가 1건 이상이면 `verifier` 에이전트: "pipeline/<호>/verified.json 의 needs_agent 항목을 확인하라."
3. `python scripts/validate_schema.py pipeline/<호>/verified.json`
4. 통과 항목이 글로벌 3·국내 2 이슈를 고르기에 부족해 보이면(예: 통과 10건 미만) 사용자에게 알리고 계속할지 묻는다.

### 3 분석·선정
`analyst` 에이전트: "호 <호>의 brief 를 pipeline/<호>/brief.md 에 써라."

### 4 자료 보강
1. `data-scout` 에이전트: "pipeline/<호>/brief.md 의 보강 요청을 처리하라."
2. `background-verified.json` 에 "에이전트 확인 필요"가 있으면 `verifier`: "pipeline/<호>/background-verified.json 의 needs_agent 항목을 확인하라."
3. `python scripts/validate_schema.py pipeline/<호>/background-verified.json`

### 5 집필
`writer` 에이전트: "호 <호>를 써라."
끝나면 직접 확인: `python scripts/check_frontmatter.py issues/<호>` 가 ✓ 인지.

### 6 검수 (최대 3회)
회차 r = 1 부터:
1. **매번 새** `reviewer` 에이전트: "호 <호>를 검수하라. 회차는 r 이다."
2. `python scripts/validate_schema.py pipeline/<호>/review.json`
3. `pass` 면 7단계로.
4. `revise` 이고 r < 3 이면: `pipeline/<호>/review.json` 을 `review-r<r>.json` 으로 복사해 남기고,
   `writer` 에이전트: "pipeline/<호>/review.json 의 지적을 반영해 호 <호>를 고쳐라." → r+1 로 1번부터.
5. r = 3 에서도 `revise` 면 멈추지 않고 7단계로 간다. 남은 지적은 PR 본문에 미해결 항목으로 들어간다.

### 7 PR
1. `python scripts/pipeline.py pr-body <호>`
2. 마지막 커밋 후 `git push -u origin issue/<호>`
3. PR 만들기:
   - `gh` 가 있으면: `gh pr create --repo jesfcne/jesfcne.github.io --base main --head issue/<호> --title "뉴스레터 <호>: <title>" --body-file pipeline/<호>/pr-body.md`
     (이 저장소는 다른 저장소의 포크로 등록되어 있어 `--repo` 를 빼면 원본 저장소로 PR 이 갈 수 있다. 반드시 넣는다.)
   - `gh` 가 없으면: 사용자에게 아래 링크와 `pipeline/<호>/pr-body.md` 내용을 주고 PR 을 만들게 한다.
     `https://github.com/jesfcne/jesfcne.github.io/compare/main...issue/<호>?expand=1`

## 마무리 보고

사용자에게:
- PR 링크 (또는 만드는 방법)
- 이번 호 제목과 이슈 5개
- 출처: 후보 수, 통과·제외 수
- 검수: 반려 횟수, 미해결 항목
- 사람이 특히 확인해야 할 점 (검수 미해결, 3등급 출처만 있는 이슈, 프리프린트, 피드백의 정정 요청)
