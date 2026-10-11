---
description: 위키 페이지를 블로그 글로 만드는 자동 파이프라인 (blog-publish 워크플로 실행)
argument-hint: "<wiki-slug> [rounds] [--til]"
allowed-tools: Bash, Read, Write, Edit, Task
---

# /draft-post

위키 한 페이지(`$ARGUMENTS`의 첫 인자 = slug)를 블로그 초안으로 변환한다. `blog-publish` 워크플로를 실행해 **출처 게이트 → quality-profile 초안 → 백테스트 루프(품질·표절·기밀·보이스·사실) → 리포트**를 자동 수행한다.

## 발행 단위·범위 (slug 하나 = 한 글)
- **앵커 = `wiki/sources/<slug>` 한 페이지 + 그 frontmatter `sources:`에 적힌 raw.** slug 하나가 한 글이다. concepts·comparisons·entities는 앵커가 아니다(본문 보조·상호링크용).
- **한 주제가 raw 여러 페이지면(core+advanced 등) → 시리즈로 slug별 따로 발행.** 예: `/draft-post argo-workflows-core`(1편) → `/draft-post argo-workflows-advanced`(2편). 한 번에 형제 raw를 끌어오지 않는다. 시리즈는 frontmatter title에 편 번호로 잇는다(예: "Argo Workflows (1) 핵심 아키텍처", "Argo Workflows (2) 고급 운영").

## 동작
1. **출처 게이트**(`provenance-gate.py`)로 발행 적격성 판정:
   - 🟩 own → 내 글로 작성
   - 🟥 타사블로그/공식문서 → **cite-only 정리글**(출처 명시·인용 ≤40단어·경험 날조 금지)
   - ⛔ 사내기밀 → 중단
   - ⚠ 미stamp own-추정 → 중단. 사용자에게 확인받아 위키 페이지에 `provenance: own`을 stamp한 뒤 재실행.
2. quality-profile 적용 초안 → `.pipeline/<slug>/draft.md`.
3. **백테스트 루프**를 clean까지 반복(기본 2라운드, `rounds` 인자로 조절). 매 라운드: 품질·표절·기밀·보이스·사실 5축 병렬 검사 → block 있으면 리비전 → 재검사.
4. `report.md` 생성. **`_posts/`엔 직접 쓰지 않는다** — 사람이 `.pipeline/<slug>/draft.md`를 검토 후 이동하고 PR. git pre-commit hook이 `_posts/` 변경분에 기밀 게이트를 재실행한다.

## 실행
```
Workflow({ name: "blog-publish", args: { slug: "<slug>", rounds: 2 } })
```
`$ARGUMENTS`에 **`--til`** 이 있으면 `args`에 `til: true`를 넣는다:
```
Workflow({ name: "blog-publish", args: { slug: "<slug>", rounds: 2, til: true } })
```
→ **TIL 모드(quality-profile §10)**: 가볍게·핵심만(개조식·짧게·다이어그램/참고자료 완화, `TIL` 태그 포함), 백테스트도 TIL답게 완화(충실성·공식 링크 필수·합쇼체 register 축 완화). **단 기밀·표절·사실·§3 비인칭 톤은 정규 글과 동일하게 검증**.

완료 후 `.pipeline/<slug>/draft.md`와 `report.md`를 사용자에게 보여주고, 미stamp/사내/표절로 중단됐으면 그 이유와 다음 행동을 안내한다.

## 워크플로 종료 후 — 로컬 캡처 질문 (메인 루프에서만)
워크플로 반환값의 `captures_needed`(로컬 테스트 결과·스크린샷이 들어가면 좋은 자리)가 있으면 **AskUserQuestion으로 사용자에게 묻는다** (이 질문은 백그라운드 워크플로 안에서는 못 하므로 여기서 처리):
- 질문 형식: *"여기에 로컬 테스트 결과/캡처가 들어가면 좋습니다 — <where>: <what>. ① 직접 IDE에서 캡처해 첨부하시겠어요? ② 안 넣고 그 자리를 빼는 방향으로 다시 수정할까요?"*
- **① 첨부** → `<!-- CAPTURE-NEEDED: ... -->` 마커와 어디에 무엇을 넣을지 안내를 draft에 남겨 사용자가 채우게 한다(측정 숫자 `____` 유지).
- **② 제거** → 해당 자리를 빼고 앞뒤 문장이 자연스럽게 이어지도록 draft를 수정한다(이때 §1 충실성이 약해지면 그 점도 알린다).
캡처가 여러 건이면 한 번의 AskUserQuestion에 여러 질문으로 묶어 묻는다. **_posts/ 이동·발행은 사용자 확인 후에만.**

## 커버 이미지 (선택)
글에 기술 로고·대표 이미지를 커버로 붙이려면 **`/cover-image <slug>`** 를 쓴다 — 후보를 찾아 보여주고 사용자가 고르면 `assets/img/<slug>/cover.png`로 저장·삽입한다(본문 첫 이미지가 홈 썸네일로도 자동 노출). 발행 전 초안·발행글 모두 가능.

ARGUMENTS: $ARGUMENTS
