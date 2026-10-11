export const meta = {
  name: 'learn-from-edits',
  description: '발행된 글의 에이전트 초안(D)↔사람 완성본(F) 수정을 분류·누적해 quality-profile·post-reviewer·humanize 갱신을 제안한다. **자동 적용 금지** — 제안서만 만들고 사람 승인(/learn-from-edits 커맨드의 AskUserQuestion)으로만 정본화. E6(게이트 경계: 1인칭·출처·익명화·인용길이)은 학습 제외.',
  whenToUse: 'edit-history에 paired(초안↔완성본) 글이 ≥2편 쌓였을 때, 또는 /learn-from-edits 호출.',
  phases: [
    { title: 'Collect', detail: 'paired&미학습 슬러그의 D↔F diff' },
    { title: 'Classify', detail: 'edit을 E1~E6 분류 + taxonomy 매핑 (E6 격리)' },
    { title: 'Propose', detail: '≥2편 반복 패턴만 제안서 렌더 (자동적용 X)' },
  ],
}
const BLOG = '/Users/anhongje/dev/hongjeZZ.github.io'
const EH = `${BLOG}/.claude/edit-history`
const OUT = `${BLOG}/.pipeline/_learn`

const SLUGS_SCHEMA = { type: 'object', additionalProperties: false, required: ['paired'], properties: {
  paired: { type: 'array', items: { type: 'string' } } } }
const EDIT_SCHEMA = { type: 'object', additionalProperties: false, required: ['slug', 'edits'], properties: {
  slug: { type: 'string' },
  edits: { type: 'array', items: { type: 'object', additionalProperties: false,
    required: ['category', 'learnable', 'direction', 'before', 'after'], properties: {
      category: { type: 'string', enum: ['E1', 'E2', 'E3', 'E4', 'E5', 'E6'] }, // E1구조·증명 E2번역투 E3어체 E4인용·자산 E5사실 E6게이트경계
      taxonomy_id: { type: 'string', description: 'humanize 패턴ID(A-8 등) 또는 "gap"' },
      learnable: { type: 'boolean', description: 'E6·E5(사실)는 false(가드/리뷰만)' },
      direction: { type: 'string', description: '정규화 방향키 예 "A-2:통해→수단조사"' },
      before: { type: 'string' }, after: { type: 'string' } } } } } }
const PROPOSAL_SCHEMA = { type: 'object', additionalProperties: false, required: ['patterns', 'proposal_path'], properties: {
  proposal_path: { type: 'string' },
  patterns: { type: 'array', items: { type: 'object', additionalProperties: false,
    required: ['direction', 'category', 'support', 'slugs', 'target_artifact', 'rule', 'learnable'], properties: {
      direction: { type: 'string' }, category: { type: 'string' }, support: { type: 'integer' },
      slugs: { type: 'array', items: { type: 'string' } },
      target_artifact: { type: 'string', description: 'quality-profile §N | post-reviewer 축N | voice baseline 재빌드' },
      rule: { type: 'string', description: '추가/수정할 규칙 문장' }, learnable: { type: 'boolean' } } } } } }

// ── Collect ──
phase('Collect')
const col = await agent(
`Bash로 ${EH} 아래 각 <slug>/meta.json을 읽어, state=="paired"이고 아직 학습 안 된(meta.state!="learned") 슬러그 목록을 구한다.
각 슬러그에 draft.md와 published.md가 모두 있어야 한다(없으면 제외). paired 배열로 반환.`,
  { label: 'collect', phase: 'Collect', schema: SLUGS_SCHEMA })
const paired = (col && col.paired) || []
if (paired.length === 0) {
  log('학습할 paired(초안↔완성본) 글이 없습니다. blog-publish로 발행하면 edit-history에 쌓입니다.')
  return { learned: 0, note: 'no paired edits' }
}
log(`paired ${paired.length}편: ${paired.join(', ')}`)

// ── Classify (슬러그별 병렬) ──
phase('Classify')
const classified = (await parallel(paired.map((slug) => () =>
  agent(
`${EH}/${slug}/draft.md (D=에이전트 초안)와 ${EH}/${slug}/published.md (F=사람 완성본)를 읽고, D→F 수정을 의미 단위로 분류한다.
각 edit을 카테고리로: E1 구조·증명·논증(섹션 재배치·증명 삽입·코드↔해석 분리), E2 번역투·피동·관용구·접속사·리듬(~에 의해→행위자주어, 되어진다→된다, 문두접속사 삭제, 종결어미 다양화), E3 어체·표기(합쇼체↔해요체, 영어용어 병기, bold 개수), E4 인용·자산(docs 링크·참고자료·출처 라벨·이미지·mermaid 추가), E5 사실·수치(틀린 주장·과장 삭제·날조수치 — **learnable=false**, facts 검수만), E6 게이트 경계(1인칭→3인칭·출처 인용·익명화·40단어 인용 — **learnable=false**, 가드만).
**스타일 vs 내용 판별**: 의미가 동일한데 표현만 바뀐 것=스타일(learnable), 사실/내용이 바뀐 것=E5(learnable=false). 임베딩 없이 너의 판단으로(수치·고유명사·인용 보존 여부를 직접 대조).
direction은 정규화 방향키(예 "A-8:되어진다→된다", "E4:출처링크 추가", "구조:불릿→산문"). humanize 패턴ID에 매핑되면 taxonomy_id에, 안되면 "gap".
${EH}/${slug}/edits.jsonl 에 각 edit 1줄씩 Write도 한다. EDIT_SCHEMA로 반환.`,
    { label: `classify:${slug}`, phase: 'Classify', schema: EDIT_SCHEMA })
))).filter(Boolean)

const allEdits = classified.flatMap((c) => (c.edits || []).map((e) => ({ ...e, slug: c.slug })))
log(`총 edit ${allEdits.length}건 (E6/E5 learnable=false 격리 포함)`)

// ── Propose (≥2편 반복만) ──
phase('Propose')
const prop = await agent(
`아래 분류된 edit들(여러 글에 걸침)을 보고, **2편 이상(서로 다른 slug)에서 같은 방향(direction)으로 반복된 패턴만** 승격 후보로 골라 제안서를 만든다. 1편/1회는 노이즈로 제외.
각 후보 패턴을:
- target_artifact 매핑: E1→quality-profile §1~§8 + post-reviewer 축5 / E2→quality-profile §7.2 (humanize quick-rules는 플러그인 자동 생성 파일이라 수정 대상 아님) / E3→quality-profile §7.1 + 축5 / E4→quality-profile §5·§6 + 축6 / E5→post-reviewer facts 축(가드만, learnable=false) / E6→**자동변경 금지, 사람만**(가드 제안만).
- **비대칭 검수 규칙**: 사용자가 '삭제'한 패턴 → 검수가 "초안에 넣지 마라". '추가'한 패턴 → 검수가 "빠지면 flag".
- rule: quality-profile/post-reviewer에 추가·수정할 규칙 문장 + 근거 slug별 before→after 스니펫.
Bash로 mkdir -p ${OUT}; 제안서를 ${OUT}/proposal-$(date +%Y%m%d-%H%M).md 에 Write(파일/§/before→after/support/충돌검사/learnable 포함). E5·E6 패턴은 "⚠ learnable=false — 가드/리뷰만, 자동 룰 금지" 명시.
PROPOSAL_SCHEMA로 반환(proposal_path 포함). **이 워크플로는 제안서만 만들고 어떤 아티팩트도 직접 수정하지 않는다**(사람 승인은 /learn-from-edits 커맨드가 처리).

EDITS:
${JSON.stringify(allEdits).slice(0, 12000)}`,
  { label: 'propose', phase: 'Propose', schema: PROPOSAL_SCHEMA })

const learnable = (prop && prop.patterns || []).filter((p) => p.learnable)
log(`제안 패턴 ${prop ? prop.patterns.length : 0}건 (learnable ${learnable.length}, 가드전용 ${(prop ? prop.patterns.length : 0) - learnable.length})`)
return { learned: 0, paired_count: paired.length, patterns: prop ? prop.patterns : [], proposal: prop ? prop.proposal_path : null,
  note: '제안서 생성 완료 — /learn-from-edits 커맨드가 AskUserQuestion으로 승인받아 적용. 자동 적용 안 함.' }
