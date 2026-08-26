# jesfcne.github.io

국내 공개 환경 데이터를 직접 수집·분석해 얻은 인사이트를 기록하는 사이트입니다.
Quarto로 만들고 GitHub Pages로 서빙합니다. → <https://jesfcne.github.io>

## 준비

```bash
pip install -r requirements.txt
```

Quarto가 필요합니다. Windows는 `winget install --id Posit.Quarto -e`,
그 외 플랫폼은 <https://quarto.org/docs/get-started/> 를 보세요.
설치 후 새 터미널에서 `quarto --version` 이 동작하는지 확인합니다.

## 로컬 개발

```bash
quarto preview     # 파일을 고칠 때마다 브라우저가 자동 갱신됩니다
quarto render      # docs/ 에 최종 산출물을 만듭니다
```

`quarto preview` 는 임시 디렉터리에 렌더링하므로 `docs/` 를 건드리지 않습니다.
푸시 전에는 반드시 `quarto render` 를 한 번 돌려야 합니다.

## 새 노트 만들기

```bash
cp -r notes/_template notes/2026-09-pm25-highdays
```

폴더명은 **`YYYY-MM-슬러그`** 규칙을 따릅니다. 슬러그는 영문 소문자와 하이픈만
씁니다. 목록 정렬은 프론트매터의 `date` 로 하지만, 폴더명에 연월이 있어야
파일 시스템에서 훑어볼 때 순서가 보입니다.

복사한 뒤 `index.qmd` 의 프론트매터를 채우고, 템플릿에 남아 있는 예시 값과
안내 주석을 지웁니다. 그다음 검증합니다.

```bash
python scripts/check_frontmatter.py
```

`_` 로 시작하는 디렉터리는 Quarto 렌더링과 listing에서 자동 제외되므로,
`notes/_template/` 은 사이트에 나타나지 않습니다.

## 노트 status 생애주기

| status | 뜻 | 사이트 노출 |
| --- | --- | --- |
| `seed` | 질문만 있고 자료를 아직 안 봄 | 노트 목록 |
| `probing` | 자료를 들춰보는 중, 결론 없음 | 노트 목록 |
| `draft` | 초고. 주장이 확정되지 않음 | 노트 목록 |
| `published` | 주장과 반증 조건 확정 | 노트 목록 + 인사이트 |
| `watching` | 발행됐고 반증 조건을 감시 중 | 노트 목록 + 인사이트 |
| `retired` | 새 자료가 주장을 뒤집음 | 노트 목록 |

`published` 이상은 `claim`, `confidence`, `falsified_if` 세 필드가 필수이며,
없으면 `check_frontmatter.py` 가 exit 1로 끝납니다.

주장이 뒤집혔을 때 노트를 지우지 않습니다. `retired` 로 바꾸고 본문에
무엇이 왜 틀렸는지 덧붙입니다. 인사이트 표에서는 빠지지만 노트는 남습니다.

## 댓글

노트마다 댓글난이 있습니다. 댓글은 이 저장소의 **GitHub Discussions**
(Announcements 카테고리)에 저장됩니다. 제3자 서비스에 글이 남지 않고
광고·추적기가 붙지 않습니다. 쓰는 사람은 GitHub 계정이 필요합니다.

설정은 `notes/_metadata.yml` 에 있습니다. 목록 페이지는 `comments: false` 로
꺼 두었고, 랜딩·인사이트 등 노트 밖 페이지에는 적용되지 않습니다.

`mapping: pathname` 이라 노트 **주소**로 토론을 짝짓습니다. 제목을 고쳐도
댓글이 흩어지지 않지만, **폴더명(슬러그)을 바꾸면 기존 댓글과 끊깁니다.**
한 번 정한 슬러그는 바꾸지 마세요.

댓글이 처음 달릴 때 giscus 가 해당 노트의 토론을 자동으로 만듭니다.
스팸이 오면 Discussions 에서 지우면 사이트에서도 사라집니다.

## 배포

CI에서 렌더링하지 않습니다. 로컬에서 렌더링한 결과를 커밋해 푸시합니다.

```bash
quarto render
python scripts/check_frontmatter.py
git add -A
git commit -m "노트 추가: ..."
git push
```

`docs/` 와 `_freeze/` 는 **커밋 대상입니다.** `docs/` 는 Pages가 그대로 서빙하고,
`_freeze/` 는 내용이 바뀌지 않은 노트를 다시 실행하지 않게 해 줍니다.
`_freeze/` 를 빼먹으면 다른 기기에서 렌더링할 때 모든 노트가 재실행됩니다.

### GitHub Pages 최초 설정

저장소 **Settings → Pages** 에서 Source를 **Deploy from a branch** 로 두고,
브랜치는 `main`, 폴더는 **`/docs`** 로 지정합니다.

`docs/.nojekyll` 은 `_quarto.yml` 의 `post-render` 가 렌더링할 때마다 만듭니다.
이 파일이 없으면 Jekyll이 Quarto가 만든 `*_files/` 디렉터리를 밑줄 접두사로 보고
무시해서 CSS와 JS가 404가 납니다.

## 구조

```
_quarto.yml          사이트 설정
index.qmd            랜딩
claims.qmd           인사이트 인덱스 (프론트매터에서 자동 생성)
status.qmd           수집 현황 (status/*.json 을 읽음)
sources.qmd          데이터 출처와 갱신 주기
about.qmd            소개
notes/               노트. 폴더 하나가 노트 한 편
  _template/         새 노트용 템플릿 (렌더링 제외)
probes/              일회성 수집 기록
watch/               감시 지표 함수 등록소
data/marts/          노트가 읽는 집계 파일
scripts/             프론트매터 검증과 인덱스 생성
docs/                렌더링 산출물 (커밋 대상)
_freeze/             실행 결과 캐시 (커밋 대상)
```

각 디렉터리의 규칙은 `probes/README.md` 와 `data/README.md` 에 적혀 있습니다.

## 아직 없는 것

데이터 수집기와 실제 분석 노트는 아직 없습니다. 지금은 뼈대만 있는 상태이며,
노트가 0개여도 `claims.qmd` 와 `notes/index.qmd` 가 깨지지 않도록 만들어 두었습니다.
