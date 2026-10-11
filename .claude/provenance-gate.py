#!/usr/bin/env python3
"""블로그 발행 게이트 — 출처 적격성(Gate1) + 표절 중복(Gate1b) + 민감정보(Gate2).

원칙: **fail-CLOSED**. 명시적 `provenance: own` + 출처 확인까지 통과해야만 발행 가능(녹색).
  - 명시 stamp 없음 → 무엇이든 검토 보류(추정 own도 발행 불가).
  - 명시 stamp 있어도 sources가 더 엄격하면 downgrade(stale stamp 방어).
  - own은 모든 출처가 own일 때만. 하나라도 비-own이면 그 등급으로 상향.
  - wiki→wiki / [[wikilink]] 출처는 전이적으로 추적(synthesis laundering 방어).
  - Confluence/.atlassian.net·sdd·k8s YAML → internal.

사용법:
  provenance-gate.py [--wiki ~/dev/llm-wiki]              # 전체 분류
  provenance-gate.py <slug|path>                          # 단일 페이지 Gate1+Gate2
  provenance-gate.py --overlap <draft.md> <source.md>     # Gate1b 표절 중복 검사
"""
import os, re, sys, glob, argparse

REF_DOMAINS = ['spring.io','kubernetes.io','k8s.io','apache.org','redis.io','mongodb.com',
   'amazon.com','aws.','google.com','microsoft.com','mozilla.org','ietf.org','wikipedia.org',
   'openjdk','graalvm.org','prometheus.io','grafana.com','argoproj','keda.sh','karpenter.sh',
   'hibernate.org','postgresql.org','docs.']
# 등급 심각도 (max를 취해 더 엄격한 쪽 채택)
SEV = {'own':0, 'reference':1, 'mixed':2, 'unknown':2, 'review':2, 'NO-SOURCES':2, 'third-party':3, 'internal':4}
LABEL = {'own':'✅ 발행후보(내것)', 'reference':'🟦 공식문서(cite-only)', 'mixed':'⚠ 혼합(검토)',
         'unknown':'⚠ 출처불명(검토)', 'NO-SOURCES':'⚠ NO-SOURCES(검토)',
         'third-party':'⛔ 타사블로그(cite-only)', 'internal':'⛔ 사내기밀'}
ORDER = ['✅ 발행후보(내것)','⚠ own-추정(미stamp·검토)','🟦 공식문서(cite-only)','⚠ 혼합(검토)',
         '⚠ 출처불명(검토)','⚠ NO-SOURCES(검토)','⛔ 타사블로그(cite-only)','⛔ 사내기밀']
# Gate1b 임계 (publish-policy.md '정량 한계'와 동일하게 유지)
MAX_VERBATIM_RUN = 25      # 인용부호 밖 연속 동일 단어
MAX_SHINGLE_OVERLAP = 0.15 # draft 8-gram 중 source와 겹치는 비율

def stricter(a, b): return a if SEV.get(a, 2) >= SEV.get(b, 2) else b

def raw_front(path):
    try: txt = open(path, encoding='utf-8', errors='ignore').read(3000)
    except OSError: return None
    fm = {}
    for k in ['source_url', 'domain', 'clipped_at', 'url', 'source']:
        m = re.search(r'^%s:\s*"?([^"\n]*)"?' % k, txt, re.M)
        if m and m.group(1).strip(): fm[k] = m.group(1).strip()
    fm['clipped'] = ('clipped_at' in fm) or ('"clipped"' in txt) or bool(re.search(r'^\s*-\s*clipped\s*$', txt, re.M))
    fm['yaml_resource'] = bool(re.search(r'^(spec|kind):', txt, re.M))
    return fm

def classify_raw(path):
    if path.startswith('sdd/') or '/sdd/' in path: return 'internal'   # 사내 SDD 경로 (확실)
    fm = raw_front(path)
    if fm is None: return 'MISSING'
    u = (fm.get('source_url') or fm.get('url') or '').lower()
    dom = (fm.get('domain') or u).lower()
    # 외부 클립이 확실하면(clip 마커 또는 외부 도메인) 도메인으로 먼저 분류한다.
    # 공식 문서의 `kind:`/`spec:` YAML 예제(예: Argo Workflow)를 사내 매니페스트로 오판하지 않도록
    # yaml_resource 휴리스틱보다 우선. (2026-06 argo-workflows 오탐 수정)
    if fm['clipped'] or dom:
        if fm.get('source', '').lower() == 'confluence' or '.atlassian.net' in u: return 'internal'  # 사내 위키
        if any(r in dom for r in REF_DOMAINS): return 'reference'
        return 'third-party'
    # 클립 마커 없는 로컬 파일에만 사내 k8s 매니페스트 휴리스틱 적용
    if fm['yaml_resource']: return 'internal'   # 로컬 spec:/kind: = 사내 인프라
    return 'own'

def explicit_provenance(path):
    try: txt = open(path, encoding='utf-8', errors='ignore').read(1500)
    except OSError: return None
    m = re.search(r'^provenance:\s*"?([a-z-]+)"?\s*$', txt, re.M)
    v = m.group(1).strip() if m else None
    return v if v in ('own', 'third-party', 'reference', 'internal', 'mixed') else None

def page_sources(path):
    txt = open(path, encoding='utf-8', errors='ignore').read()
    m = re.search(r'\nsources:\s*\n((?:[ \t]*-[ \t]*\S.*\n)+)', txt)
    out = []
    if m:
        for l in m.group(1).splitlines():
            s = re.sub(r'^[ \t]*-[ \t]*', '', l).split('#')[0].strip()
            if s: out.append(s)
    return out

def find_wiki_page(ref, wiki):
    ref = ref.strip().strip('[]')
    base = os.path.basename(ref)
    if not base.endswith('.md'): base += '.md'
    if ref.startswith('wiki/'):
        p = os.path.join(wiki, ref if ref.endswith('.md') else ref + '.md')
        if os.path.exists(p): return p
    hits = glob.glob(os.path.join(wiki, 'wiki/**', base), recursive=True)
    return hits[0] if hits else None

def resolve_source(src, wiki, depth, seen):
    src = src.strip()
    if src.startswith('sdd/') or '/sdd/' in src: return 'internal'
    if src.startswith('[[') or src.startswith('wiki/'):           # 전이적 wiki→wiki
        p = find_wiki_page(src, wiki)
        return classify_core(p, wiki, depth + 1, seen) if p else 'unknown'
    for c in ({src, 'raw/' + src if not src.startswith('raw/') else src}):
        p = os.path.join(wiki, c)
        if os.path.exists(p): return classify_raw(p)
    hits = glob.glob(os.path.join(wiki, 'raw/**', os.path.basename(src)), recursive=True)
    return classify_raw(hits[0]) if hits else 'MISSING'

def sources_class(path, wiki, depth, seen):
    srcs = page_sources(path)
    if not srcs: return 'NO-SOURCES'
    classes = [resolve_source(s, wiki, depth, seen) for s in srcs]
    classes = [('unknown' if c == 'MISSING' else c) for c in classes]
    return max(classes, key=lambda c: SEV.get(c, 2))   # 가장 엄격한 출처 채택

def classify_core(path, wiki, depth=0, seen=None):
    """페이지의 provenance CLASS. 명시 stamp는 sources와 cross-check해 더 엄격한 쪽으로."""
    if seen is None: seen = set()
    if not path or path in seen or depth > 4: return 'unknown'
    seen.add(path)
    explicit = explicit_provenance(path)
    sc = sources_class(path, wiki, depth, seen)
    if explicit:
        return explicit if sc == 'NO-SOURCES' else stricter(explicit, sc)
    return 'unknown' if sc == 'NO-SOURCES' else sc

def classify_page(path, wiki):
    """발행 판정. 녹색(publishable)은 명시 own + 출처도 own일 때만 (fail-closed)."""
    explicit = explicit_provenance(path)
    core = classify_core(path, wiki)
    srcs = page_sources(path)
    detail = [(resolve_source(s, wiki, 1, set()), s) for s in srcs] or [('(no sources)', '')]
    if explicit:
        how = f"provenance: {explicit} (명시)"
        if core != explicit: how += f"  ⚠ stamp '{explicit}'보다 출처가 엄격 → '{core}'로 downgrade"
        publishable = (explicit == 'own' and core == 'own')
        label = LABEL.get(core, '⚠ 검토')
    else:
        how = "provenance 미stamp → sources 추정 (fail-closed)"
        if core == 'own':
            label, publishable = '⚠ own-추정(미stamp·검토)', False   # 추정 own은 발행 불가
        else:
            label, publishable = LABEL.get(core, '⚠ 검토'), False
    return label, how, detail, publishable

# ---------- Gate1b: 표절 중복 ----------
def words(text):
    text = re.sub(r'```.*?```', ' ', text, flags=re.S)        # 코드블록 제외
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)
    return re.findall(r'[0-9A-Za-z가-힣]+', text)

def overlap(draft_text, source_text):
    d, s = words(draft_text), words(source_text)
    sset8 = set(tuple(s[i:i+8]) for i in range(len(s) - 7))
    dsh = [tuple(d[i:i+8]) for i in range(len(d) - 7)]
    shingle = (sum(1 for g in dsh if g in sset8) / len(dsh)) if dsh else 0.0
    # 최장 연속 동일 run
    sset_pos = {}
    for i, w in enumerate(s): sset_pos.setdefault(w, []).append(i)
    best = 0
    for i in range(len(d)):
        for j in sset_pos.get(d[i], []):
            k = 0
            while i + k < len(d) and j + k < len(s) and d[i+k] == s[j+k]: k += 1
            best = max(best, k)
    return shingle, best

# ---------- Gate2: 민감정보 ----------
def load_deny(path):
    pats = []
    if not path or not os.path.exists(path):
        # fail-closed: 차단 목록이 없으면(위키 미설치·끊긴 링크) 통과가 아니라 차단. pre-commit 훅이 stdout의 이 문구로 막는다.
        print(f"GATE2 기밀: ⛔ deny-list 파일 없음 ({path}) — ~/dev/llm-wiki 를 받은 뒤 다시 실행")
        print("\nVERDICT: ⛔ 발행 보류 (deny-list 없음)")
        sys.exit(1)
    for line in open(path, encoding='utf-8'):
        line = line.split('#')[0].strip() if not line.strip().startswith('#') else ''
        if not line: continue
        pats.append(('re', line[6:].strip()) if line.startswith('regex:') else ('word', line))
    return pats

def scan_sensitive(text, deny):
    hits = []
    for kind, pat in deny:
        try: rx = re.compile(pat if kind == 're' else r'\b' + re.escape(pat) + r'\b', re.I)
        except re.error: continue
        if rx.findall(text): hits.append((pat, len(rx.findall(text))))
    return hits

def backfill_write(path, value):
    """frontmatter에 provenance: value 삽입 (confidence: 다음, 없으면 닫는 --- 앞). 이미 있으면 skip."""
    txt = open(path, encoding='utf-8', errors='ignore').read()
    lines = txt.split('\n')
    if not lines or lines[0].strip() != '---': return False
    try: end = next(i for i in range(1, len(lines)) if lines[i].strip() == '---')
    except StopIteration: return False
    if any(l.startswith('provenance:') for l in lines[1:end]): return False
    at = end
    for i in range(1, end):
        if lines[i].startswith('confidence:'): at = i + 1
    lines.insert(at, f'provenance: {value}')
    open(path, 'w', encoding='utf-8').write('\n'.join(lines))
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('page', nargs='?')
    ap.add_argument('extra', nargs='?')
    ap.add_argument('--wiki', default=os.path.expanduser('~/dev/llm-wiki'))
    ap.add_argument('--deny', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blog-sensitive-terms.txt'))
    ap.add_argument('--overlap', nargs=2, metavar=('DRAFT', 'SOURCE'))
    ap.add_argument('--backfill', action='store_true', help='미stamp 페이지에 provenance 추정값 기록 (own은 제외)')
    ap.add_argument('--write', action='store_true', help='--backfill을 실제로 파일에 기록 (없으면 dry-run)')
    a = ap.parse_args()
    wiki = os.path.expanduser(a.wiki)

    if a.overlap:
        dt = open(a.overlap[0], encoding='utf-8', errors='ignore').read()
        st = open(a.overlap[1], encoding='utf-8', errors='ignore').read()
        sh, run = overlap(dt, st)
        bad = sh > MAX_SHINGLE_OVERLAP or run > MAX_VERBATIM_RUN
        print(f"Gate1b 표절 중복: 8-gram 겹침 {sh:.1%} (한계 {MAX_SHINGLE_OVERLAP:.0%}) · 최장 연속 {run}단어 (한계 {MAX_VERBATIM_RUN})")
        print('VERDICT:', '⛔ 표절 의심 — 재작성 필요' if bad else '✅ 통과')
        sys.exit(1 if bad else 0)

    if a.backfill:
        from collections import Counter
        AUTO = {'third-party', 'reference', 'internal', 'mixed'}
        deny = load_deny(a.deny)
        cnt = Counter(); own = []; review = []; wrote = 0
        for f in sorted(glob.glob(os.path.join(wiki, 'wiki/**/*.md'), recursive=True)):
            rel = os.path.relpath(f, os.path.join(wiki, 'wiki'))
            if explicit_provenance(f): cnt['이미stamp'] += 1; continue
            core = classify_core(f, wiki)
            if core in AUTO:
                cnt[core] += 1
                if a.write and backfill_write(f, core): wrote += 1
            elif core == 'own':
                hits = scan_sensitive(open(f, encoding='utf-8', errors='ignore').read(), deny)
                own.append((rel, len(hits))); cnt['own-후보(미stamp)'] += 1
            else:
                review.append(rel); cnt['검토-미stamp'] += 1
        print('# Backfill', '(WRITE)' if a.write else '(dry-run)')
        for k, v in cnt.most_common(): print(f'  {k}: {v}')
        if a.write: print(f'  → 자동 stamp 기록: {wrote}건 (third-party/reference/internal/mixed)')
        print(f'\n## own-후보 {len(own)}건 — 자동 stamp 안 함. 사용자가 own 확정해야 함 (⚠N = 기밀 deny-list N건 적중):')
        for rel, h in own: print(f'  {"⚠" + str(h) if h else "   "} {rel}')
        if review:
            print(f'\n## 검토 필요(출처불명/혼합) {len(review)}건:')
            for rel in review: print(f'   {rel}')
        if not a.write: print('\n실제 기록: provenance-gate.py --backfill --write   (own-후보·검토는 제외, 비-own만 기록)')
        return

    if not a.page:
        from collections import defaultdict
        buckets, explicit_n = defaultdict(list), 0
        for f in sorted(glob.glob(os.path.join(wiki, 'wiki/**/*.md'), recursive=True)):
            label, how, _, _ = classify_page(f, wiki)
            if '명시' in how: explicit_n += 1
            buckets[label].append(os.path.relpath(f, os.path.join(wiki, 'wiki')))
        total = sum(len(x) for x in buckets.values())
        print(f"# provenance 명시 {explicit_n}/{total} (나머지 fail-closed 검토 — backfill 필요)")
        for v in ORDER + [k for k in buckets if k not in ORDER]:
            items = buckets.get(v, [])
            if items: print(f"\n## {v} — {len(items)}건")
            for n in items[:30]: print("  ", n)
            if len(items) > 30: print(f"   ... +{len(items)-30}")
        return

    cand = a.page if os.path.exists(a.page) else find_wiki_page(a.page, wiki)
    if not cand: sys.exit(f"page not found: {a.page}")
    label, how, detail, publishable = classify_page(cand, wiki)
    print(f"PAGE: {cand}")
    print(f"GATE1 출처: {label}   [{how}]")
    for p, s in detail: print(f"   - {p:12s} {s}")
    deny = load_deny(a.deny)
    _raw = open(cand, encoding='utf-8', errors='ignore').read()
    # 위키 페이지의 Connections/Open Questions(내부 페이지로의 [[wikilink]] 상호참조)는 발행될 본문이 아니므로
    # Gate2(기밀)에서 제외하고 발행 본문만 스캔한다. 초안(_posts)엔 이 헤딩이 없어 전체 스캔과 동일.
    # 진짜 유출 방어는 초안 단계 Gate2(백테스트)·pre-commit 훅이 _posts 본문 전체를 스캔해 담당.
    _body = re.split(r'(?m)^#{1,4}\s*(Connections|Open Questions|연결|열린\s*질문|관련 글)\b', _raw)[0]
    hits = scan_sensitive(_body, deny)
    print(f"GATE2 기밀: {'⛔ ' + str(len(hits)) + '종 발견' if hits else '✅ 0건'}")
    for pat, n in hits: print(f"   - {pat}  ×{n}")
    blocked = (not publishable) or bool(hits)
    print(f"\nVERDICT: {'⛔ 발행 보류 (사람 확인 필요)' if blocked else '✅ 통과'}")
    if not publishable and 'cite-only' in label:
        print("  → 이 주제로 직접 정리한 글 + 원글 인용/참고는 가능. 원문 재사용·경험 날조 금지. (publish-policy Gate1)")
    sys.exit(1 if blocked else 0)

if __name__ == '__main__':
    main()
