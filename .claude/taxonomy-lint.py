#!/usr/bin/env python3
"""taxonomy-lint.py — 발행된 블로그 전체(_posts/)의 제목·카테고리·태그 정합성 검사. 표준 라이브러리 전용.

.claude/blog-taxonomy.json(SSOT)을 기준으로 코퍼스 전체를 훑어 다음을 잡는다:
- 태그 파편화: 같은 의미인데 표기만 다른 태그(argo-workflows ↔ Argo Workflows, crd ↔ CRD, kubernetes ↔ Kubernetes).
  → 태그를 정규화(소문자·공백/하이픈/· 제거)해 한 정규형에 표기가 2개 이상이면 파편화.
- alias 위반: SSOT tag_aliases에 정답 표기가 정의된 태그가 다른 표기로 쓰임.
- 태그 스타일: 고유명사인데 소문자/kebab(docker → Docker), 개념인데 영문 등. 정책 = 고유명사 공식표기 + 개념 한글.
- 카테고리: SSOT 카테고리 트리에 없는 값.
- 제목: 개념·학습 정리 글 제목이 장황하거나 'AI가 쓴' 티(완벽 가이드·총정리 등). PS(백준/프로그래머스) 글은 제외.

파편화는 본질적으로 코퍼스 전체를 봐야 검출되므로 기본 대상은 _posts/ 전체다.

사용:
  taxonomy-lint.py                 # _posts/ 전체 검사. block 있으면 exit 1
  taxonomy-lint.py --json          # 결과 JSON(파이프라인/도구용)
  taxonomy-lint.py --post <slug>   # 특정 글에 대한 finding만 출력(파편화는 전체 코퍼스 기준)
  taxonomy-lint.py --fix           # 태그를 정답 표기로 일괄 치환(제목·카테고리는 사람이 수정)
"""
import re, sys, json, os, glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
POSTS_DIR = os.path.join(REPO_ROOT, '_posts')
SSOT_PATH = os.path.join(SCRIPT_DIR, 'blog-taxonomy.json')


def load_ssot():
    with open(SSOT_PATH, encoding='utf-8') as f:
        return json.load(f)


def norm(tag):
    """태그 정규형: 소문자 + 공백·하이픈·언더스코어·가운뎃점·마침표 제거. 'Spring Boot'·'spring-boot'·'springboot' → 'springboot'."""
    return re.sub(r'[\s\-_·./]', '', str(tag)).lower()


def has_hangul(s):
    return bool(re.search(r'[가-힣]', s))


def parse_inline_list(val):
    val = val.strip()
    if val.startswith('['):
        inner = val[1:val.rfind(']')] if ']' in val else val[1:]
        return [x.strip().strip('"\'') for x in inner.split(',') if x.strip()]
    return []


def parse_frontmatter(text):
    """frontmatter에서 title(str)·categories(list)·tags(list) 추출. inline [..] · block(- item) 둘 다 지원."""
    m = re.match(r'^---\n(.*?)\n---', text, re.S)
    if not m:
        return None
    out = {'title': None, 'categories': [], 'tags': []}
    block = None
    for line in m.group(1).splitlines():
        ml = re.match(r'^(title|categories|category|tags|tag):\s*(.*)$', line)
        if ml:
            key, val = ml.group(1), ml.group(2)
            block = None
            if key == 'title':
                out['title'] = val.strip().strip('"\'')
                continue
            tgt = 'categories' if key.startswith('categor') else 'tags'
            items = parse_inline_list(val)
            if items:
                out[tgt].extend(items)
            elif val.strip() in ('', '|', '>', '[]'):
                block = tgt
            continue
        bl = re.match(r'^\s*-\s+(.*)$', line)
        if bl and block:
            out[block].append(bl.group(1).strip().strip('"\''))
        elif re.match(r'^\S', line):
            block = None
    return out


def load_corpus():
    posts = []
    for path in sorted(glob.glob(os.path.join(POSTS_DIR, '*.md'))):
        try:
            fm = parse_frontmatter(open(path, encoding='utf-8').read())
        except Exception:
            fm = None
        if fm:
            fm['path'] = path
            fm['slug'] = os.path.basename(path)
            posts.append(fm)
    return posts


def build_maps(ssot):
    alias_by_norm, proper_by_norm = {}, {}
    for k, v in ssot['tag_aliases'].items():
        alias_by_norm[norm(k)] = v
    for p in ssot['proper_nouns']:
        proper_by_norm[norm(p)] = p
        alias_by_norm.setdefault(norm(p), p)          # 고유명사는 그 자체가 정답
    for v in set(ssot['tag_aliases'].values()):
        alias_by_norm.setdefault(norm(v), v)          # canonical은 자기 자신으로
    lc_ok = {norm(x) for x in ssot['lowercase_ok']}
    return alias_by_norm, proper_by_norm, lc_ok


def pick_canonical(forms, freq, proper_by_norm):
    """파편화 클러스터에서 정답 후보 선택: 고유명사목록 > 대문자 포함 > 최다 사용."""
    return sorted(forms, key=lambda f: (norm(f) in proper_by_norm, any(c.isupper() for c in f), freq.get(f, 0)), reverse=True)[0]


def is_ps(post, ssot):
    ps = set(ssot['ps_categories'])
    if any(c in ps for c in post['categories']):
        return True
    return bool(re.match(r'^\s*\[(BOJ|백준|프로그래머스|Programmers)', post.get('title') or '', re.I))


def lint(posts, ssot, only_slug=None):
    alias_by_norm, proper_by_norm, lc_ok = build_maps(ssot)
    sev = ssot['severity']
    findings = []

    def add(code, severity, post, label, context, fix):
        findings.append({'code': code, 'severity': severity,
                         'post': post['slug'] if post else '(corpus)',
                         'label': label, 'context': context, 'fix': fix})

    def want(post):
        return only_slug is None or (post and only_slug in post['slug'])

    # ── 코퍼스 전역: 파편화(정규형당 표기 2+개) ────────────────────
    surface_freq, surface_posts, norm_forms = {}, {}, {}
    for p in posts:
        for t in p['tags']:
            surface_freq[t] = surface_freq.get(t, 0) + 1
            surface_posts.setdefault(t, []).append(p['slug'])
            norm_forms.setdefault(norm(t), set()).add(t)

    frag_canonical = {}
    for n, forms in norm_forms.items():
        if len(forms) < 2:
            continue
        if n in alias_by_norm:
            continue  # alias 검사가 정답 표기로 강제하므로 중복 회피
        canon = pick_canonical(forms, surface_freq, proper_by_norm)
        frag_canonical[n] = canon
        others = sorted(f for f in forms if f != canon)
        involved = [p for p in posts if any(norm(t) == n for t in p['tags'])]
        for p in involved:
            bad = [t for t in p['tags'] if norm(t) == n and t != canon]
            if bad and want(p):
                add('fragmentation', sev['fragmentation'], p,
                    f"파편화된 태그: {', '.join(sorted(forms))}",
                    f"{p['slug']} 에서 {', '.join(bad)}",
                    f"'{canon}' 로 통일 (다른 표기: {', '.join(others)})")

    # ── 글별: alias · 태그 스타일 · 카테고리 · 제목 ────────────────
    for p in posts:
        # tags: alias 위반 + 스타일
        for t in p['tags']:
            n = norm(t)
            if n in alias_by_norm and alias_by_norm[n] != t:
                if want(p):
                    add('alias', sev['alias'], p,
                        f"태그 표기 불일치: '{t}'",
                        f"{p['slug']}",
                        f"'{alias_by_norm[n]}' 로 (SSOT 정답 표기)")
                continue
            # 스타일: 소문자/kebab 영문 태그(공식 소문자 식별자·한글 제외)
            if (re.match(r'^[a-z0-9][a-z0-9-]*$', t) and not has_hangul(t)
                    and n not in lc_ok and n not in alias_by_norm and re.search(r'[a-z]', t)):
                if want(p):
                    add('tag-style', sev['tag_style'], p,
                        f"태그 스타일: '{t}' (소문자/kebab 영문)",
                        f"{p['slug']}",
                        "고유명사면 공식 표기(예: Docker·Kubernetes), 일반 개념이면 한글로. 확정되면 SSOT tag_aliases에 등록")

        # categories: 트리 검증
        cats = p['categories']
        tree = ssot['categories']
        if cats:
            parent = cats[0]
            if parent not in tree:
                if want(p):
                    add('category', sev['unknown_category'], p,
                        f"카테고리 트리에 없는 값: '{parent}'",
                        f"{p['slug']} categories={cats}",
                        f"SSOT categories 트리에서 선택({', '.join(tree.keys())}) 또는 트리에 추가")
            else:
                for child in cats[1:]:
                    if child not in tree[parent]:
                        if want(p):
                            allowed = ', '.join(tree[parent]) or '(하위 없음)'
                            add('category', sev['category_structure'], p,
                                f"'{parent}' 하위에 없는 카테고리: '{child}'",
                                f"{p['slug']} categories={cats}",
                                f"'{parent}' 허용 하위: {allowed}")

        # title: PS 글 제외
        if is_ps(p, ssot) or not p.get('title'):
            continue
        if not want(p):
            continue
        title, tcfg = p['title'], ssot['title']
        hit = [b for b in tcfg['banned'] if b in title]
        if hit:
            add('title', sev['title'], p,
                f"제목에 장황·AI 티 표현: {', '.join(hit)}",
                f"{p['slug']}: \"{title}\"",
                "간결하게 직접 쓴 느낌으로 — 예: '<주제> 정리' / '<주제> 비교'")
        elif re.search(r':\s*[^:]*·', title):
            add('title', sev['title'], p,
                "부제 나열형 제목 ('…: A·B·C') — AI 티",
                f"{p['slug']}: \"{title}\"",
                "부제 나열을 빼고 '<주제> 정리 / 비교'처럼 직접 쓴 느낌으로")
        elif len(title) > tcfg['max_len']:
            add('title', sev['title'], p,
                f"제목이 {len(title)}자 (>{tcfg['max_len']})",
                f"{p['slug']}: \"{title}\"",
                f"{tcfg['max_len']}자 이하로 간결하게 — 핵심 주제 + '정리/비교' 형태")

    order = {'block': 0, 'warn': 1, 'nit': 2}
    findings.sort(key=lambda f: (order.get(f['severity'], 3), f['code'], f['post']))
    return findings, frag_canonical, alias_by_norm


def apply_fix(posts, ssot):
    alias_by_norm, proper_by_norm, lc_ok = build_maps(ssot)
    _, frag_canonical, _ = lint(posts, ssot)
    changed = []
    for p in posts:
        new_tags, dirty = [], False
        for t in p['tags']:
            n = norm(t)
            c = t
            if n in alias_by_norm and alias_by_norm[n] != t:
                c = alias_by_norm[n]
            elif n in frag_canonical and frag_canonical[n] != t:
                c = frag_canonical[n]
            if c != t:
                dirty = True
            if c not in new_tags:
                new_tags.append(c)
        if not dirty:
            continue
        text = open(p['path'], encoding='utf-8').read()
        new, cnt = re.subn(r'(?m)^tags:\s*\[.*?\]\s*$', 'tags: [' + ', '.join(new_tags) + ']', text, count=1)
        if cnt:
            open(p['path'], 'w', encoding='utf-8').write(new)
            changed.append((p['slug'], new_tags))
        else:
            changed.append((p['slug'], None))  # block-style tags: 수동
    return changed


def main():
    argv = sys.argv[1:]
    as_json = '--json' in argv
    do_fix = '--fix' in argv
    only = None
    if '--post' in argv:
        i = argv.index('--post')
        only = argv[i + 1] if i + 1 < len(argv) else None

    ssot = load_ssot()
    posts = load_corpus()

    if do_fix:
        changed = apply_fix(posts, ssot)
        auto = [c for c in changed if c[1] is not None]
        manual = [c for c in changed if c[1] is None]
        if as_json:
            print(json.dumps({'fixed': [{'post': s, 'tags': t} for s, t in auto],
                              'manual': [s for s, _ in manual]}, ensure_ascii=False, indent=2))
        else:
            print(f"✅ 태그 정규화: {len(auto)}개 글 수정")
            for s, t in auto:
                print(f"  {s} → [{', '.join(t)}]")
            if manual:
                print(f"⚠ block-style tags(수동 필요): {', '.join(s for s, _ in manual)}")
        return 0

    findings, frag_canonical, _ = lint(posts, ssot, only_slug=only)
    blocks = [f for f in findings if f['severity'] == 'block']

    if as_json:
        out = {'block': [f for f in findings if f['severity'] == 'block'],
               'warn': [f for f in findings if f['severity'] == 'warn'],
               'nit': [f for f in findings if f['severity'] == 'nit'],
               'summary': {'posts': len(posts), 'block': len(blocks),
                           'warn': sum(1 for f in findings if f['severity'] == 'warn'),
                           'nit': sum(1 for f in findings if f['severity'] == 'nit')}}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1 if blocks else 0

    icon = {'block': '⛔', 'warn': '⚠', 'nit': '·'}
    print(f"# taxonomy-lint — 글 {len(posts)}개 검사"
          + (f" (필터: {only})" if only else ""))
    if not findings:
        print("✅ 파편화·카테고리·제목 이상 없음")
        return 0
    cur = None
    for f in findings:
        if f['severity'] != cur:
            cur = f['severity']
            n = sum(1 for x in findings if x['severity'] == cur)
            print(f"\n## {icon[cur]} {cur.upper()} ({n})")
        print(f"[{f['code']}] {f['label']}")
        print(f"    {f['context']}")
        print(f"    → {f['fix']}")
    print(f"\n요약: block {len(blocks)} · "
          f"warn {sum(1 for f in findings if f['severity']=='warn')} · "
          f"nit {sum(1 for f in findings if f['severity']=='nit')}")
    print("수정: python3 .claude/taxonomy-lint.py --fix  (태그 정규화; 제목·카테고리는 수동)")
    return 1 if blocks else 0


if __name__ == '__main__':
    sys.exit(main())
