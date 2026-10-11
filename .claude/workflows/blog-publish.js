export const meta = {
  name: 'blog-publish',
  description: '위키 페이지 → 블로그 초안 자동 파이프라인: 출처 게이트 → quality-profile 초안 → 백테스트 루프(품질·표절·기밀·보이스·사실, clean까지 반복) → 리포트. 발행은 호출자 몫(사람 PR, 또는 위키 /ingest-to-blog가 post-reviewer 통과 후 PR·머지) + git hook 게이트.',
  whenToUse: '위키 한 페이지를 블로그 글로 만들 때. args:{slug, rounds?}. mode(own/cite-only)는 게이트가 자동 판정.',
  phases: [
    { title: 'Gate', detail: '출처/기밀 게이트 (provenance-gate.py)' },
    { title: 'Draft', detail: 'quality-profile 적용 초안' },
    { title: 'Enrich', detail: '공식문서 인라인 링크·mermaid·라이선스 이미지·참고자료·캡처필요 마킹' },
    { title: 'Humanize', detail: 'humanize-korean monolith 윤문 → 독립 S1 재탐지 → 1회 보정', model: 'opus' },
    { title: 'Backtest', detail: '품질·표절·기밀·보이스·사실·인용 다축 검사 + 리비전 루프' },
    { title: 'Report', detail: '최종 초안 + 통과 리포트 (발행 안 함)' },
  ],
}

const WIKI = '/Users/anhongje/dev/llm-wiki'
const BLOG = '/Users/anhongje/dev/hongjeZZ.github.io'
const GATE = `${BLOG}/.claude/provenance-gate.py`
const PROFILE = `${BLOG}/.claude/quality-profile.md`
const POLICY = `${BLOG}/.claude/publish-policy.md`
const PLUGIN = '/Users/anhongje/.claude/plugins/marketplaces/im-not-ai'
const QUICK_RULES = `${PLUGIN}/skills/humanize-korean/references/quick-rules.md`

let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = { slug: A } } }
const slug = A && A.slug
const ROUNDS = (A && A.rounds) || 2
const TIL = !!(A && A.til)   // TIL 모드 — 가볍게·핵심만 (quality-profile §10)
if (!slug) { log('⚠ args.slug 필요. 예: Workflow({name:"blog-publish", args:{slug:"jvm-warmup"}})'); return { error: 'no slug' } }
const SCRATCH = `${BLOG}/.pipeline/${slug}`
const DRAFT = `${SCRATCH}/draft.md`
// TIL 모드 완화 주입 (안전·정직·§3 톤·기밀은 완화하지 않는다 — 아래 문자열이 빈 값이면 정규 글)
const tilDraft = TIL ? `
2-2) **TIL 모드다 (§10) — 가볍게, 핵심만.** 짧은 학습 노트다: (1) raw 전수 재현이 아니라 개념의 정의·동작·요점만 선별(§1 충실성 완화). (2) 개조식 우선 — "X란?" 정의 + 요점 bullet, 긴 합쇼체 산문 강요 금지(§7.1 완화, 터스한 해라체 '~다'·명사형 노트 어조 허용). (3) 한두 화면 분량, ### 소제목 몇 개면 충분(§2.5 완화, ## 큰 섹션 남발 금지). (4) mermaid·이미지는 대개 생략, 코드는 짧은 예시 1~2개. (5) 공식 링크 있으면 1개, 없어도 됨·참고자료 섹션 선택(§6 완화). (6) frontmatter tags에 \`TIL\` 포함. **단 §3 비인칭·선언형(1인칭·감상 금지)과 안전·정직은 그대로.**` : ''
const tilQuality = TIL ? ' **이 글은 TIL(§10)이다** — 충실성 미달(a: 앵커 raw 누락·축약)·난이도 계단(f)은 적용하지 않는다(TIL은 핵심만 간추리는 게 정상, 짧고 개조식이어도 OK). 안전·정직·§3 톤·기밀은 그대로 본다.' : ''
const tilVoice = TIL ? ' **TIL(§10)은 개조식·terse 노트 어조가 정상** — 합쇼체가 아니어도(해라체 "~다"·bullet 나열) off-voice·노트모드 finding으로 보지 않는다. voice-similarity 점수가 낮아도 TIL이면 무시. 한국어 자연스러움·AI 번역투(§7.2 S1)만 본다.' : ''
const tilRefs = TIL ? ' **TIL(§10)이므로 공식 문서 인라인 링크·참고 자료 섹션은 필수가 아니다** — 없거나 1개여도 warn 내지 않는다(깨진 링크·가짜 인용만 지적).' : ''
const tilHuman = TIL ? ' (TIL이면 개조식·해라체 노트 어조를 보존한다 — 합쇼체로 바꾸지 말 것.)' : ''
log(`blog-publish: ${slug} (rounds=${ROUNDS}${TIL ? ', TIL' : ''}) → ${SCRATCH}`)

const GATE_SCHEMA = { type: 'object', additionalProperties: false, required: ['gate1', 'gate2_hits', 'sources', 'note'], properties: {
  gate1: { type: 'string', enum: ['own', 'third-party', 'reference', 'internal', 'mixed', 'unstamped', 'missing'] },
  gate2_hits: { type: 'integer' },
  sources: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['path', 'provenance'], properties: { path: { type: 'string' }, provenance: { type: 'string' } } } },
  note: { type: 'string' } } }
const DRAFT_SCHEMA = { type: 'object', additionalProperties: false, required: ['archetype', 'title'], properties: {
  archetype: { type: 'string', enum: ['B', 'cite-only'] }, title: { type: 'string' } } }
const CHECK_SCHEMA = { type: 'object', additionalProperties: false, required: ['axis', 'pass', 'findings'], properties: {
  axis: { type: 'string' }, pass: { type: 'boolean' },
  findings: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['severity', 'detail', 'fix'], properties: {
    severity: { type: 'string', enum: ['block', 'warn', 'nit'] }, detail: { type: 'string' }, fix: { type: 'string' } } } } } }
const REVISE_SCHEMA = { type: 'object', additionalProperties: false, required: ['changed', 'summary'], properties: { changed: { type: 'boolean' }, summary: { type: 'string' } } }
const ENRICH_SCHEMA = { type: 'object', additionalProperties: false, required: ['links_added', 'mermaid_added', 'images_added', 'captures_needed'], properties: {
  links_added: { type: 'integer' }, mermaid_added: { type: 'integer' },
  images_added: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['path', 'source', 'license'], properties: { path: { type: 'string' }, source: { type: 'string' }, license: { type: 'string' } } } },
  captures_needed: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['where', 'what'], properties: { where: { type: 'string' }, what: { type: 'string' } } } } } }

// ── PHASE 1: GATE ────────────────────────────────────────────────
phase('Gate')
const gate = await agent(
`출처 게이트를 실행한다. Bash:  python3 ${GATE} ${slug} --wiki ${WIKI}
출력에서 **사실만 추출**해 반환한다 (blocked/mode 판단은 하지 말 것 — 스크립트가 결정한다):
- gate1: 'GATE1 출처:' 라인의 출처 분류를 그대로 — own / third-party(🟥 타사블로그) / reference(🟦 공식문서) / internal(⛔ 사내기밀) / mixed / unstamped(⚠ own-추정·미stamp) / missing(출처불명).
- gate2_hits: 'GATE2 기밀:' 라인의 적중 종수(없으면 0). secret/password 패턴 등 — **종수만 옮기고 판단은 말 것**.
- sources: 각 출처의 {path, provenance}. third-party/reference raw 경로는 표절 대조에 쓰임.
- note: 한 줄 요약.`,
  { label: `gate:${slug}`, phase: 'Gate', schema: GATE_SCHEMA })

if (!gate) { log('⛔ gate 실패'); return { stopped: true, reason: 'gate failed' } }
// mode는 GATE1 출처분류로만 결정(결정론적). GATE2 민감정보는 mode를 막지 않는다 — 다운스트림(백테스트 sensitivity 축 + commit pre-commit 훅)에서 FP 판단.
const mode = gate.gate1 === 'own' ? 'own'
  : (gate.gate1 === 'third-party' || gate.gate1 === 'reference') ? 'cite-only'
  : 'blocked'  // internal · mixed · unstamped · missing
gate.mode = mode
if (mode === 'blocked') {
  log(`⛔ 진행 불가 (GATE1=${gate.gate1}): ${gate.note}`)
  return { stopped: true, reason: `GATE1=${gate.gate1}`, gate }
}
if ((gate.gate2_hits || 0) > 0) log(`⚠ GATE2 민감패턴 ${gate.gate2_hits}종 적중 — 공식 YAML 필드명 등 FP 가능. 백테스트 sensitivity 축 + commit pre-commit 훅에서 판단(게이트 phase는 막지 않음).`)
const thirdParty = (gate.sources || []).filter(s => ['third-party', 'reference'].includes(s.provenance)).map(s => s.path)
log(`Gate 통과: mode=${mode} (GATE1=${gate.gate1}, third-party 출처 ${thirdParty.length}개) — ${gate.note}`)

// ── PHASE 2: DRAFT ───────────────────────────────────────────────
phase('Draft')
const citeRules = gate.mode === 'cite-only'
  ? `mode=cite-only다. 단, **표절 대상은 "저자가 쓴 글"이지 "기술의 사실"이 아니다**(${POLICY} 'cite-only 정량 한계' 필독). (1) 명시적 "정리 노트" 글 — 제목·도입에 정리 글임을 밝힌다. (2) 1인칭 경험 날조 금지 — 출처 저자가 한 일은 3인칭. (3) 출처는 prose 언급/기술명 인라인 링크 + 마지막 참고 자료 섹션에 명시(본문 괄호 (출처:…) 표기 금지). (4) 저자 산문 인용은 출처당 ≤40단어 블록인용. (5) **금지는 저자의 글에만** — 산문·서사·고유 분석·저자가 지어낸 서사형 예제·소제목 구성 통째 답습은 금지(내 흐름으로). **반면 기술의 객관적 사실·공식 스키마/설정 YAML·공식 예제·API·설정키·기본값·동작 순서는 위키에 있는 그대로 충실히 재현하라 — 억지로 "내 예제로 교체"하지 말 것(축약 금지).** (6) 그림은 내 실행 스크린샷만, 없으면 생략.`
  : `mode=own이다. 내 지식·경험으로 작성하되, 모르는 측정값은 \`____\`(실측 placeholder)로 남기고 날조하지 않는다.`
const draft = await agent(
`블로그 초안을 작성한다.
1) ${PROFILE}(quality-profile §1 발행 단위)와 **앵커 위키 페이지(${WIKI}/wiki/sources/${slug}.md)**를 읽고, 그 frontmatter \`sources:\`에 나열된 raw 파일(보통 ${WIKI}/raw/<topic>/${slug}.md)을 충실히 그대로 옮긴다 — 템플릿 타입·설정·기본값·예외·공식 YAML 예제를 임의로 추리거나 추상화하지 말고 빠짐없이. **그 앵커의 raw만 본다 — 형제 페이지(${slug}-advanced 등)나 다른 주제 raw는 끌어오지 않는다(그건 별도 시리즈 편이다).** 위키 요약만 보면 디테일이 빠지니 그 raw를 직접 본다.
2) **공식 문서체로 쓴다**(§3 — 비인칭·선언형): 위키 사실을 AWS·NVIDIA docs처럼 비인칭으로 진술한다. **주어는 기술/대상이지 글쓴이가 아니다.** 금지: 1인칭·개인 감상·깨달음("저는 ~인 줄 알았는데", "오늘 배운 건", "~하려 합니다"), 수사적 대조 후크("X이지 Y가 아니다"·"~가 아니다"), 대화체 연결어("결국"·"사실은"), 메타 프레이밍("~을 정리한 TIL입니다"·"오해를 풀고"), 서사 훅·감정·비유·수사의문, 권고·반성 마무리("~하도록 하자"·"안심하지 않으려 합니다"). **TIL 태그를 붙여도 어조는 일기가 아니라 레퍼런스다.** 1인칭은 cite-only 출처 고지 한 줄로만(중립적으로). 구조는 내용을 따라 자연스러운 헤딩으로 — 템플릿 강제 없음(§2). 구체값은 추상어로 뭉개지 말고 그대로.
2-1) **읽기 쉽게 — 난이도 계단(§2.5)**: 글과 **모든 ## 섹션은 예외 없이** 맨 앞 문단에서 *한 줄 요지 + 무엇을 해결하는가/왜 있는가*를 평이한 선언형으로 연 뒤 세부로 내려간다 — 곧바로 ### 하위섹션이나 표·목록으로 들어가지 않는다(세부·정의·수치를 먼저 던지지 않는다). 모든 쿼터·엣지케이스·내부구현·튜닝값은 뒤 섹션이나 "심화" 표시(접기가 필요하면 <details markdown="1">)로 내린다 — **정보는 다 담되 밀도만 층으로(§1 충실성은 삭제가 아니라 재배치로 유지)**. 처음 쓰는 용어는 괄호로 곧바로 한 줄 정의. 한 문장에 조건·수치를 겹치지 말고 bullet로 편다. **난이도는 구조·정의로만 낮춘다 — 서사·감정·비유·수사의문(§3)으로 낮추지 않는다.** ${citeRules}${tilDraft}
3) quality-profile §1~§9(TIL 모드면 §10 포함)를 적용. Bash로 mkdir -p ${SCRATCH} 후 ${DRAFT}에 Write.
   frontmatter: title/date(+0900)/categories/tags/source_wiki:${slug}/provenance:${gate.mode === 'own' ? 'own' : 'cite-only-draft'}.
   **제목·카테고리·태그는 §9 준수**: 제목은 간결한 '<주제> 정리/비교' 느낌(부제 'A·B·C' 나열·'완벽 가이드'류·40자 초과 금지, PS 글 예외), 카테고리는 .claude/blog-taxonomy.json 트리에서만, 태그는 고유명사 공식표기(Kubernetes·CRD·Argo Workflows)+개념 한글에 기존 표기 재사용(파편화 금지).
   **date 주의**: Bash \`date '+%Y-%m-%d %H:%M:%S +0900'\`로 **현재 시각**을 박는다(절대 미래 시각 금지 — Jekyll production 빌드가 미래 날짜 글을 조용히 제외함).
   실측값은 모르면 \`____\`로(날조 금지). §7.2 S1 AI티(번역투·관용구·접속사·이중피동) 피해서 자연스러운 한국어로.
   **Liquid 안전(필수)**: 본문 코드블록에 \`{{ }}\`(이중 중괄호)나 \`{% %}\` 템플릿 문법(Argo \`{{workflow.parameters.x}}\`·Helm·Vue·Jekyll 등)이 하나라도 있으면, Jekyll Liquid가 빌드 때 그걸 변수로 먹어 빈 값으로 깨뜨린다. 이때 **frontmatter 닫는 \`---\` 다음 줄에 \`{% raw %}\`, 본문 맨 끝에 \`{% endraw %}\`를 넣어 본문 전체를 감싼다**(frontmatter는 밖, raw 태그는 코드펜스 밖 일반 줄에). 단일 \`{ }\`(YAML \`{}\`·mermaid 노드)는 무관.
archetype과 title 반환.`,
  { label: `draft:${slug}`, phase: 'Draft', schema: DRAFT_SCHEMA })
if (!draft) return { stopped: true, reason: 'draft 실패' }
log(`초안 작성: [${draft.archetype}] ${draft.title}`)

// ── PHASE 2.5: ENRICH ────────────────────────────────────────────
phase('Enrich')
const enrich = await agent(
`${DRAFT}를 enrichment한다 (quality-profile §5·§6·§7 + publish-policy '외부 자산'). WebSearch/WebFetch(필요시 ToolSearch로 로드)와 Bash 사용.
1) **공식 문서 인라인 링크**: 본문에 처음 등장하는 오픈소스·라이브러리·기술마다 공식 docs(>공식 GitHub repo>스펙) URL을 WebSearch로 찾아 텍스트 링크 [기술](URL)로 건다. 블로그·StackOverflow는 1차 링크 금지(참고자료 인용으로만). URL은 실제로 열리는지 WebFetch로 확인.
2) **mermaid**: 상태/흐름/계층/시퀀스로 **넣을 만한 자리에만** mermaid 코드블록(\`\`\`mermaid)을 추가. 과용 금지 — 본문으로 충분하면 안 넣음.${gate.mode === 'cite-only' ? ' cite-only: 출처 그림을 베끼지 말고 내 모델로 새로 그린다.' : ''}
2-1) **알림박스(callout)** (quality-profile §5.2 — 선택·과용 금지): 사전지식·전제(NOTE), 곁가지 설명·팁(TIP), 함정·주의(WARNING), 되돌릴 수 없는 작업(DANGER), 꼭 기억할 핵심(IMPORTANT)이 자연스러운 자리엔 \`> [!TYPE] 제목\` blockquote callout으로 살짝 강조한다(타입 NOTE/TIP/WARNING/DANGER/IMPORTANT, 첫 줄 \`[!TYPE] 제목\` + 다음 줄 본문). 글당 소수만, 본문 사실 서술을 옮겨 담지 말고 곁가지 강조에만. 안 넣어도 됨.
3) **이미지**: 라이선스가 명확할 때만(공식 docs 다이어그램·CC·Wikimedia) Bash(curl)로 ${BLOG}/assets/img/${slug}/에 내려받아 ![](/assets/img/${slug}/NN.png) 임베드 + 출처·라이선스 캡션. 불확실하면 넣지 말고 mermaid로 대체.${gate.mode === 'cite-only' ? ' cite-only: 출처 원본 이미지 복제 절대 금지.' : ''}
4) **로컬 캡처 필요 지점**: 내 실행 결과/콘솔/벤치마크 스크린샷이 들어가면 좋은 자리는 만들지 말고 \`<!-- CAPTURE-NEEDED: 설명 -->\` 마커로 표시하고 captures_needed에 수집. 측정 숫자는 \`____\` 유지(날조 금지).
5) **참고 자료 섹션(마지막) — 넘치지 않게 추린다**: 본문에서 *비중 있게 다루거나 근거로 삼은* 출처만 '- 저자/기관, [제목](URL)'로 정리(접근 날짜 없음). **같은 기술은 대표 링크 1~2개로 통합**(같은 docs의 여러 하위페이지를 따로 나열 금지), **가볍게 1회 언급한 곁다리 기술(React·OAuth·gRPC 등)은 인라인 링크만 두고 목록에선 생략**. 라벨은 위키 raw frontmatter(${WIKI}/raw/**)의 domain/author와 일치(추정 라벨 금지). 목록에 넣었으면 본문에서 실제 사용(가짜 인용 금지). **본문에는 '(참고: …)'·'(출처: …)' 괄호 출처 표기 금지 — 출처는 이 섹션에서만(기술명 인라인 링크는 예외).**
수정본을 ${DRAFT}에 다시 Write. 통계 반환.`,
  { label: `enrich:${slug}`, phase: 'Enrich', schema: ENRICH_SCHEMA })
const capturesNeeded = (enrich && enrich.captures_needed) || []
log(`Enrich: 링크 ${enrich ? enrich.links_added : 0} · mermaid ${enrich ? enrich.mermaid_added : 0} · 이미지 ${enrich ? enrich.images_added.length : 0} · 캡처필요 ${capturesNeeded.length}`)

// ── PHASE 2.7: HUMANIZE (Enrich 후 / Backtest 전 — enrich 산문까지 함께 윤문) ──────
phase('Humanize')
const HUMAN_OUT = `${SCRATCH}/humanized.md`
const HUMAN_SCHEMA = { type: 'object', additionalProperties: false, required: ['grade', 'change_rate', 's1_residual'], properties: {
  grade: { type: 'string' }, change_rate: { type: 'number' }, s1_residual: { type: 'integer' } } }
// monolith는 input_path를 Read하고 final.md(+summary.md)를 쓴다. 여기선 출력 경로를 humanized.md로 직접 지정.
const human = await agent(
`너는 humanize-korean monolith 윤문 에이전트다. 한 호출 안에서 탐지·윤문·자체검증을 끝내라.
입력 input_path: ${DRAFT}  (Read)
룰북 quick_rules_path: ${QUICK_RULES}  (Read)
genre_hint: 블로그${TIL ? ' (TIL 노트 — 개조식·터스한 해라체 허용, 합쇼체 강제 금지)' : ''}
출력: 윤문본 + 본문 끝 <!-- HUMANIZE-SUMMARY ... --> 주석 블록을 ${HUMAN_OUT} 에 Write (디폴트 _workspace 경로 대신 이 절대경로).
철칙(위반 시 롤백): 의미 불변(사실·수치·날짜·고유명사·직접인용·영어약어 LLM/JVM/Kafka/API 100% 보존), quick-rules 미매핑 구간 불변, 블로그 장르·합쇼체 register 보존${tilHuman}, 변경률 30% 초과 경고/50% 초과 중단.
**Do-NOT(원형 보존)**: 코드펜스(\`\`\`), mermaid 블록, 인라인 링크 [텍스트](URL), 이미지 ![](...), HTML주석 <!-- CAPTURE-NEEDED -->, frontmatter(---), \`____\` placeholder.
끝나면 자체 SUMMARY의 grade(A~D)·change_rate(%)·S1 잔존 수를 반환.`,
  { label: `humanize:${slug}`, phase: 'Humanize', schema: HUMAN_SCHEMA, agentType: 'humanize-korean:humanize-monolith' })

if (!human) {
  log('⚠ humanize 실패/미해결 — Enrich 산출 draft.md로 진행(Backtest voice 축이 최종 백스톱)')
} else {
  await agent(
`Bash로 humanize 결과를 파이프라인 SSOT인 draft.md로 흡수한다(Backtest 축들은 ${DRAFT}만 읽음).
1) ${HUMAN_OUT}을 읽어 본문 끝 <!-- HUMANIZE-SUMMARY ... --> HTML 주석 블록을 통째 제거.
2) frontmatter(---)·mermaid·인라인 링크·![](...)·\`____\` placeholder·<!-- CAPTURE-NEEDED --> 마커가 윤문 전(${DRAFT})과 비교해 누락되지 않았는지 grep으로 확인(누락 시 그 항목은 원본에서 복원).
3) 정제 본문을 ${DRAFT}에 덮어쓰기. grep으로 HUMANIZE-SUMMARY 0건·\`____\` 보존 확인.
변경 여부+한 줄 요약 반환.`,
    { label: `humanize-merge:${slug}`, phase: 'Humanize', schema: REVISE_SCHEMA })
  log(`Humanize: 등급 ${human.grade} / 변경률 ${human.change_rate}% / S1잔존(자체보고) ${human.s1_residual}`)
}

// 검증 게이트: monolith 자체등급을 믿지 말고 독립적으로 S1을 재탐지 (detector는 quick-rules taxonomy로 재스캔)
const DET_SCHEMA = { type: 'object', additionalProperties: false, required: ['s1_count', 's2_count', 'residual_ids', 'clean'], properties: {
  s1_count: { type: 'integer' }, s2_count: { type: 'integer' }, residual_ids: { type: 'array', items: { type: 'string' } }, clean: { type: 'boolean' } } }
const det = await agent(
`${DRAFT}를 Read하고 ${QUICK_RULES}를 Read한 뒤, 본문 산문에서 **S1 패턴만** 전수 스캔한다(블로그 장르 기준).
대상 S1: 번역투 A(특히 A-7 have/make 직역·A-8 이중피동 "~되어진다"·A-9 "~에 의해" 피동), 관용구 D(D-1 결산피벗·D-3 본질적으로·D-6 결말공식), 접속사 남발 H(H-1 문두접속사 5회+·H-3 메타진입), 형식명사 I-1 "~인 것이다".
**Do-NOT(세지 않음)**: 수치·날짜·고유명사·직접인용(블록인용)·영어약어·코드블록·mermaid·인라인 링크·\`____\`·CAPTURE-NEEDED 주석.
반환: s1_count(S1 잔존 수), s2_count, residual_ids(잔존 finding의 taxonomy ID 배열 예 ["A-8","H-1"]), clean(s1_count===0).`,
  { label: `humanize-verify:${slug}`, phase: 'Humanize', schema: DET_SCHEMA })

if (det && !det.clean) {
  log(`⚠ S1 잔존 ${det.s1_count}건 (${(det.residual_ids || []).join(', ')}) — 1회 타깃 보정`)
  await agent(
`${DRAFT}를 읽고 아래 S1 잔존만 ${QUICK_RULES} 처방대로 제거해 ${DRAFT}에 다시 Write한다.
규칙: 의미·사실·출처·frontmatter·mermaid·링크·\`____\`·CAPTURE-NEEDED 보존, 새 비유/수사 추가 금지, 변경 최소화.
잔존 ID: ${(det.residual_ids || []).join(', ')}`,
    { label: `humanize-fix:${slug}`, phase: 'Humanize', schema: REVISE_SCHEMA })
} else if (det && det.clean) {
  log(`Humanize 검증: S1 잔존 0 (S2 ${det.s2_count}건) — clean`)
}

// ── PHASE 3: BACKTEST LOOP ───────────────────────────────────────
phase('Backtest')
const axes = () => {
  const a = [
    { key: 'quality', p: `${DRAFT}를 읽고 ${PROFILE}(충실 정리체) §8 체크리스트 + §1~§7 conformance를 평가한다. 날조 스크린샷/측정(block), CAPTURE-NEEDED·\`____\` 마커 정상 여부, mermaid 문법, 웹 이미지 출처·라이선스 캡션을 본다.
**충실성·평이함 (warn — 강제 아님, 개선 제안용)**: Bash로 **앵커 raw**(${WIKI}/wiki/sources/${slug}.md의 \`sources:\`에 나열된 raw 파일)와 대조해 다음을 warn(사소하면 nit)으로만 표시한다(block 아님 — 발행을 막지 않는다): (a) 앵커 raw에 있는 사실·구체값·설정·공식 YAML 예제가 초안에서 누락·축약됨(충실성 미달), (b) 공식 YAML을 빈약한 자작 예제로 억지 교체함, (c) "최적화돼 있다·효율적이다" 류 추상어로 구체값을 뭉갬, (d) **§3 비인칭·선언형 위반** — 1인칭·개인 감상·깨달음("저는~", "오늘 배운 건", "~하려 합니다", "~인 줄 알았는데")·수사적 대조 후크("X이지 Y가 아니다")·대화체 연결어("결국"·"사실은")·메타 프레이밍("~을 정리한 TIL입니다"·"오해를 풀고")·서사 훅·감정·비유·수사의문·반성 마무리가 들어감(공식 문서 어조가 아님), (e) 앵커 밖 형제(${slug}-advanced)·다른 주제 raw 내용이 섞임(§1 발행 단위 위반 — 시리즈로 분리 권장), (f) **§2.5 난이도 계단 미흡** — 글·큰 섹션이 핵심(요지+왜) 없이 바로 세부로 들어가거나, 쿼터·엣지케이스·튜닝값이 핵심과 평평하게 섞여 밀도가 높거나, 처음 쓴 용어에 정의가 없어 난도가 높음(정보를 빼라는 게 아니라 핵심 먼저·심화 뒤로 재배치·용어 정의 제안). 이들은 개선 제안이며 최종 판단은 사용자 몫 — block 안 냄(warn/nit만).${tilQuality}` },
    { key: 'tone', p: `**결정론적 톤 게이트(§3 공식 문서체 — 거부된 오글 톤의 결정론적 백스톱).** Bash로 \`python3 ${BLOG}/.claude/tone-lint.py --json ${DRAFT}\`를 실행한다. 출력 JSON의 \`block\` 배열 각 항목을 그대로 severity=block finding으로 옮긴다(detail=\`label\`+\`context\`, fix="해당 §3 패턴을 평서·비인칭으로 제거 — 1인칭·수사적 대조 후크·TIL 일기체·반성 마무리 삭제"). \`block\`이 비면 pass=true(warn은 참고로만). **네 문체 판단을 넣지 말고 스크립트의 block 출력만 전사한다** — 이 축은 LLM 품질 리뷰가 확률적으로 놓치는 거부 패턴(콜아웃 제목의 'X이지 Y가 아니다' 등)을 literal로 잡는 백스톱이다. 광범위한 문체는 quality 축이 warn으로 다룬다.` },
    { key: 'sensitivity', p: `Bash:  python3 ${GATE} ${DRAFT} --wiki ${WIKI}  를 실행하고 'GATE2 기밀' 라인을 본다. 회사명·내부 제품/코드명·티켓ID·시크릿·PII가 1건이라도 있으면 block + 해당 단어.` },
    { key: 'voice', p: `${DRAFT}가 자연스러운 한국어(합쇼체 본문·한 문단 한 생각·짧고 능동·영어용어 보존+첫등장 병기)인지 평가. AI/번역투 문장, 노트모드(한 문장 한 줄), 어색한 리듬은 finding. §7.2 S1 잔존은 block. (서사·감정·1인칭 무용담은 §3 위반 → quality 축 warn에서 다룸. voice 축은 한국어 자연스러움만 본다.)
**정량 신호(참고용·한국어 유창성만)**: Bash로 \`python3 ${BLOG}/.claude/voice-similarity.py score ${DRAFT}\` 실행해 문체 점수를 얻는다(골든=합쇼체 산문+공식문서체 발행글, baseline≈75, accept_low≈70). 이 점수는 **한국어 유창성**만 본다 — 톤 feature(1인칭·들어가며/마치며·결국)는 제거됨. **톤·포맷은 §3(비인칭)·§2(구조)가 SSOT**다. off-voice가 나와도 **톤을 1인칭·서사 쪽으로 되돌리지 말 것**(그건 거부된 톤). own 글이 크게 off-voice면 한국어 유창성 점검용 warn으로만 기록.${tilVoice}` },
    { key: 'facts', p: `적대적 사실검증: ${DRAFT}의 모든 기술 주장을 위키 페이지(${WIKI}/wiki/**/${slug}.md)와 raw 출처(${WIKI}/raw/**)에 대조. 출처에 없는 주장·과장·날조 수치는 block(환각 방지).${gate.mode === 'cite-only' ? ' 1인칭 경험 날조("제가 겪었습니다")는 block.' : ''}` },
    { key: 'references', p: `${DRAFT}의 §6 인용 규율을 검사한다(Bash로 ${WIKI}/raw/** frontmatter 대조 가능): (1) 본문 처음 등장 기술마다 공식 docs 인라인 링크가 있는가(없으면 warn). (2) 참고 자료 섹션이 **넘치지 않는가** — 같은 기술의 중복 엔트리(같은 docs 하위페이지 여러 개)나 가벼운 1회 언급 곁다리 출처(React·OAuth 등)가 과하게 나열됐으면 warn(대표 링크로 통합·정리 제안). 비중 있게 근거로 쓴 출처가 목록에서 누락됐으면 warn. (3) 참고자료에만 있고 본문 미인용인 URL → block(가짜 인용). (4) **출처 라벨(블로그명·저자)이 raw frontmatter의 domain/author와 일치하는가 — 추정·날조 라벨은 block**(예: raw에 author 없는데 '알쓸개잡'으로 단 것). (5) 블로그·SO가 1차 인라인 링크로 걸렸으면 warn(공식 docs로 교체 권장). (6) 깨진 링크 warn. (7) 본문에 '(참고: …)'·'(출처: …)' 식 괄호 출처 표기가 있으면 warn(마지막 참고 자료 섹션으로 옮기라고 제안 — 기술명 인라인 링크는 예외).${tilRefs}` },
  ]
  if (thirdParty.length) a.push({ key: 'plagiarism', p: `표절 검사. 각 third-party 출처에 대해 Bash:  python3 ${GATE} --overlap ${DRAFT} ${WIKI}/<src>  (각 src를 ${WIKI}/ 절대경로로). 8-gram 겹침>15% 또는 연속>25단어면 block + 위반 span. 출처: ${thirdParty.join(', ')}` })
  return a
}

let round = 0, clean = false
while (round < ROUNDS && !clean) {
  round++
  log(`백테스트 라운드 ${round}/${ROUNDS}`)
  const checks = (await parallel(axes().map(ax => () =>
    agent(`${ax.p}\n\naxis="${ax.key}"로 CHECK_SCHEMA 반환.`, { label: `check:${ax.key}:r${round}`, phase: 'Backtest', schema: CHECK_SCHEMA })
  ))).filter(Boolean)
  const blocking = checks.flatMap(c => (c.findings || []).filter(f => f.severity === 'block').map(f => ({ axis: c.axis, ...f })))
  log(`라운드 ${round}: block ${blocking.length}건 (axis별 pass: ${checks.map(c => `${c.axis}=${c.pass ? 'O' : 'X'}`).join(' ')})`)
  if (blocking.length === 0) { clean = true; break }
  if (round >= ROUNDS) break
  const rev = await agent(
`${DRAFT}를 읽고 아래 blocking findings를 모두 수정해 ${DRAFT}에 다시 Write한다. 규칙: 내용·사실·출처 보존, quality-profile·publish-policy 준수, §7.2 S1 AI티·§3 서사/감정 늘리지 말 것. 표절 finding은 내 표현으로 재작성하거나 ≤40단어 블록인용+출처로. 사실 finding은 출처 없는 주장 삭제.
FINDINGS:
${blocking.map((f, i) => `${i + 1}. [${f.axis}/${f.severity}] ${f.detail} → ${f.fix}`).join('\n')}`,
    { label: `revise:r${round}`, phase: 'Backtest', schema: REVISE_SCHEMA })
  log(`라운드 ${round} 수정: ${rev ? rev.summary : '(실패)'}`)
}

// ── PHASE 4: REPORT ──────────────────────────────────────────────
phase('Report')
await agent(
`${DRAFT}와 백테스트 결과를 종합해 ${SCRATCH}/report.md에 Write(Bash mkdir -p 보장). 내용: axis별 통과(품질·표절·기밀·보이스·사실·인용), 남은 warn/nit, 라운드 ${round}, clean=${clean}, mode=${gate.mode}, enrich(링크 ${enrich ? enrich.links_added : 0}·mermaid ${enrich ? enrich.mermaid_added : 0}·이미지 ${enrich ? enrich.images_added.length : 0}).
**사용자 캡처 필요 지점** ${capturesNeeded.length}건을 목록으로 적는다: ${JSON.stringify(capturesNeeded)}.
다음 액션: 사람이 초안 검토 → (캡처 필요 지점은 직접 첨부 또는 제거 결정) → _posts/로 이동 → commit(pre-commit hook이 기밀 게이트 재실행). **절대 _posts/에 직접 쓰지 않는다**.`,
  { label: `report:${slug}`, phase: 'Report' })

// ── FREEZE: 에이전트 초안 D를 edit-history에 영구 보관 (.pipeline은 휘발 — 수정-학습 루프의 D 원천) ──
const EH = `${BLOG}/.claude/edit-history/${slug}`
await agent(
`Bash로 에이전트 초안을 수정-학습용으로 동결한다(발행 후 사람 수정본 F와 짝지어 학습).
  mkdir -p ${EH}
  cp ${DRAFT} ${EH}/draft.md
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ); sha=$(git -C ${BLOG} hash-object ${DRAFT} 2>/dev/null || md5 -q ${DRAFT})
그 뒤 ${EH}/meta.json 에 JSON Write(이미 있으면 덮어쓰기):
  {"slug":"${slug}","archetype":"${draft.archetype}","mode":"${gate.mode}","title":${JSON.stringify(draft.title)},"frozen_at":"<now>","draft_sha":"<sha>","source_wiki":"${slug}","published_path":null,"paired_at":null,"state":"frozen"}
초안 frontmatter에 source_wiki:${slug}가 있으니, 발행 시 파일명을 바꿔도 pre-commit 훅이 그 값으로 역매칭한다.
한 줄 요약 반환.`,
  { label: `freeze:${slug}`, phase: 'Report' })

return { slug, mode: gate.mode, archetype: draft.archetype, title: draft.title, rounds: round, clean, captures_needed: capturesNeeded, draft: DRAFT, report: `${SCRATCH}/report.md` }
