#!/usr/bin/env python3
"""tone-lint.py — 공식 문서체 위반(오글 톤) 결정론적 차단. 표준 라이브러리 전용.

quality-profile §3(비인칭·선언형)가 톤 SSOT다. LLM 품질 리뷰는 확률적이라 §3 금지
패턴을 놓칠 수 있다(실제로 콜아웃 제목의 'X이지 Y가 아니다'를 PASS시킨 적 있음).
이 린트는 사용자가 명시적으로 거부한 패턴만 high-precision 정규식으로 잡아 BLOCK한다
— "다시는 안 나오게"의 결정론적 백스톱. 광범위한 문체 판단은 하지 않는다(그건 LLM 축).

검사 대상 = 본문 산문만. frontmatter·코드블록·인라인코드·mermaid·HTML주석·URL은 제외.

사용:
  tone-lint.py <file>          # BLOCK 있으면 exit 1, 없으면 exit 0
  tone-lint.py --json <file>   # 결과를 JSON으로(파이프라인 축에서 사용)
"""
import re, sys, json, os

# (정규식, 라벨) — 사용자가 명시 거부한 §3 패턴만. 오탐을 막으려 매우 좁게 잡는다.
BLOCK = [
    # 수사적 대조 후크 "X이지 Y가 아니다" — '이지' 뒤 공백(절 경계) 강제로 페이지/이미지/패키지 오탐 차단
    (r'이지\s+[^\n]{0,18}?아니[다란]', '수사적 대조 후크 "X이지 Y가 아니다"(§3) — 평서로 진술'),
    # 1인칭 — 어두 경계 강제로 문제가/숙제가/실제 등 오탐 차단
    (r'(?<![가-힣])(?:저는|제가|저희|저도)(?![가-힣])', '1인칭(§3) — 주어는 글쓴이가 아니라 기술/대상'),
    (r'오늘\s*배운', '학습일기 메타프레이밍 "오늘 배운"(§3)'),
    (r'그게\s*아니', '개인 깨달음 반전 "그게 아니었/아니라"(§3)'),
    (r'인\s*줄\s*알았', '개인 깨달음 "~인 줄 알았는데"(§3)'),
    (r'안심하지', '반성 마무리 "안심하지 않으려"(§3)'),
    (r'않으려\s*합니다', '반성·권고 마무리 "~하지 않으려 합니다"(§3)'),
    (r'오해를\s*풀', '메타프레이밍 "오해를 풀고"(§3)'),
    (r'정리한\s*TIL|정리하는\s*TIL|TIL\s*입니다', 'TIL 일기 프레이밍(§3) — 태그는 되나 어조는 레퍼런스'),
]
# (정규식, 라벨) — WARN(차단 아님, 사람이 판단). 문두 대화체 연결어.
WARN = [
    (r'(?:^|[.!?]\s|\n)\s*결국\b', '대화체 연결어 문두 "결국"(§3)'),
    (r'(?:^|[.!?]\s|\n)\s*사실은\b', '대화체 연결어 문두 "사실은"(§3)'),
]

def prose_only(md):
    """frontmatter·코드블록·인라인코드·HTML주석·URL 제거 → 본문 산문만 남긴다."""
    md = re.sub(r'^---\n.*?\n---\n', '\n', md, flags=re.S)   # frontmatter
    md = re.sub(r'```.*?```', '\n', md, flags=re.S)           # 코드블록(mermaid 포함)
    md = re.sub(r'`[^`]*`', ' ', md)                          # 인라인 코드
    md = re.sub(r'<!--.*?-->', ' ', md, flags=re.S)           # HTML 주석(CAPTURE-NEEDED 등)
    md = re.sub(r'\]\([^)]*\)', '] ', md)                     # 링크 URL부 제거(텍스트는 남김)
    return md

def scan(path):
    md = open(path, encoding='utf-8', errors='ignore').read()
    text = prose_only(md)
    hits = []
    for pats, sev in ((BLOCK, 'block'), (WARN, 'warn')):
        for rx, label in pats:
            for m in re.finditer(rx, text):
                ctx = re.sub(r'\s+', ' ', text[max(0, m.start()-25):m.end()+25]).strip()
                hits.append({'severity': sev, 'label': label, 'match': m.group(0).strip(), 'context': f'…{ctx}…'})
    return hits

def main():
    args = [a for a in sys.argv[1:] if a != '--json']
    as_json = '--json' in sys.argv
    if not args:
        sys.exit('tone-lint.py [--json] <file>')
    path = args[0]
    if not os.path.exists(path):
        sys.exit(f'파일 없음: {path}')
    hits = scan(path)
    blocks = [h for h in hits if h['severity'] == 'block']
    warns = [h for h in hits if h['severity'] == 'warn']
    if as_json:
        print(json.dumps({'block': blocks, 'warn': warns, 'clean': not blocks}, ensure_ascii=False, indent=1))
    else:
        if not hits:
            print('tone-lint: 공식 문서체 위반 0건 ✅ (§3)')
        for h in blocks:
            print(f"BLOCK  {h['label']}\n       └ {h['context']}")
        for h in warns:
            print(f"warn   {h['label']}\n       └ {h['context']}")
        print(f"\n→ BLOCK {len(blocks)} · warn {len(warns)}  {'(차단)' if blocks else '(통과)'}")
    sys.exit(1 if blocks else 0)

if __name__ == '__main__':
    main()
