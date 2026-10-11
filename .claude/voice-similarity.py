#!/usr/bin/env python3
"""voice-similarity.py — 한국어 기술블로그 문체 자기유사도 백테스트 (표준 라이브러리 전용).

설계(D2 적대검증 반영):
  - z-정규화 기준 코퍼스 = 전체 _posts (작은 골든셋의 σ 붕괴 방지).
  - 거리 = Burrows's Delta (피처 z-score의 평균 |차이|).
  - 스케일 자동 보정: 골든 자기유사도(leave-one-out 쌍별 평균)가 TARGET(75)에 오도록 K 계산.
    → '자기 글끼리도 100이 아니라 ~75'라는 self-similarity ceiling. 초안은 이 ceiling 대비 상대 판정.

사용:
  voice-similarity.py baseline       # 골든 baseline 계산·저장(voice-baseline.json)
  voice-similarity.py score <file>   # 초안을 골든셋에 대조 (PASS/FAIL)
  voice-similarity.py discriminate   # 변별력 검증: 골든(leave-one-out) vs 개조식 노트 점수 분포
"""
import os, re, sys, glob, json, math, argparse
from statistics import mean, pstdev

POSTS = os.path.expanduser('~/dev/hongjeZZ.github.io/_posts')
HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, 'voice-baseline.json')
TARGET = 75.0  # 골든 자기유사도 ceiling 목표점

# 톤 중립 — 한국어 유창성·구조만 측정한다. 톤(1인칭·들어가며/마치며·"결국")은 점수에서 제외:
# 그건 quality-profile §3(비인칭·선언형)가 SSOT다. voice는 "유창한 합쇼체 한국어인가"만 보고,
# 비인칭 공식 문서체 초안을 off-voice로 처벌하지 않는다. (first_person/has_intro/has_outro는 features()가
# 계산해도 FEATS에 없어 점수에 안 들어감.)
FEATS = ['hapsho', 'pyeong', 'da_plain', 'slen_mean', 'slen_cv', 'comma_rate', 'ttr',
         'nominal', 'fw_rate', 'sents_per_para', 'bullet_rate', 'bold_rate']
FW = ['그리고', '하지만', '그러나', '또한', '즉', '따라서', '그래서', '물론', '다만', '특히', '반면', '게다가', '예를']

def load(path):
    t = open(path, encoding='utf-8', errors='ignore').read()
    t = re.sub(r'^---\n.*?\n---\n', '', t, flags=re.S)      # frontmatter 제거
    full = t
    prose = re.sub(r'```.*?```', ' ', t, flags=re.S)        # 코드블록
    prose = re.sub(r'`[^`]*`', ' ', prose)                  # 인라인 코드
    prose = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', prose)     # 이미지
    prose = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', prose)  # 링크→텍스트
    prose = re.sub(r'[#>*|`]', ' ', prose)                  # md 기호
    return full, prose

def sentences(prose):
    parts = re.split(r'(?<=[다요까함음])[.!?]?\s+|[.!?]\s+|\n+', prose)
    return [s.strip() for s in parts if s.strip().split()]

def tokens(prose):
    return re.findall(r'[가-힣A-Za-z0-9]+', prose)

def _last(s):
    e = s.split()
    return e[-1].rstrip('.!?,') if e else ''

def features(full, prose):
    sents = sentences(prose); toks = tokens(prose)
    n_s = max(len(sents), 1); n_t = max(len(toks), 1)
    slen = [len(s.split()) for s in sents] or [0]
    def end(sufs): return sum(1 for s in sents if any(_last(s).endswith(x) for x in sufs))
    hap = ['습니다', '합니다', '입니다', '됩니다', '겠습니다', '봅니다', '니다']
    pyeong_end = ['이다', '한다', '된다', '였다', '았다', '었다', '간다', '난다']
    hapsho = end(hap) / n_s
    pyeong = end(pyeong_end) / n_s
    da_plain = sum(1 for s in sents if _last(s).endswith('다') and not any(_last(s).endswith(x) for x in hap)) / n_s
    paras = [p for p in re.split(r'\n\s*\n', full) if p.strip()]
    spp = mean([len(sentences(p)) for p in paras]) if paras else 0.0
    lines = [l for l in full.split('\n') if l.strip()]
    bullet = sum(1 for l in lines if re.match(r'\s*[-*]\s', l)) / max(len(lines), 1)
    return {
        'hapsho': hapsho, 'pyeong': pyeong, 'da_plain': da_plain,
        'slen_mean': mean(slen), 'slen_cv': (pstdev(slen) / mean(slen) if mean(slen) else 0.0),
        'comma_rate': (prose.count(',') + prose.count('，')) / n_s,
        'ttr': len(set(toks)) / n_t,
        'nominal': len(re.findall(r'[가-힣]{1,4}(?:성|적|화|적인)(?![가-힣])', prose)) / n_t,
        'first_person': len(re.findall(r'(?:제가|저는|저희|저도|제\b)', prose)) / n_t,
        'fw_rate': sum(prose.count(w) for w in FW) / n_t,
        'sents_per_para': spp,
        'bullet_rate': bullet,
        'bold_rate': full.count('**') / 2 / n_t,
        'has_intro': 1.0 if re.search(r'들어가며|들어가기', full) else 0.0,
        'has_outro': 1.0 if re.search(r'마치며|마무리|정리하', full) else 0.0,
    }

def corpus_stats(feats):
    mu, sd = {}, {}
    for k in FEATS:
        vals = [f[k] for f in feats]
        mu[k] = mean(vals); s = pstdev(vals); sd[k] = s if s > 1e-9 else 1.0
    return mu, sd

def zvec(f, mu, sd): return {k: (f[k] - mu[k]) / sd[k] for k in FEATS}
def delta(a, b): return mean(abs(a[k] - b[k]) for k in FEATS)   # Burrows's Delta

def feats_of(path):
    full, prose = load(path); return features(full, prose)

def golden_files():
    """골든 = 합쇼체 산문(습니다≥8) 중 **사람이 쓴 글만**.
    blog-publish 산출물(frontmatter에 source_wiki:)은 AI 초안 기반이라 기본 제외 —
    자기출력 학습 피드백 루프(accept_low가 단조 하향하는 ratchet) 방지.
    AI 보조 글을 골든에 넣고 싶으면 사용자가 in-voice 확인 후 voice-golden-allow.txt에 파일명 추가."""
    allow = set()
    ap = os.path.join(HERE, 'voice-golden-allow.txt')
    if os.path.exists(ap):
        allow = {l.strip() for l in open(ap, encoding='utf-8') if l.strip() and not l.startswith('#')}
    g = []
    for f in sorted(glob.glob(os.path.join(POSTS, '*.md'))):
        txt = open(f, encoding='utf-8', errors='ignore').read()
        if txt.count('습니다') < 8:
            continue
        ai_assisted = bool(re.search(r'^source_wiki:', txt, re.M))
        if ai_assisted and os.path.basename(f) not in allow:
            continue
        g.append(f)
    return g

def build():
    allf = sorted(glob.glob(os.path.join(POSTS, '*.md')))
    feats = {f: feats_of(f) for f in allf}
    mu, sd = corpus_stats(list(feats.values()))            # 기준 코퍼스 = 전체 47글
    golden = golden_files()
    gz = {f: zvec(feats[f], mu, sd) for f in golden}
    # 골든 쌍별 거리 평균 → K 보정
    pairs = [delta(gz[a], gz[b]) for i, a in enumerate(golden) for b in golden[i+1:]]
    dbar = mean(pairs)
    K = -math.log(TARGET / 100.0) / dbar                   # 골든 평균거리가 75점이 되도록
    # 각 골든의 leave-one-out 자기유사도 점수
    per = []
    for f in golden:
        d = mean(delta(gz[f], gz[o]) for o in golden if o != f)
        per.append(100.0 * math.exp(-K * d))
    bmean, bsd = mean(per), pstdev(per)
    return {'mu': mu, 'sd': sd, 'K': K, 'golden': golden, 'gz': {f: gz[f] for f in golden},
            'baseline_mean': bmean, 'baseline_sd': bsd, 'accept_low': bmean - 1.5 * bsd,
            'per_golden': dict(zip([os.path.basename(f) for f in golden], [round(x, 1) for x in per]))}

def score_text(path, B):
    f = feats_of(path); z = zvec(f, B['mu'], B['sd'])
    d = mean(delta(z, B['gz'][g]) for g in B['golden'])
    return 100.0 * math.exp(-B['K'] * d)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['baseline', 'score', 'discriminate'])
    ap.add_argument('file', nargs='?')
    a = ap.parse_args()
    if a.cmd == 'baseline':
        B = build()
        json.dump(B, open(BASELINE, 'w'), ensure_ascii=False, indent=1)
        print(f"골든 {len(B['golden'])}글 · 기준코퍼스 {len(glob.glob(os.path.join(POSTS,'*.md')))}글")
        print(f"자기유사도 baseline: mean {B['baseline_mean']:.1f} / sd {B['baseline_sd']:.1f} / accept_low(−1.5σ) {B['accept_low']:.1f}")
        print(f"K={B['K']:.3f}  (TARGET={TARGET})")
        print("\n골든별 leave-one-out 점수:")
        for k, v in sorted(B['per_golden'].items(), key=lambda x: -x[1]): print(f"  {v:5.1f}  {k}")
        print(f"\n→ verify: baseline mean {B['baseline_mean']:.1f} {'≥70 ✅' if B['baseline_mean']>=70 else '<70 ❌'}")
        return
    B = json.load(open(BASELINE)) if os.path.exists(BASELINE) else build()
    if a.cmd == 'score':
        if not a.file: sys.exit('score <file> 필요')
        s = score_text(a.file, B)
        ok = s >= B['accept_low']
        print(f"문체 점수: {s:.1f}  (baseline {B['baseline_mean']:.1f}, accept_low {B['accept_low']:.1f})")
        print(f"판정: {'✅ PASS (in-voice)' if ok else '⚠ FAIL (off-voice — 보이스 점검)'}")
        sys.exit(0 if ok else 1)
    if a.cmd == 'discriminate':
        golden = set(B['golden'])
        gset = golden_files()
        print("=== 골든 (leave-one-out, in-voice 기대) ===")
        for f in gset:
            z = zvec(feats_of(f), B['mu'], B['sd'])
            d = mean(delta(z, B['gz'][g]) for g in B['golden'] if g != f)
            print(f"  {100*math.exp(-B['K']*d):5.1f}  {os.path.basename(f)}")
        print("\n=== 개조식 노트 샘플 (off-voice 기대 — 점수 낮아야 변별력 OK) ===")
        notes = [f for f in sorted(glob.glob(os.path.join(POSTS, '*.md'))) if f not in golden][:0]
        import random  # 사용 안 함 — 고정 샘플
        samples = ['2025-03-24-cpu-scheduling.md', '2024-08-22-git-commands.md',
                   '2025-03-13-memory-hierarchy.md', '2024-08-14-spring-application-properties-profile.md',
                   '2025-01-03-boj-2579-stairs.md']
        for n in samples:
            p = os.path.join(POSTS, n)
            if os.path.exists(p):
                print(f"  {score_text(p, B):5.1f}  {n}")

if __name__ == '__main__':
    main()
