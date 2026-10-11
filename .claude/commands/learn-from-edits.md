---
description: 발행 글의 에이전트 초안↔사람 완성본 수정을 학습해 글쓰기 프로파일·검수 조건을 점진 강화 (사람 승인 게이트)
argument-hint: "[--slug <slug>] (기본: 모든 paired 글)"
allowed-tools: Bash, Read, Write, Edit, Task
---

# /learn-from-edits

발행된 글의 **에이전트 초안(D) ↔ 사람이 수정한 완성본(F)** 차이를 학습해, 글이 쌓일수록 **글쓰기 스킬(quality-profile)과 검수 조건(post-reviewer·백테스트 축)을 함께 성숙**시킨다. 자동 변이 금지 — **사람 승인으로만** 정본화한다.

## 동작

### 1. 분석 (워크플로)
```
Workflow({ name: "learn-from-edits" })
```
→ paired(초안↔완성본) 글들을 수집→분류(E1~E6)→누적해, **2편 이상에서 반복된 패턴**만 제안서(`.pipeline/_learn/proposal-*.md`)로 만든다. paired가 없으면 "아직 학습할 글 없음"으로 종료(blog-publish로 발행하면 edit-history에 쌓임).

### 2. 사람 승인 (메인 루프 — AskUserQuestion)
워크플로 반환의 `patterns` 중 **learnable=true**인 것만 사용자에게 묻는다. 각 패턴마다:
- 방향키 + 근거 slug별 before→after 스니펫 + support(반복 편수) + 대상 아티팩트(§)를 보여주고
- *"이 수정 패턴을 [quality-profile §N / post-reviewer 축N]에 규칙으로 반영할까요?"* 를 AskUserQuestion으로.
- **E5(사실)·E6(게이트 경계: 1인칭·출처·익명화·인용길이)** 패턴은 `learnable=false` — **자동 적용 금지**. publish-policy·deny-list 변경은 사람이 직접만. 제안서엔 정보로만 표시하고 승인 대상에서 제외.

### 3. 적용 (승인분만)
승인된 패턴을 **비대칭**으로 반영한다:
- 사용자가 **삭제**한 패턴(과설명·AI티) → quality-profile에 "쓰지 마라" + post-reviewer 검수에 "초안에 있으면 flag".
- 사용자가 **추가**한 패턴(출처·caveat·1인칭·구체) → quality-profile에 "넣어라" + post-reviewer에 "빠지면 flag".
- E2(번역투류)는 `quality-profile.md` §7.2(S1 digest)에 반영한다. humanize quick-rules는 플러그인이 taxonomy에서 자동 생성하고 업데이트 때 덮어쓰므로 수정 대상이 아니다.
- 대상 파일을 Edit: `quality-profile.md`(§ 해당, E2는 §7.2), `agents/post-reviewer.md`(축).

### 4. 버전 bump + 마무리
- `quality-profile.md` frontmatter `version` 한 단계 올리고(0.2→0.3), 변경 한 줄을 `.claude/edit-digests/applied.jsonl`에 기록(날짜·패턴·아티팩트·근거 slug).
- `python3 .claude/voice-similarity.py baseline` 재실행(코퍼스 성장 반영) + `discriminate`로 변별 유지 확인. **AI 보조 발행글은 golden에서 자동 제외**되므로 baseline 드리프트 없음(in-voice 확인 후 골든 편입하려면 `voice-golden-allow.txt`에 추가).
- 적용한 slug의 `edit-history/<slug>/meta.json` state를 `learned`로 닫는다(중복 학습 방지).

## 안전 원칙
- **제안서만 자동 생성, 적용은 사람 승인 후.** (MEMORY blog-publish-gates의 fail-closed와 동일 철학)
- 학습 신호는 **사람 수정(F)에서만** — 에이전트 초안(D)이나 사람 미수정 발행은 학습 안 함(자기출력 피드백 루프 방지).
- 1편/1회 수정은 노이즈로 제외(≥2편 반복만 후보).

ARGUMENTS: $ARGUMENTS
