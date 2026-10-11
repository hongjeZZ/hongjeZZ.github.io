---
description: 발행된 블로그 전체(_posts/)의 제목·카테고리·태그 정합성 검사 — 파편화(같은 뜻 다른 표기)·트리 위반·장황한 제목을 잡는다
argument-hint: "[--fix] [--post <slug>]"
allowed-tools: Bash, Read, Edit
---

# /lint-blog

발행 후 **블로그 전체 글**의 분류(taxonomy)를 검사한다. 파편화는 한 글만 봐선 안 보이고 코퍼스 전체를 대조해야 하므로, 기본 대상은 `_posts/` 전부다. `blog-publish` 초안 단계가 아니라 **발행 뒤** 도는 게이트다(파이프라인 `/ingest-to-blog` 7단계에서 자동 호출되며, 이 명령으로 언제든 단독 실행).

## 검사 항목 (SSOT: `.claude/blog-taxonomy.json`)

| 코드 | 무엇 | 기본 심각도 |
|---|---|---|
| `alias` | SSOT에 정답 표기가 있는데 다른 표기로 씀 (`crd`→`CRD`, `argo-workflows`→`Argo Workflows`) | block |
| `fragmentation` | 같은 정규형인데 표기가 2개 이상(정답 미정) — 하나로 통일 필요 | block |
| `tag-style` | 소문자/kebab 영문 태그 — 고유명사면 공식표기, 개념이면 한글 (정책: 고유명사 공식표기 + 개념 한글) | warn |
| `category` | SSOT 카테고리 트리에 없는 값 / 상위-하위 불일치 | block/warn |
| `title` | 부제 나열형(`…: A·B·C`)·과장어("완벽 가이드")·40자 초과. PS 글은 예외 | warn |

심각도는 SSOT `severity`에서 조정한다.

## 실행

```bash
cd ~/dev/hongjeZZ.github.io

# 1) 전체 검사 (기본)
python3 .claude/taxonomy-lint.py            # block 있으면 exit 1
python3 .claude/taxonomy-lint.py --json     # 도구·파이프라인용 JSON

# 2) 특정 글만 (파편화는 여전히 전체 코퍼스 기준으로 판정)
python3 .claude/taxonomy-lint.py --post <slug>

# 3) 태그 표기 일괄 정규화 (제목·카테고리는 자동 수정 안 함 — 수동)
python3 .claude/taxonomy-lint.py --fix
```

`$ARGUMENTS`에 `--fix`나 `--post <slug>`가 있으면 그대로 붙여 실행한다.

## 처리 (기본 = 검출 → 수정 → 발행까지 한 작업으로)

`/lint-blog`은 리포트에서 끝나지 않는다 — **검출한 문제를 고치고 커밋·푸시(발행)까지** 한 흐름으로 처리한다. `--check`(리포트만) 인자가 있으면 1단계만.

1. **검출**: `python3 .claude/taxonomy-lint.py --json`로 block/warn 수집. `--check`면 결과만 보여주고 종료.
2. **태그 수정**: `python3 .claude/taxonomy-lint.py --fix`로 태그를 SSOT 정답 표기로 일괄 치환(파편화·alias 해소). block-style tags는 수동.
3. **제목 수정**: 제목 finding(부제 나열형 `…: A·B·C`·과장어·40자 초과)은 §9대로 **간결한 '<주제> 정리/비교'로 직접 고친다**(PS 글 제외, 의미·시리즈 번호 보존). URL은 파일명 기반이라 title 변경은 링크에 영향 없음.
4. **카테고리 수정**: 트리 위반은 SSOT 트리에 맞게 글의 categories를 고치거나(오분류), 정당한 신규 분류면 `blog-taxonomy.json` 트리에 추가.
5. **새 표기 등록**: 새로 정한 정답 표기·고유명사는 `blog-taxonomy.json`(`tag_aliases`/`proper_nouns`)에 반영해 다음부터 자동 검출.
6. **발행**: 변경분만 스테이징 → `chore(taxonomy): 태그·제목 정합성 정리` 커밋 → push. GitHub Actions가 배포. **블로그 커밋 규칙**: author=hongjeZZ `<ajyong316@gmail.com>`, `Co-Authored-By: Claude` 트레일러 금지(개인 공개 repo). 유지보수 변경이므로 main 직접 커밋(새 글은 `/ingest-to-blog`가 PR).
7. 재검사로 block 0 확인 후 배포 성공까지 지켜본다.

## 새 표기 규칙을 추가할 때

`blog-taxonomy.json`만 고치면 된다(코드 수정 불필요):
- 같은 뜻 다른 표기 → `tag_aliases`에 `"변형": "정답"` 추가(변형은 어떤 표기든 정규화 매칭됨).
- 새 고유명사 공식표기 → `proper_nouns`에 추가.
- 공식이 소문자인 식별자(오탐 방지) → `lowercase_ok`에 추가.
- 카테고리 신설 → `categories` 트리에 추가.

## 관련
- 작성 규율: `quality-profile.md` §9(제목·카테고리·태그) — 초안부터 파편화를 안 만들게.
- 파이프라인: `/ingest-to-blog` 7단계(발행 후 자동 호출).
