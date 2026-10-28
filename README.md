# jesfcne.github.io

한 주의 기후·환경 이슈를 긴 흐름 속에서 정리하는 주간 뉴스레터
**기후·환경 주간 브리핑**의 저장소입니다. → <https://jesfcne.github.io>

운영 방식(에이전트 구성, 파이프라인, 출처 정책, 승인 절차)은
[`METHODOLOGY.md`](METHODOLOGY.md)에 있습니다.

## 준비

```bash
pip install -r requirements.txt
```

Quarto가 필요합니다. Windows는 `winget install --id Posit.Quarto -e`,
그 외 플랫폼은 <https://quarto.org/docs/get-started/> 를 보세요.
CI와 같은 버전(`.github/workflows/deploy.yml`의 `version`)을 쓰는 것이 좋습니다.

## 로컬 개발

```bash
quarto preview     # 파일을 고칠 때마다 브라우저가 자동 갱신됩니다
quarto render      # _site/ 에 최종 산출물을 만듭니다 (커밋하지 않음)
```

## 발행 흐름

1. 새 호는 `issue/<YYYY-Www>` 브랜치에서 만들고 PR을 엽니다.
2. PR이 열리면 GitHub Actions가 렌더링만 해서 깨지지 않는지 확인합니다.
3. 내용을 검토한 뒤 PR을 머지하면, 그것이 발행 승인입니다.
   Actions가 렌더링해 GitHub Pages에 배포합니다.

`main`에는 직접 푸시하지 않습니다.

차트처럼 코드를 실행하는 호는 로컬에서 `quarto render`를 한 번 돌려
`_freeze/`를 함께 커밋해야 합니다. CI는 코드를 다시 실행하지 않습니다.

### GitHub 설정 (최초 1회)

- **Settings → Pages**: Source를 **GitHub Actions**로 지정
- **Settings → Rules → Rulesets** (또는 Branches): `main`에 PR 필수, 직접 푸시 금지

## 구조

```
_quarto.yml          사이트 설정 (렌더링 대상, 테마, 필터)
index.qmd            랜딩 (최근 호)
about.qmd            소개
issues/              각 호. 폴더 하나가 한 호 (issues/2026-W44/index.qmd)
  index.qmd          지난 호 목록 + RSS
  _metadata.yml      댓글(giscus) 설정
filters/             각 호 끝 정정 제보 안내
themes/              SCSS 테마 (라이트/다크)
scripts/             보조 스크립트 (OG 카드 생성 등)
.github/workflows/   렌더링·배포
```

## 댓글

각 호의 댓글은 이 저장소의 **GitHub Discussions**(Announcements 카테고리)에
저장됩니다. `mapping: pathname`이라 호의 주소로 토론을 짝지으므로,
**한 번 정한 폴더명은 바꾸지 마세요.** 바꾸면 기존 댓글과 연결이 끊깁니다.

## 이전 사이트

이 저장소의 이전 주제(환경 데이터 노트)는 `archive/data-notes-v1` 태그에 보존되어 있습니다.
