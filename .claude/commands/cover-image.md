---
description: 기술 대표 이미지(로고·아이콘)를 찾아 글 커버로 첨부 — 후보를 보여주고 사용자가 고른다
argument-hint: "<slug 또는 기술명> [--publish]"
allowed-tools: Bash, Read, Write, Edit, WebFetch, WebSearch, Task
---

# /cover-image

`$ARGUMENTS`가 가리키는 블로그 글(초안 또는 발행글)에 그 기술의 **대표 이미지(로고·아이콘)를 찾아 커버로 삽입**한다.
argo·aws 글처럼 **프론트매터 직후 인라인 `![](...)` 한 줄**이면 커버가 되고, 이 테마의 `_layouts/home.html`이
**본문 첫 이미지를 홈 리스트 썸네일로 자동 사용**하므로(별도 `image:` 프론트매터 불필요) 썸네일도 함께 붙는다.

## 위임 원칙 (중요)
- **상표·저작권 적합성 판단은 사용자가 초안을 검토할 때 한다 — 발행 게이트가 아니다.** 스킬은 적절한 후보를
  찾아 **보여주고**, 사용자가 고른 것만 첨부한다. 임의로 확정하지 않는다.
- 출처는 **참고용으로만** 기록한다(커밋 메시지 한 줄). 라이선스 때문에 후보 수집을 스스로 막지 않는다.

## 1. 대상·기술 해석
- `$ARGUMENTS` 첫 토큰 = slug 또는 기술명. 대상 파일을 찾는다:
  - 미발행 초안: `.pipeline/<slug>/draft.md`
  - 발행/발행대기 글: `_posts/*<slug>*.md` — **시리즈면 여러 편 전부 대상**(예: `aws-vpc`, `aws-vpc-2`).
- 대상 글의 `title`·`tags`·`source_wiki`로 **대표 기술명**을 정한다(예: `aws-vpc-*`→"AWS", `argo-workflows-*`→"Argo Workflows", `nvidia-smi`→"NVIDIA", `kafka-*`→"Apache Kafka").

## 2. 후보 이미지 수집 (2~4개)
`curl`로 받아 `200`인 것만 모은다. 우선순위:
1. **Devicon**(컬러, jsDelivr) — 워드마크 우선, 없으면 아이콘:
   - `https://cdn.jsdelivr.net/gh/devicons/devicon/icons/<name>/<name>-original-wordmark.svg`
   - `.../<name>-original.svg` · `.../<name>-plain.svg`
   - name 추론 예: AWS=`amazonwebservices`, k8s=`kubernetes`, nginx=`nginx`, kafka=`apachekafka`, docker=`docker`. 목록: devicon.dev
2. **Simple Icons**(브랜드 컬러):
   - `https://cdn.simpleicons.org/<slug>`(기본 검정) 또는 `https://cdn.simpleicons.org/<slug>/<hex>`(브랜드색)
   - slug: simpleicons.org. **일부 브랜드는 상표 사유로 없음**(예 AWS `amazonaws`→404) → 그럴 땐 Devicon/웹으로.
3. **공식 로고·위키미디어** — 위 둘에 없거나 부적절하면:
   - `WebSearch "<기술> logo svg official"` → `WebFetch`/`curl`로 공식 프레스킷·`commons.wikimedia.org` SVG/PNG.
4. **사용자 제공 이미지** — 사용자가 채팅에 붙여넣었으면 그걸 후보로. 디스크에 없으면 **세션에서 복구**:
   ```bash
   JSONL="$HOME/.claude/projects/-Users-anhongje-dev-hongjeZZ-github-io/<sessionId>.jsonl"
   grep -o '"data":"iVBORw0KGgo[A-Za-z0-9+/=]*"' "$JSONL" | tail -1 | sed 's/^"data":"//; s/"$//' \
     | python3 -c "import base64,sys;open('cand-user.png','wb').write(base64.b64decode(sys.stdin.read().strip()))"
   ```

## 3. 미리보기 → 사용자 선택 (위임 지점)
- 각 후보를 **커버 PNG로 정규화**(§5)해 scratchpad에 저장하고 **`Read`로 사용자에게 보여준다**(출처·라이선스 한 줄씩).
- 사용자가 하나를 고른다(또는 "붙여넣은 것"·"다시 찾아줘"). **스킬이 대신 확정하지 않는다.**

## 4. 첨부
- 고른 이미지를 정규화해 **`assets/img/<slug>/cover.png`** 로 저장(`mkdir -p` 보장).
- 대상 글 **frontmatter(`---`) 직후**에 삽입(이미 커버가 있으면 교체):
  ```
  ![<기술명>](/assets/img/<slug>/cover.png)
  ```
- **시리즈면 각 편에 동일 삽입.** `grep -n "cover.png" <파일>`로 삽입 확인.

## 5. 이미지 정규화 레시피 (이 환경엔 sips·qlmanage만 — SVG 래스터라이저 없음)
```bash
D="<scratchpad>"; SLUG="<slug>"
# (a) SVG → PNG (qlmanage QuickLook; 최대변 1024, RGBA). PNG 후보면 이 단계 생략.
qlmanage -t -s 1024 -o "$D" logo.svg            # → $D/logo.svg.png
# (b) 로고를 최대변 440으로 축소(비율 유지) → 사방 60px 흰 카드로 패딩
sips -Z 440 "$D/logo.svg.png" --out "$D/fit.png"
W=$(sips -g pixelWidth  "$D/fit.png" | awk '/pixelWidth/{print $2}')
H=$(sips -g pixelHeight "$D/fit.png" | awk '/pixelHeight/{print $2}')
mkdir -p "assets/img/$SLUG"
sips --padToHeightWidth $((H+120)) $((W+120)) --padColor FFFFFF "$D/fit.png" \
     --out "assets/img/$SLUG/cover.png"
sips -g pixelWidth -g pixelHeight "assets/img/$SLUG/cover.png"   # 확인
```
- 밝은 배경 권장(테마가 밝음). **투명 로고 그대로**가 나으면 (a)까지만 쓰고 패딩 생략.
- 로고가 가로형(워드마크)이면 결과 카드도 가로형이 된다 — 자동 적응.

## 6. 검토·발행 (사용자 위임)
- **기본**: 첨부까지만 하고 멈춘다. 초안이면 사용자가 검토 후 발행(draft-post 흐름), 발행글이면 사용자가 확인.
- **`--publish`**(발행글 대상)이면 PR 흐름 실행:
  1. `git checkout -b post/<slug>-cover`
  2. `git add assets/img/<slug>/cover.png <대상 글들>`
  3. 커밋 — **Co-Authored-By/Generated-with 금지**(commit-msg 훅 강제). 메시지에 이미지 **출처** 한 줄.
  4. **Gate2 오탐 주의**: pre-commit이 글 전체를 재스캔하다 AWS `*.compute.internal` 같은 **공개 규약**을 오탐하면, 확정 오탐 확인 후 `ALLOW_PUBLISH=1 git commit`.
  5. `git push -u origin …` → `gh pr create` → CI(build) 통과 → `gh pr merge --squash --delete-branch`.
  6. 배포 후 **라이브 검증**: `curl`로 `assets/img/<slug>/cover.png`→200, 각 글 HTML에 커버 `<img>`, 홈 리스트 `entry-thumb`에 cover.png.

## 실행
1. §1로 대상 파일·기술명 확정 → 2. 후보 2~4개 수집 → 3. 정규화·`Read`로 보여주고 **선택 대기** →
4. 고른 것 첨부(시리즈 전 편) → 6. 기본은 멈춤, `--publish`면 PR까지.

**참고**: `/draft-post`로 새 글을 만든 뒤 이 스킬로 커버를 붙이는 흐름이 자연스럽다. 이미 발행된 글에도 소급 적용 가능(argo·aws가 그 예).
