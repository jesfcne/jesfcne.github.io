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

## 새 호 만들기

```bash
cp -r issues/_template issues/2026-W43
```

폴더명은 **대상 주**의 ISO 주차(`YYYY-Www`)입니다. 2026-W43은 10월 19일(월)~25일(일)을
다루고 10월 26일(월)에 발행합니다. 작성 규칙은 [`editorial/style-guide.md`](editorial/style-guide.md),
출처 등급은 [`editorial/source-whitelist.yml`](editorial/source-whitelist.yml)을 따릅니다.
출처는 같은 폴더의 `references.json`(CSL JSON)에 넣고 본문에서 `[@id]`로 인용합니다.
차트는 `lib/briefplot.py`의 함수로 그립니다.

## 검증 도구

파이프라인 산출물과 각 호의 형식을 검사하는 스크립트가 `scripts/`에 있습니다.
사용법은 [`pipeline/README.md`](pipeline/README.md)를 보세요. PR을 열면 CI가
`pytest`, 산출물 형식 검사, 각 호 형식 검사를 렌더링 전에 돌립니다.

```bash
pytest               # 검증 스크립트 시험 (네트워크 없이)
pytest -m network    # 실제 Crossref·원문으로 확인하는 시험
```

## 장기 연속자료

`editorial/series-registry.yml`에 등록한 자료를 `data/series/<id>/`로 내려받습니다.
정리된 표(`data.csv`)와 수집 기록(`meta.json`)은 커밋하고, 원파일은 커밋하지 않습니다.

```bash
python scripts/fetch_series.py            # 전부 (이번 주에 받은 것은 건너뜀)
python scripts/fetch_series.py --force    # 다시 받기
```

각 호에서는 `load_series("co2-mlo-annual")`로 읽고, 캡션은 `caption(meta)`로 만듭니다.

## 디자인 견본

`issues/_sample/`은 모든 블록을 한 번씩 써 본 견본 호입니다(문구·출처는 임의, 차트는 실제 장기 자료).
사이트에는 올라가지 않고, 견본 프로파일로만 렌더링됩니다.

```bash
quarto render --profile sample     # .quarto/sample-site/ 에 생성 (커밋하지 않음)
```

## 차트와 _freeze

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
issues/              각 호. 폴더 하나가 한 호 (issues/2026-W43/index.qmd)
  index.qmd          지난 호 목록 + RSS
  _metadata.yml      각 호 공통 설정 (댓글, 출처 양식, 코드 숨김)
  _template/         새 호 템플릿
  _sample/           디자인 견본 (사이트 제외)
editorial/           스타일 가이드, 출처 화이트리스트, 인용 양식(nature.csl)
lib/briefplot.py     차트 공통 스타일 (라이트/다크)
filters/             호수·기간 부제, 정정 제보 안내
themes/              SCSS 테마 (newsletter.scss 가 뉴스레터 블록)
scripts/             검증 스크립트, 스키마(schema/), OG 카드 생성
pipeline/            주차별 파이프라인 산출물 (감사 기록)
data/series/         장기 연속자료 (fetch_series.py 가 생성)
tests/               검증 스크립트 시험
.github/workflows/   렌더링·배포
```

## 댓글

각 호의 댓글은 이 저장소의 **GitHub Discussions**(Announcements 카테고리)에
저장됩니다. `mapping: pathname`이라 호의 주소로 토론을 짝지으므로,
**한 번 정한 폴더명은 바꾸지 마세요.** 바꾸면 기존 댓글과 연결이 끊깁니다.

## 이전 사이트

이 저장소의 이전 주제(환경 데이터 노트)는 `archive/data-notes-v1` 태그에 보존되어 있습니다.
