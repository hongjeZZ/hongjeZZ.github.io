---
title: "컨테이너 이미지 포맷과 Registry Pull 프로토콜 (OCI Image Spec)"
date: 2026-07-04 20:14:40 +0900
categories: [Infra, Kubernetes]
tags: [container, oci, docker, image, registry, kubernetes, imagepullpolicy, TIL]
source_wiki: container-image-pull-format
provenance: cite-only
---

![Kubernetes](/assets/img/container-image-pull-format/cover.png)

컨테이너 이미지는 하나의 파일이 아니라, JSON 문서 몇 개와 파일시스템 tar 묶음들이 콘텐츠 해시로 서로를 가리키는 작은 그래프입니다. 이 하나의 설계 결정 — 모든 조각을 자기 바이트의 해시로 식별하는 것 — 이 태그와 digest의 차이, 멀티아키텍처 이미지의 동작, Kubernetes의 `imagePullPolicy` 기본값, 레지스트리 pull 프로토콜까지 관통합니다.

이 글은 [OCI](https://opencontainers.org/)(Open Container Initiative) Image Spec·Distribution Spec, [Docker](https://docs.docker.com/) 문서, [Kubernetes](https://kubernetes.io/docs/concepts/containers/images/)·[containerd](https://containerd.io/) 공식 문서를 근거로 이미지 포맷과 pull 경로를 정리한 노트입니다. 이미지가 어떤 구조로 저장되고, 레지스트리에서 어떤 HTTP 흐름으로 내려오며, Kubernetes가 그 위에서 인증·정책·병렬성을 어떻게 다루는지를 아래에서 위로 따라갑니다.

> [!NOTE] 전제 지식
> Docker 이미지·태그·레지스트리의 기본 개념, HTTP 요청/응답과 헤더, SHA-256 같은 해시의 성질, Kubernetes Pod의 개념을 안다고 가정합니다. 이 글은 그 위에서 이미지의 내부 포맷과 pull 프로토콜을 다룹니다. 이미지를 받은 노드가 그 위에서 컨테이너를 실제로 실행하는 계층(CRI·containerd·runc)은 별도 편입니다.

## 이미지의 3층 구조: manifest + config + layers

**한 줄 요지: 컨테이너 이미지는 단일 파일이 아니라 manifest(JSON) → config(JSON) + layers(tar)로 이어지는 작은 문서 그래프이며, 모든 조각이 자기 바이트의 SHA-256 해시로 식별됩니다.**

OCI 컨테이너 이미지는 파일 하나가 아닙니다. JSON 문서 몇 개와 파일시스템 tarball blob들이 콘텐츠 해시로 묶인 작은 그래프입니다. 이미지 참조(예: `nginx:1.25`)에서 출발해 아래로 내려가는 구조는 다음과 같습니다.

```mermaid
graph TD
    ref["이미지 참조<br/>예: nginx:1.25"]
    manifest["Image Manifest (JSON)<br/>descriptor 목록만 담음"]
    config["Image Config (JSON)<br/>entrypoint · cmd · env · history"]
    l1["Layer blob 1 (tar / tar+gzip)"]
    l2["Layer blob 2"]
    l3["Layer blob 3 …"]

    ref --> manifest
    manifest -->|"config descriptor"| config
    manifest -->|"layers[] descriptor 배열"| l1
    manifest --> l2
    manifest --> l3
```

세 구성요소는 각각 이런 역할을 합니다.

- **manifest** — *한* 플랫폼(하나의 os/arch 조합)을 위한 최상위 포인터 문서입니다. 실제 파일시스템 콘텐츠를 담지 않고, config JSON과 각 레이어 blob을 가리키는 **descriptor**(mediaType + digest + size)만 담습니다.
- **config** — 그 자체가 digest로 주소 지정되는 blob이며, "이걸 어떻게 실행하는가" 메타데이터를 담습니다: entrypoint, cmd, 환경 변수, 작업 디렉터리, 노출 포트, 그리고 빌드 **history**.
- **layers** — 실제 파일시스템 콘텐츠입니다. 각 레이어는 이전 레이어 위에 적용되는 변경분(diff)을 나타내는, 압축(또는 비압축) tar 아카이브입니다.

OCI Image Spec은 이를 이렇게 요약합니다.

> An OCI Image consists of an image manifest, an image index (optional), a set of filesystem layers, and a configuration.

### Image Manifest — 정확한 스키마

manifest의 미디어 타입은 `application/vnd.oci.image.manifest.v1+json`입니다. 필수 최상위 필드는 다음과 같습니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `schemaVersion` | integer | REQUIRED, 이 스펙 버전에서는 `2`여야 한다 |
| `mediaType` | string | `application/vnd.oci.image.manifest.v1+json` |
| `config` | descriptor object | 이미지 config JSON blob을 가리킨다 |
| `layers` | array of descriptor objects | 순서 있는 파일시스템 레이어 blob 목록, 베이스가 먼저 |
| `annotations` | map[string]string | OPTIONAL, 임의 메타데이터 |

`config`와 `layers`의 각 항목에 쓰이는 **descriptor**는 필수 필드 세 개를 갖습니다.

- `mediaType` — 참조하는 blob의 콘텐츠 타입
- `digest` — 참조하는 blob의 콘텐츠 주소 해시(`sha256:<hex>`)
- `size` — 참조하는 blob의 크기(바이트)

레이어 `mediaType` 값에는 다음이 있습니다.

- `application/vnd.oci.image.layer.v1.tar` (비압축)
- `application/vnd.oci.image.layer.v1.tar+gzip` (gzip 압축 — 흔한 기본값)
- `application/vnd.oci.image.layer.v1.tar+zstd` (zstd 압축)

다음은 스펙 자체의 예제 manifest입니다.

```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.manifest.v1+json",
  "config": {
    "mediaType": "application/vnd.oci.image.config.v1+json",
    "digest": "sha256:b5b2b2c507a0944348e0303114d8d93aaaa081732b86451d9bce1f432a537bc7",
    "size": 7023
  },
  "layers": [
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:9834876dcfb05cb167a5c24953eba58c4ac89b1adf57f28f2f9d09af107ee8f0",
      "size": 32654
    }
  ],
  "annotations": {
    "com.example.key1": "value1"
  }
}
```

### Image Config — 정확한 스키마

config의 미디어 타입은 `application/vnd.oci.image.config.v1+json`입니다. 필수 필드는 다음과 같습니다.

- `architecture` (string) — 이 이미지의 바이너리가 겨냥하는 CPU 아키텍처(예: `amd64`, `arm64`)
- `os` (string) — 대상 OS(예: `linux`, `windows`)
- `rootfs` (object, 필수):
  - `type` — `"layers"`여야 한다
  - `diff_ids` — **비압축** 레이어 콘텐츠의 콘텐츠 해시 배열, 순서대로

> [!NOTE] diff_ids와 layers[].digest는 다른 해시다
> `diff_ids`는 *비압축* tar의 해시이고, manifest의 `layers[].digest`는 저장·전송되는 (압축됐을 수 있는) blob의 해시입니다. gzip/zstd 압축을 쓰면 같은 레이어라도 이 둘은 서로 다른 해시가 됩니다.

선택 필드는 다음과 같습니다.

- `created` — [RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339) 타임스탬프
- `author` — 자유 텍스트 생성자 문자열
- `config` (object) — 실제 런타임 기본값:
  - `User` — 실행 사용자
  - `ExposedPorts` — `"<port>/<protocol>": {}` 맵
  - `Env` — `"VARNAME=VARVALUE"` 문자열 배열
  - `Entrypoint` — 문자열 배열, 고정 실행 파일
  - `Cmd` — 문자열 배열, 기본 인자(덮어쓰기 가능)
  - `Volumes` — 마운트 지점 경로 → `{}` 맵
  - `WorkingDir` — 문자열
  - `Labels` — 문자열 메타데이터 맵(annotations와 같은 키 규칙)
  - `StopSignal` — 문자열, 예: `"SIGTERM"`
- `history` (object 배열) — 빌드 단계당 항목 하나, 각각:
  - `created`, `author`, `created_by`(Dockerfile 명령 텍스트), `comment`
  - `empty_layer` (boolean) — 이 history 항목이 파일시스템 변경을 만들지 않았으면 true(예: `ENV`나 `CMD` 명령). 이런 항목은 `rootfs.diff_ids`의 항목과 1:1로 대응하지 않는다.

이 `Entrypoint`/`Cmd`/`Env`/`WorkingDir`/`ExposedPorts` 집합이, Dockerfile의 `ENTRYPOINT`·`CMD`·`ENV`·`WORKDIR`·`EXPOSE` 명령이 컴파일되어 떨어지는 바로 그 형태입니다.

### 콘텐츠 주소 지정 — 핵심 설계 목표

**콘텐츠 주소 지정(content-addressable)**은 모든 blob을 자기 바이트의 해시로 식별하는 방식이며, 이미지 포맷의 첫 번째 설계 목표입니다. OCI Image Spec은 그 목표를 이렇게 밝힙니다.

> The first goal is content-addressable images, by supporting an image model where the image's configuration can be hashed to generate a unique ID for the image and its components.

모든 manifest·config·레이어 blob은 자기 바이트 콘텐츠의 SHA-256 digest(`sha256:<64자리 hex>`)로 식별됩니다. 이 성질에서 세 가지 결과가 따라옵니다.

1. **중복 제거(deduplication)** — 두 이미지가 베이스 레이어를 공유하면(예: 두 Node.js 앱이 모두 `FROM node:20`), 공유 레이어는 digest 기준으로 정확히 한 번만 저장·전송됩니다. 레지스트리와 로컬 이미지 저장소는 두 이미지가 함께 참조하는 단일 blob을 유지합니다.
2. **무결성 검증이 공짜** — blob을 받은 뒤 클라이언트가 다시 해시해 요청한 digest와 비교합니다. 전송 중 손상이나 변조가 결정론적으로 감지되며, 별도 체크섬 파일이 필요 없습니다.
3. **불변성(immutability)** — 하나의 digest는 오직 하나의 특정 바이트 시퀀스만 가리킬 수 있습니다. 그래서 digest는 (태그와 달리) 신뢰할 수 있는 고정 수단입니다.

## 이미지 참조 문법: 태그 vs digest

**한 줄 요지: 이미지 참조는 `[레지스트리[:포트]/]저장소[:태그][@digest]` 형태이며, 태그는 언제든 바뀔 수 있는 가변 포인터, digest는 절대 바뀌지 않는 불변 해시입니다.**

컨테이너 이미지 참조의 정규 형태는 다음과 같습니다.

```
[registry-host[:port]/]repository[/repository...][:tag][@digest]
```

예:

- `nginx` → 축약형
- `nginx:1.25` → 저장소 + 태그
- `myregistry.example.com:5000/team/app:v2` → 커스텀 레지스트리 + 포트 + 중첩 저장소 경로 + 태그
- `registry.k8s.io/pause:3.5@sha256:1ff6c18fbef2045af6b9c16bf034cc421a1e516b9da0234649c95d3c6c4b3d18` → 태그 **와** digest 동시 지정(둘 다 있으면 digest가 우선)

주요 문법 규칙은 다음과 같습니다.

- 레지스트리 호스트명은 DNS 규칙을 따라야 하고 언더스코어를 포함할 수 없으며, 뒤에 `:<port>`가 붙을 수 있습니다.
- 첫 `/` 앞 첫 경로 세그먼트가 호스트명처럼 보이지 않으면(점도 콜론도 없고 `localhost`도 아니면), 문자열 전체가 커스텀 레지스트리 호스트가 아니라 **기본 레지스트리**의 저장소 경로로 취급됩니다.
- 저장소 이름 구성요소는 소문자이며 구분자 `_`, `.`, `-`를 쓸 수 있습니다(반복·선행·후행 구분자에는 제약). `/`가 경로 구성요소(네임스페이스/저장소)를 나눕니다.
- 태그: 최대 128자, `[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}`에 일치해야 합니다(Kubernetes 문서가 이 정확한 정규식을 검증에 확인).
- Digest: `<algorithm>:<hex>`, 예: `sha256:<64자리 hex>`.

### 무자격 이름의 기본 레지스트리·네임스페이스

이미지 참조에 명시적 레지스트리 호스트가 없으면, 클라이언트에 설정된 기본 레지스트리가 쓰입니다. 레퍼런스 Docker 클라이언트와 대부분의 컨테이너 런타임에서 이 기본값은 **Docker Hub**(`docker.io`)이며, Docker Hub 안에서 무자격 단일 세그먼트 저장소 이름은 암묵적으로 **`library/`** 네임스페이스(Docker의 공식 이미지 네임스페이스) 아래에 놓입니다.

구체적으로:

- `busybox` → `docker.io/library/busybox:latest`로 해석
- `busybox:1.32.0` → `docker.io/library/busybox:1.32.0`로 해석
- `someuser/myapp` → `docker.io/someuser/myapp:latest`로 해석(`docker.io/library/someuser/myapp`가 **아님** — `library/` 접두사는 네임스페이스 세그먼트가 아예 없을 때만 주입됨)

> [!WARNING] 무자격 이름은 프로덕션에서 모호하다
> 무자격 이름은 전적으로 클라이언트 측 기본 레지스트리 설정에 의존하며, 이 설정은 클러스터·도구마다 다를 수 있고 조용히 재설정될 수도 있습니다. 그래서 Kubernetes 문서와 일반적인 컨테이너 보안 가이드는, 어떤 레지스트리가 실제로 바이트를 서빙하는지에 대한 모호성을 없애기 위해 프로덕션 매니페스트에서 항상 완전 자격(fully-qualified) 이미지 참조(명시적 레지스트리 호스트)를 쓰기를 권장합니다.

### 태그의 가변성과 `:latest` 함정

**태그는 가변 포인터입니다.** `nginx:1.25`나 `myapp:latest` 같은 태그는, 레지스트리가 특정 시점에 *어떤* manifest digest에 매핑해 둔 라벨일 뿐입니다. 레지스트리 소유자(또는 push 권한이 있는 누구든)는 언제든 같은 태그로 다른 이미지를 재푸시할 수 있습니다. 그러면 태그는 태그 레벨에 아무 이력도 남기지 않은 채 새 바이트를 가리킵니다.

**digest는 불변 콘텐츠 해시입니다.** `myapp@sha256:abc123...`은 오직 하나의 특정 manifest, 그리고 그것이 가리키는 하나의 config + 레이어 집합만을 뜻할 수 있습니다. digest가 가리키는 대상을 "갱신"할 방법은 없습니다 — 다른 이미지는 단지 다른 digest를 가질 뿐입니다.

`:latest`가 위험한 이유는 다음과 같습니다.

1. `latest`는 "가장 새 버전"이라는 의미적 보장이 아니라 관습상의 태그 이름일 뿐입니다. 유지보수자가 `latest`에 더 오래된 빌드를 푸시하거나, 아예 갱신하지 않는 것을 막는 장치가 없습니다.
2. 가변이기 때문에, 서로 다른 시점(또는 로컬 캐시가 있는 서로 다른 노드)에서 `image:latest`를 두 번 pull하면 조용히 **다른 실제 콘텐츠**로 해석될 수 있어 재현성이 깨집니다. "내 머신에선 되는데" 버그와 노드 간 불일치가 여기서 직접 비롯됩니다.
3. Kubernetes에서는 태그를 생략하거나 `:latest`를 명시하면 *기본* `imagePullPolicy`가 `Always`로 바뀌어, 컨테이너가 (재)시작될 때마다 레지스트리 왕복을 강제합니다. 플랫폼이 "이 태그를 단 이미지"가 안정적이라고 신뢰할 수 없어서, 가변성 문제가 기본값에까지 반영됐습니다.
4. 모범 사례(Kubernetes 문서와 OCI 생태계 가이드에서 확인됨)는, 프로덕션 배포를 명시적 시맨틱 버전 태그에, 더 강하게는 digest(`image@sha256:...`)에 고정하는 것입니다. 이후 태그에 무슨 일이 생기든 바이트 단위 재현성을 보장합니다.

## 멀티아키텍처: Image Index (fat manifest)

**한 줄 요지: 하나의 태그가 여러 아키텍처를 지원하려면, 태그가 실제로 가리키는 것은 os/arch별 manifest를 나열한 Image Index이고, 클라이언트는 자기 플랫폼과 맞는 항목 하나만 골라 받습니다.**

단일 이미지 manifest는 **하나의** 플랫폼 — 하나의 (os, arch, variant) 조합 — 에만 스코프됩니다. 그런데 `nginx` 같은 이미지는 amd64 서버, arm64 서버(Graviton, Apple Silicon 빌드 호스트), 그리고 경우에 따라 다른 OS에서도 돌아야 합니다. 아키텍처별로 이미지 이름을 따로 두는 대신(`nginx-amd64`, `nginx-arm64`, ...), OCI는 **fat manifest** — **Image Index** — 를 정의합니다. 태그가 실제로 가리키는 것이 이 Image Index이고, Index가 다시 플랫폼별 manifest 하나씩을 가리킵니다.

```mermaid
graph TD
    tag["nginx:1.25 (태그)"]
    index["OCI Image Index<br/>application/vnd.oci.image.index.v1+json"]
    m1["manifest · linux/amd64"]
    m2["manifest · linux/arm64"]
    m3["manifest · linux/arm/v7"]
    c1["amd64용 config + layers"]
    c2["arm64용 config + layers"]
    c3["armv7용 config + layers"]

    tag --> index
    index --> m1 --> c1
    index --> m2 --> c2
    index --> m3 --> c3
```

### 정확한 스키마

Image Index의 미디어 타입은 `application/vnd.oci.image.index.v1+json`입니다.

```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.index.v1+json",
  "manifests": [
    {
      "mediaType": "application/vnd.oci.image.manifest.v1+json",
      "digest": "sha256:e692...",
      "size": 7143,
      "platform": {
        "architecture": "amd64",
        "os": "linux"
      }
    },
    {
      "mediaType": "application/vnd.oci.image.manifest.v1+json",
      "digest": "sha256:5b0b...",
      "size": 7143,
      "platform": {
        "architecture": "arm64",
        "os": "linux"
      }
    }
  ],
  "annotations": {}
}
```

필수 필드는 `schemaVersion`(Docker 하위 호환을 위해 `2`여야 함), `mediaType`, `manifests`(배열, 비어 있어도 됨)입니다.

`manifests`의 각 항목은 descriptor(`mediaType` + `digest` + `size`)에 선택적 `platform` 객체가 더해진 형태입니다.

- `architecture` — 예: `amd64`, `arm64`, `ppc64le`, `s390x`
- `os` — 예: `linux`, `windows`
- `os.version` (선택) — 요구 OS 버전(Windows에서 사용)
- `os.features` (선택) — 요구 OS 기능 배열
- `variant` (선택) — CPU variant, 예: ARM 하위 아키텍처의 `v7`, `v8`

### 클라이언트가 맞는 것을 고르는 방법

클라이언트(Docker Engine, containerd, kubelet의 CRI 런타임)가 이미지 참조를 해석할 때의 순서는 다음과 같습니다.

1. 태그/digest가 가리키는 최상위 객체를 가져온다.
2. 반환된 `mediaType`이 **Image Index**(`application/vnd.oci.image.index.v1+json`, 또는 Docker 등가물 `application/vnd.docker.distribution.manifest.list.v2+json`)이면, `manifests[]` 배열을 살핀다.
3. 자신의 런타임 플랫폼(arch/OS, 예: 컨테이너 런타임의 노드 `GOARCH`/`GOOS`)을 각 항목의 `platform` 객체와 비교한다.
4. OCI 스펙에 따라, 여러 manifest가 클라이언트/런타임 요구에 맞으면 **배열의 첫 매치 항목을 사용**한다. 그래서 배열 순서가 tie-breaker로 작동한다.

   > If multiple manifests match a client or runtime's requirements, the first matching entry SHOULD be used.

5. 그 하나의 플랫폼별 manifest(그리고 그것이 가리키는 config + 레이어)만 실제로 가져와 노드에 저장한다. 필요 없는 아키텍처의 바이트는 결코 내려받지 않는다.

이것이 Kubernetes Pod 명세의 `image: nginx:1.25` 한 줄이 amd64/arm64 혼합 노드 풀에서 수정 없이 동작하는 원리입니다 — kubelet의 컨테이너 런타임이 노드별로 맞는 manifest를 투명하게 해석합니다.

## Registry HTTP API v2 — pull 프로토콜

**한 줄 요지: 레지스트리 pull은 OCI Distribution Spec이 정의한 HTTP API v2 위에서 (1) manifest 요청 → (2) 레이어 digest 파싱 → (3) 각 blob 요청(로컬에 있으면 생략) → (4) 재해시 검증·추출의 네 단계로 이뤄집니다.**

### 기본 엔드포인트 / API 버전 확인

`GET /v2/`가 API 버전 확인용 엔드포인트입니다. 클라이언트는 실제 작업을 시도하기 전에 이것으로 레지스트리가 Distribution/OCI v2 API를 말하는지 확인합니다.

> If the response is `200 OK`, then the registry implements this specification.

### Pull 흐름 — 단계별

**1단계 — 태그 또는 digest로 manifest(또는 index)를 가져온다:**

```
GET /v2/<name>/manifests/<reference>
```

- `<name>`은 저장소 네임스페이스(예: `library/nginx`, `myorg/myapp`).
- `<reference>`는 태그 이름 또는 digest(`sha256:...`).
- 클라이언트는 자신이 이해하는 manifest 미디어 타입을 나열한 `Accept` 헤더를 보내야 합니다(구 Docker v2 schema2 포맷과 신 OCI manifest/index 미디어 타입 사이의 콘텐츠 협상이 이렇게 일어납니다).
- 응답 `200 OK`와 함께 manifest JSON 본문, 그리고 실제로 반환된 manifest의 digest를 담은 필수 응답 헤더 `Docker-Content-Digest`가 옵니다(태그→manifest 해석 결과를, 예컨대 digest 고정과 대조해 클라이언트가 검증할 수 있게).
- 저장소나 참조가 없으면 `404 Not Found`.

**2단계 — manifest를 파싱해 레이어 digest를 추출한다:**

클라이언트는 manifest JSON에서 `config.digest`와 각 `layers[i].digest`를 읽습니다. 가져온 객체가 실제로 Image Index였다면, 클라이언트는 먼저 플랫폼에 맞는 `manifests[i].digest`로 1단계를 반복해 실제 플랫폼별 manifest를 얻습니다.

**3단계 — 각 blob(config + 모든 레이어)을 digest로 가져오되, 이미 로컬에 있는 것은 건너뛴다:**

```
GET /v2/<name>/blobs/<digest>
```

- 응답 `200 OK`가 원시 blob 바이트를 스트리밍하고, `Docker-Content-Digest` 헤더가 반환되는 것의 digest를 확인해 줍니다.
- blob이 없으면 `404 Not Found`.
- 레지스트리는 blob 다운로드에 HTTP `Range` 요청([RFC 9110](https://datatracker.ietf.org/doc/html/rfc9110))을 지원해야 하며(SHOULD), 이로써 큰 레이어의 재개 가능·병렬 청크 다운로드가 가능합니다.
- blob을 요청하기 전에, 클라이언트(containerd/Docker)는 로컬 콘텐츠 저장소를 확인합니다. **그 정확한 digest의 blob이 (콘텐츠 주소 지정 중복 제거 덕분에 어느 이미지에서든) 이미 디스크에 있으면 재사용하고 다시 내려받지 않습니다.** 앞서 말한 "공유 베이스 레이어는 한 번만 받는다"가 바로 이 지점에서 일어납니다.

**4단계 — digest 검증, 추출:**

내려받은 모든 blob에 대해 클라이언트가 해시를 다시 계산해 요청한 digest와 비교합니다. 불일치면 다운로드를 거부합니다(손상과, 손상되거나 오작동하는 레지스트리의 조용한 콘텐츠 치환을 막습니다). 검증되면 레이어 tarball을 manifest 순서대로 런타임의 레이어드 파일시스템(예: [overlayfs](https://docs.kernel.org/filesystems/overlayfs.html))에 풀어 넣고, 각 레이어의 변경분을 이전 레이어 위에 적용해 컨테이너가 실행될 최종 루트 파일시스템을 만듭니다.

"이 blob이 애초에 필요한가"를 GET에 앞서 값싸게 확인하는 존재 여부 체크는 `HEAD`로 가능합니다.

```
HEAD /v2/<name>/manifests/<reference>
HEAD /v2/<name>/blobs/<digest>
```

있으면 `200 OK`(`Docker-Content-Digest`·`Content-Length` 헤더 포함), 없으면 `404 Not Found`를 반환하며, 응답 본문은 전송되지 않습니다.

### 인증 — Bearer 토큰 흐름

Distribution v2 API는 표준 HTTP `WWW-Authenticate` 챌린지-리스폰스 패턴으로 인증을 외부 토큰 서비스에 위임합니다. 무인증(또는 스코프가 부족한) 요청이 401과 챌린지 헤더를 받으면, 클라이언트가 realm URL에서 스코프가 지정된 단기 토큰을 발급받아 재요청합니다. 클라이언트·레지스트리·토큰 서비스 세 주체 사이의 왕복은 다음과 같습니다.

```mermaid
sequenceDiagram
    participant C as 클라이언트
    participant R as 레지스트리 (/v2)
    participant A as 토큰 서비스 (realm)

    C->>R: GET /v2/.../manifests/latest — 무인증
    R-->>C: 401 Unauthorized<br/>WWW-Authenticate: Bearer realm, service, scope
    C->>A: GET realm?service=...&scope=repository:...:pull
    A-->>C: 200 — token, expires_in 반환
    C->>R: GET /v2/.../manifests/latest<br/>Authorization: Bearer token
    R-->>C: 200 OK — manifest JSON
    Note over C,R: 이후 모든 blob GET에 같은 토큰 재사용, 만료 전까지
```

**1단계 — 무인증(또는 저스코프) 요청이 챌린지를 받는다:**

```
GET /v2/samalba/my-app/manifests/latest
→ HTTP/1.1 401 Unauthorized
  WWW-Authenticate: Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:samalba/my-app:pull"
```

`WWW-Authenticate` 헤더는 핵심 파라미터 세 개를 담습니다.

- `realm` — 토큰 발급 엔드포인트의 URL
- `service` — 토큰이 어느 서비스(레지스트리)용인지 식별
- `scope` — 요청하는 구체 권한, 형식 `repository:<name>:<action>[,<action>...]`(예: `pull`, `pull,push`)

**2단계 — 클라이언트가 realm URL에서 토큰을 요청한다:**

```
GET https://auth.docker.io/token?service=registry.docker.io&scope=repository:samalba/my-app:pull
```

(클라이언트 자격 — 예: 레지스트리 사용자명/비밀번호를 쓴 HTTP Basic 인증, 또는 공개 이미지의 익명 pull이면 없음 — 이 요청에 필요에 따라 첨부됩니다.)

**3단계 — 토큰 엔드포인트가 Bearer 토큰으로 응답한다:**

```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiI...",
  "expires_in": 3600,
  "issued_at": "2009-11-10T23:00:00Z"
}
```

**4단계 — 클라이언트가 Bearer 토큰으로 원래 요청을 재시도한다:**

```
GET /v2/samalba/my-app/manifests/latest
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiI...
→ HTTP/1.1 200 OK
```

토큰은 스코프가 지정되고 시간 제한(`expires_in` 초)이 있습니다. 클라이언트는 요청마다 재인증하지 않고, pull 작업의 나머지 전체(manifest GET과 이후 모든 blob GET)에서 토큰을 캐시·재사용하며, 만료되면 새 토큰을 요청하도록 기대됩니다.

<details markdown="1">
<summary>심화: push 흐름 (pull 경로는 아니지만 같은 API 표면)</summary>

push는 pull의 역방향입니다. Kubernetes pull 경로의 관심사는 아니지만 같은 API 표면을 이해하는 데 도움이 됩니다.

1. **blob 업로드** — 두 가지:
   - 단일(monolithic): `POST /v2/<name>/blobs/uploads/?digest=<digest>`에 전체 blob 본문 → 성공 시 `201 Created`.
   - 청크/재개형: `POST /v2/<name>/blobs/uploads/`로 세션 시작 → `202 Accepted`와 업로드 세션용 `Location` 헤더. 이어 하나 이상의 `PATCH <location>`로 청크를 스트리밍(매번 갱신된 `Location`/`Range` 헤더와 함께 `202 Accepted`). 마지막에 `PUT <location>?digest=<digest>`로 마무리 → `201 Created`.
2. **manifest 업로드** — `PUT /v2/<name>/manifests/<reference>`에 manifest JSON 본문과 manifest의 `mediaType`으로 설정한 `Content-Type`. 레지스트리는 manifest를 제공된 바이트 그대로 저장합니다(이 정확-바이트 저장이, 그 위에서 계산된 digest를 유효·재현 가능한 콘텐츠 주소로 만듭니다) → `201 Created`.
3. manifest push는 보통 참조하는 모든 blob(config + 레이어)이 레지스트리에 이미 존재한 **뒤에** 일어납니다. 의존 대상이 해석되지 않으면 manifest는 무의미하기 때문입니다.

</details>

### Docker Hub rate limit

Docker Hub는 pull 횟수에 제한을 둡니다. 계정 유형별 제한은 다음과 같습니다.

| 계정 유형 | pull 제한 |
|---|---|
| 익명(무인증) | 6시간당 100회 (IP 주소당) |
| 인증, Docker Personal(무료) | 6시간당 200회 |
| Docker Pro / Team / Business(유료) | pull rate limit 없음 |

Kubernetes 클러스터 관점에서의 실무적 함의는 다음과 같습니다.

- 익명 pull은 **소스 IP당** rate limit이 걸립니다. 여러 노드가 공유 NAT 게이트웨이 IP로 나가는 대형 클러스터·CI에서는 심각한 문제입니다 — IP 하나의 쿼터를 전체 fleet이 공유하므로 빠르게 소진되고, 특정 Pod의 행위와 무관한 `ErrImagePull`/`429 Too Many Requests` 실패를 냅니다.
- 이것이 레지스트리 미러 / pull-through 캐시(뒤 섹션)를 두고, CI·프로덕션에서 익명 접근에 기대는 대신 항상 인증 pull을 하는 실무적 동기 중 하나입니다.

> [!NOTE] 이 수치는 변동될 수 있다
> Docker는 이전에 예고했던(2025년 4월 예정) 이 제한 강화를 이 문서 작성 시점 기준으로 시행하지 않았습니다. 위의 100/200 수치가 현재값이지만, Docker는 이 정책이 여전히 검토 중이며 변경될 수 있다고 밝혔습니다.

## imagePullSecrets — 프라이빗 레지스트리 인증

**한 줄 요지: 프라이빗 레지스트리 자격은 `kubernetes.io/dockerconfigjson` 타입 Secret으로 만들어 Pod 또는 ServiceAccount에 붙이거나, 정적 Secret 없이 kubelet 크리덴셜 프로바이더 플러그인이 동적으로 발급합니다.**

### docker-registry Secret 만들기

```bash
kubectl create secret docker-registry <secret-name> \
  --docker-server=<registry-hostname> \
  --docker-username=<username> \
  --docker-password=<password> \
  --docker-email=<email>
```

이 명령은 `kubernetes.io/dockerconfigjson` 타입 Secret을 만듭니다. 페이로드는 사실상 레지스트리 호스트명 → 자격으로 키가 매겨진 `~/.docker/config.json` 형태의 blob입니다.

이미 로컬 Docker config 파일이 있을 때(예: `docker login`이나 클라우드 CLI가 만든 것) 유용한 generic-secret 형태도 있습니다.

```bash
kubectl create secret generic <secret-name> \
  --from-file=.dockerconfigjson=<path/to/.docker/config.json> \
  --type=kubernetes.io/dockerconfigjson
```

구형 `kubernetes.io/dockercfg` 타입(레거시 `.dockercfg` 포맷)도 Pod 명세의 `imagePullSecrets`에서 여전히 받아들여지지만, 현재 표준은 `dockerconfigjson`입니다.

### Pod 명세 vs ServiceAccount에서 참조

**Pod 레벨**(가장 흔하고 가장 명시적):

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: foo
spec:
  containers:
    - name: foo
      image: janedoe/awesomeapp:v1
  imagePullSecrets:
    - name: myregistrykey
```

여기에는 하드 제약이 하나 있습니다.

> All `imagePullSecrets` must be Secrets that exist in the same namespace as the Pod.

다른 네임스페이스의 Secret은 참조할 수 없습니다.

**ServiceAccount 레벨**(클러스터/네임스페이스 전역 기본값 — 모든 Pod 명세에 같은 `imagePullSecrets` 블록을 반복하지 않아도 됨): Secret을 Pod가 실행되는 ServiceAccount의 `imagePullSecrets` 목록에 붙일 수 있습니다. 그 ServiceAccount를 쓰는 모든 Pod가 Pod별 선언 없이 자동으로 pull 자격을 상속합니다. 네임스페이스 전체(또는 네임스페이스의 `default` ServiceAccount)에 프라이빗 레지스트리 접근을 일괄로 주는 데 흔히 쓰이는 패턴입니다.

여러 자격 출처는 공존할 수 있습니다 — Pod 레벨과 ServiceAccount 레벨 `imagePullSecrets`, 그리고 노드 레벨 자격 — kubelet/컨테이너 런타임이 특정 pull을 인증할 때 필요에 따라 이들을 병합·시도합니다.

### kubelet이 자격을 실제로 쓰는 순서

kubelet이 컨테이너 이미지를 pull해야 할 때, 자격을 다음 고려 순서로 해석합니다.

1. Pod가 참조하는 `imagePullSecrets`(직접, 또는 ServiceAccount에서 상속).
2. 노드 자체에 설정된 노드 레벨 Docker config(`~/.docker/config.json` 등가) — 클러스터 전역 정적 노드 자격을 쓸 때. 그 노드에 스케줄된 모든 Pod가 사실상 같은 레지스트리 신원을 공유하므로 Pod별 Secret보다 거친, 덜 권장되는 대안입니다.
3. 설정된 **kubelet 이미지 크리덴셜 프로바이더 플러그인** — 정적 config를 읽는 대신 pull 시점에 동적으로 호출됨.

해석된 자격은 최종적으로 `PullImage` CRI 호출의 일부로 컨테이너 런타임(containerd/[CRI-O](https://cri-o.io/))에 전달되고, 런타임이 대상 레지스트리에 대해 앞서 설명한 Bearer 토큰 교환을 실제로 수행합니다.

### kubelet 이미지 크리덴셜 프로바이더 플러그인 (동적 자격)

Kubernetes v1.20부터(이후 릴리스에서 GA) kubelet은 pull 시점에 호출되어 단기 레지스트리 자격을 동적으로 가져오는 **exec 방식 크리덴셜 프로바이더 플러그인**을 지원합니다. 장수 정적 Secret에 기대는 대신입니다. kubelet 플래그 두 개로 설정합니다.

```
--image-credential-provider-config=<path-to-config.yaml>
--image-credential-provider-bin-dir=<path-to-plugin-binaries>
```

`CredentialProviderConfig` 예제는 다음과 같습니다.

```yaml
apiVersion: kubelet.config.k8s.io/v1
kind: CredentialProviderConfig
providers:
  - name: ecr-credential-provider
    matchImages:
      - "*.dkr.ecr.*.amazonaws.com"
      - "*.dkr.ecr.*.amazonaws.com.cn"
      - "*.dkr.ecr-fips.*.amazonaws.com"
    defaultCacheDuration: "12h"
    apiVersion: credentialprovider.kubelet.k8s.io/v1
    env:
      - name: AWS_PROFILE
        value: example_profile
```

주요 필드는 다음과 같습니다.

- `name` — `--image-credential-provider-bin-dir`에서 찾을 실행 바이너리 이름과 일치해야 한다.
- `matchImages` — 이미지의 레지스트리 호스트/경로에 매칭되는 glob 패턴. 이 중 하나에 맞는 이미지에만 플러그인이 호출된다.
- `defaultCacheDuration` — 플러그인 응답이 자체 TTL을 지정하지 않을 때, kubelet이 반환된 자격을 캐시하는 기간.
- `apiVersion` — kubelet이 stdin/stdout으로 바이너리와 통신하는(JSON 요청/응답) 버전화된 exec-plugin 프로토콜(`credentialprovider.kubelet.k8s.io/v1`).
- `args`, `env` — 플러그인 프로세스에 넘길 선택적 인자/환경 변수.
- `tokenAttributes` (Kubernetes v1.33+) — kubelet이 프로젝션된 **서비스 어카운트 토큰**을 플러그인에 전달하게 해, 노드 전역 자격 대신 Pod별 신원 기반 자격 해석을 가능케 한다(pod-identity 기반 인증 모델에 관련).

### 클라우드별: ECR 크리덴셜 헬퍼 / IRSA

**AWS ECR**에는 혼동하기 쉬운 서로 다른 두 메커니즘이 있습니다.

- [`amazon-ecr-credential-helper`](https://github.com/awslabs/amazon-ecr-credential-helper)는 **Docker CLI 크리덴셜 헬퍼**입니다 — Docker/[Podman](https://docs.podman.io/) 클라이언트 자신의 크리덴셜 스토어 메커니즘(`~/.docker/config.json`의 `credHelpers`)에 꽂혀, ECR을 상대로 직접 `docker pull`/`docker push`하는 인터랙티브/CI 용도에 씁니다. EKS/Fargate의 kubelet 주도 pull에 쓰도록 설계된 것이 **아닙니다.**
- Kubernetes/EKS에서 지원되는 경로는 앞 절의 **kubelet 크리덴셜 프로바이더 플러그인** 메커니즘입니다. `ecr-credential-provider` 바이너리가 노드에 설치되고(EKS 최적화 AMI가 기본 탑재) `matchImages: ["*.dkr.ecr.*.amazonaws.com", ...]`로 설정됩니다. pull 시점에 kubelet이 그것을 호출하면, 플러그인이 **노드의 IAM 역할**(또는 최신 pod-identity 인식 설정에서는 Pod 스코프 신원)을 써서 `ecr:GetAuthorizationToken`을 호출하고 단기 자격을 반환합니다 — 정적 Secret이 필요 없습니다.
- **[IRSA(IAM Roles for Service Accounts)](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)**는 OIDC 페더레이션으로 Kubernetes ServiceAccount를 IAM 역할에 매핑해, Pod 자신의 AWS SDK 호출이 그 역할을 assume하게 합니다. IRSA가 다스리는 것은 *실행 중인* Pod의 애플리케이션 코드가 AWS API에 무엇을 할 수 있는가이며, *노드/kubelet이 애초에 Pod의 컨테이너 이미지를 어떻게 pull했는가*(보통 노드 IAM 역할 + ECR 크리덴셜 프로바이더 경로)와는 별개 관심사입니다. 둘 다 "Kubernetes에서 장수 정적 AWS 자격을 피한다"를 풀지만 서로 다른 계층(노드/kubelet vs Pod/애플리케이션)에서 작동합니다.

GKE의 GCR/Artifact Registry도 원리가 같습니다. 이미지 pull은 근본적으로 노드 자신의 Google Cloud 서비스 계정이 수행하는 **노드 레벨** 작업이며, 애플리케이션 코드의 Pod-to-Google-API 인증을 다스리는 Workload Identity(위 IRSA에 대응)가 아닙니다. GKE 클러스터와 레지스트리 저장소가 **같은 GCP 프로젝트**에 있으면 노드의 IAM 서비스 계정에 레지스트리 읽기 권한을 주는 것으로 충분하고 `imagePullSecrets`가 필요 없습니다. 교차 프로젝트 시나리오는 노드 서비스 계정에 대한 명시적 IAM 권한 부여나, 서비스 계정 키를 담은 고전적 `imagePullSecrets` Secret이 필요합니다.

## imagePullPolicy 시맨틱

**한 줄 요지: `imagePullPolicy`는 `Always`·`IfNotPresent`·`Never` 세 값을 가지며, 생략 시 기본값은 태그 형태로 결정되고(오브젝트 최초 생성 시 한 번 계산·고정), K8s v1.33부터는 `IfNotPresent`라도 캐시 히트 시 요청 Pod의 자격을 재검증합니다.**

### 세 가지 값

- **`Always`** — kubelet이 컨테이너를 (재)기동할 때마다 컨테이너 런타임에 이미지 pull을 요청합니다. 런타임은 태그를 레지스트리에 대해 digest로 해석하고, 로컬 캐시에 아직 없는 레이어만 내려받습니다(콘텐츠 주소 지정 중복 제거). 즉 `Always`는 "매번 전부 재다운로드"가 아니라 "매번 레지스트리를 재확인"을 뜻합니다. 필요한 모든 레이어가 해석된 digest 아래 이미 캐시돼 있으면 실제로 전송되는 바이트는 없지만, 태그→digest 해석을 위한 레지스트리 왕복은 매번 일어나며, 이는 레이턴시 비용과 (앞서의) Docker Hub rate limit 소모를 동반합니다.
- **`IfNotPresent`** — 이미지가 노드에 **아직 없을 때만** 레지스트리에서 pull합니다. 이전 pull이 정확히 해석된 참조에 맞는 이미지를 이미 캐시했다면, kubelet은 pull을 통째로 건너뛰고 캐시된 이미지로 컨테이너를 시작합니다 — 그 경우 레지스트리 접촉이 전혀 없습니다.
- **`Never`** — kubelet이 이 이미지를 위해 레지스트리를 결코 접촉하지 않습니다. 이미지가 로컬에 이미 있지 않으면(예: 수동 [`crictl`](https://github.com/kubernetes-sigs/cri-tools/blob/master/docs/crictl.md) `pull`, 또는 미리 구운 노드 이미지) 컨테이너 시작이 즉시 실패합니다.

### 기본 정책 — 태그에 따라 달라진다

`imagePullPolicy`가 컨테이너 명세에서 생략되면, Kubernetes는 이미지 참조를 근거로 기본값을 계산합니다.

| 이미지 참조 형태 | 기본 `imagePullPolicy` |
|---|---|
| digest 지정 (`image@sha256:...`) | `IfNotPresent` |
| 태그가 `:latest` | `Always` |
| 태그를 아예 지정하지 않음(암묵적 `:latest`) | `Always` |
| 명시적 non-`latest` 태그(예: `:1.25`) | `IfNotPresent` |

이 기본값에는 중요한 시점 규칙이 있습니다.

> The value of `imagePullPolicy` of the container is always set when the object is first created, and is not updated if the image's tag or digest later changes.

즉 이 기본값은 오브젝트 생성 시점에 한 번 계산되어 Pod의 유효 명세에 고정됩니다. 기존 컨트롤러의 이미지 태그를 나중에 바꿔도 이미 기본값이 정해진 Pod 템플릿의 정책이 소급 변경되지는 않습니다 — 새 롤아웃(새 Pod 오브젝트)이 이를 재평가합니다.

태그와 무관하게 `Always` pull을 강제하는 방법은 다음과 같습니다.

- `imagePullPolicy: Always`를 명시적으로 설정한다.
- `:latest`나 태그 미지정을 쓰면서 필드를 생략한다(위 기본 규칙에 의존).
- 클러스터 전역으로 [`AlwaysPullImages`](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/) 어드미션 컨트롤러를 켠다. Pod가 지정한 정책을 덮어써 모든 컨테이너가 레지스트리에 대해 재검증하도록 강제한다.

### IfNotPresent의 digest 재검증 뉘앙스 (K8s v1.33+)

이것은 미묘하고 역사적으로 문서화가 부족했던, Kubernetes가 최근 능동적으로 강화해 온 동작입니다. `IfNotPresent`가 "바이트를 재다운로드하지 않는다"를 넘어 "권한 확인을 건너뛴다"로 새면 안 된다는 것이 요지입니다.

**v1.33 이전의 갭**: `imagePullPolicy: IfNotPresent`에서 "이미 로컬에 있음"은 순전히 노드의 로컬 이미지 저장소에 대한 이미지 신원(digest/참조)으로만 확인됐고, **요청하는 Pod가 그 이미지에 대한 유효 자격을 실제로 가졌는지는 재검증하지 않았습니다.** 이것이 10년 넘게 [kubernetes/kubernetes#18787](https://github.com/kubernetes/kubernetes/issues/18787)로 추적된 실질적 멀티테넌시 보안 구멍을 만들었습니다.

```mermaid
graph TD
    A["Pod A (네임스페이스 X)<br/>imagePullSecrets: validSecret 보유"]
    A -->|"foo:v1 정상 pull"| cache[("Node1 로컬 이미지 캐시<br/>foo:v1 저장됨")]
    B["Pod B (네임스페이스 Y)<br/>imagePullSecrets 없음, 같은 Node1"]
    B -->|"foo:v1 요청 · IfNotPresent"| check{"kubelet:<br/>이미지 이미 캐시됨?"}
    cache -.-> check
    check -->|"예 → pull 통째로 생략"| leak["Pod B 컨테이너가<br/>그 프라이빗 이미지로 시작<br/><b>권한 없이 획득</b>"]
```

**해결 — feature gate `KubeletEnsureSecretPulledImages`, Kubernetes v1.33(2025년 5월) Alpha**: 켜면, `IfNotPresent`(그리고 이미지가 이미 있을 때의 `Never`)의 캐시 히트 경로가 더 이상 "이 digest가 디스크에 있는가"만 확인하지 않습니다 — 실제 바이트는 재다운로드하지 않되, **요청 Pod 자신의 자격(imagePullSecrets)이 그 이미지 pull에 유효한지**를 추가로 검증합니다. 구체적으로:

- 이미지가 *없으면*: Pod 자격으로 정상 pull — 기존 동작과 동일.
- 이미지가 *있으면*: kubelet이 캐시된 이미지로 컨테이너를 시작하도록 허용하기 전에 **자격 확인**("이 Pod의 자격이 지금 이 이미지를 pull할 권한이 있는가")을 수행합니다. 레이어 바이트를 재전송하지는 않지만(콘텐츠 주소 지정 캐시 재사용은 보존됨 — 이건 재다운로드가 아니라 권한 확인입니다), 레지스트리에 대한 성공적 인증 핸드셰이크(또는 유효하고 아직 신선한 자격 확인 결과 캐시)가 필요합니다.
- 모든 Pod 시작마다 재인증하는 성능 저하를 피하기 위해, 자격 검증 결과는 캐시됩니다. **동일 자격(예: 같은 Secret에서 온)을 제시하는 Pod들은 매 pull마다 재인증할 필요가 없으며**, 이 캐시는 기반 Secret이 로테이션되면 올바르게 무효화됩니다.
- `Always` 정책 동작은 이 기능의 영향을 받지 않습니다 — 정의상 이미 매 기동 때 레지스트리에 대해 재인증·재해석하므로(§세 가지 값) 애초에 이 갭이 없었습니다.

digest/콘텐츠 매치는 여전히 필요하지만 더 이상 충분하지 않으며, 캐시 히트 경로에서도 자격 유효성을 재확인합니다.

### ImagePullBackOff / ErrImagePull 상태

둘 다 `kubectl describe pod` / `kubectl get pod` 출력에 표면화되는 컨테이너 `Waiting` 상태 사유이며, kubelet이 필요한 이미지를 성공적으로 pull하지 못했음을 뜻합니다. 다만 재시도 라이프사이클의 서로 다른 지점을 나타냅니다.

- **`ErrImagePull`** — 이미지 pull 시도가 처음 실패했을 때 kubelet이 보고하는 *즉각적* 오류 이벤트/상태. 백오프가 적용되지 않은 원시 실패 신호입니다.
- **`ImagePullBackOff`** — 한 번 이상의 `ErrImagePull` 실패 뒤, kubelet은 매 조정 루프마다 레지스트리를 두드리지 않고 **지수 백오프** 재시도 일정에 들어갑니다. 시도 간 지연이 컴파일된 상한 **300초(5분)**까지 늘어납니다. `ImagePullBackOff`는 이 "재시도 대기" 상태에서 보이는 상태로, "실패했고 다음 시도 전 대기 중"을 뜻하지 별개의 새 실패 유형이 아닙니다.

두 상태의 공통 원인(둘은 같은 근본 원인을 공유하며, 실패가 재시도에도 지속될 때 보이는 것이 `ImagePullBackOff`)은 다음과 같습니다.

- 잘못되거나 오타 난 이미지 이름·태그(오타, 틀린 레지스트리 경로, 또는 태그가 실제로 존재하지 않음).
- 유효한 `imagePullSecrets` 참조 없이 프라이빗 레지스트리 이미지 pull(또는 크리덴셜 프로바이더 플러그인 오설정) — Bearer 토큰 교환 단계의 인증 실패.
- 노드에서 레지스트리로의 네트워크 연결 문제(DNS 해석 실패, 아웃바운드를 막는 방화벽/보안 그룹 규칙, NAT 게이트웨이/VPC 엔드포인트 없는 프라이빗 서브넷 노드의 인터넷 접근 부재).
- 레지스트리 측 문제: rate limiting, 레지스트리 장애, 또는 Pod 명세 작성 후 레지스트리에서 이미지/태그가 삭제됨.
- digest 불일치 또는 미지원 플랫폼(예: arm64 노드에 스케줄됐는데 Image Index에 arm64 manifest가 없음).

## 이미지 pull 병렬성 / 직렬화

**한 줄 요지: kubelet은 기본적으로 이미지를 한 번에 하나씩 직렬로 pull하며, `serializeImagePulls: false` + `maxParallelImagePulls`로 노드 단위 동시 pull 상한을 열 수 있습니다. 이는 디스크 I/O·네트워크 경합을 막기 위한 것으로, 요청 발행 속도 제한(`--registry-qps`)과는 별개 축입니다.**

### 기본 동작 — 기본이 직렬

기본적으로 kubelet은 이미지를 직렬로 pull합니다. 이미지 서비스에 한 번에 하나의 pull 요청만 보냅니다.

> By default, the kubelet pulls images serially. In other words, the kubelet sends only one image pull request to the image service at a time.

역사적으로, 그리고 기본값으로, 노드가 각기 다른(아직 캐시 안 된) 이미지를 참조하는 새 Pod 10개를 동시에 띄워야 하면, kubelet은 그 10개 pull 요청을 큐에 넣고 **한 번에 하나씩** 처리합니다 — 밑의 컨테이너 런타임(containerd)과 네트워크·디스크가 원리상 여러 동시 다운로드를 감당할 수 있더라도 그렇습니다.

### KubeletConfiguration 필드: serializeImagePulls와 maxParallelImagePulls

```yaml
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
serializeImagePulls: false
maxParallelImagePulls: 3
```

- **`serializeImagePulls`** (boolean) — 역사적으로 `true`(직렬, 한 번에 하나 — 위 기본 동작)가 기본값이었습니다. `false`로 두면 병렬 경로가 켜집니다.
- **`maxParallelImagePulls`** (integer) — `serializeImagePulls: false`일 때 kubelet이 동시에 진행할 최대 이미지 pull 수입니다. [KEP-3673](https://github.com/kubernetes/enhancements/blob/master/keps/sig-node/3673-kubelet-parallel-image-pull-limit/README.md)의 일부로 도입됐습니다.

<details markdown="1">
<summary>심화: 검증 규칙, 스코프 뉘앙스, KEP-3673 승격 일정</summary>

**검증 규칙**(kubelet 설정 로드 시점에 강제):

- `serializeImagePulls: true`(또는 기본값)면 `maxParallelImagePulls`는 미설정이거나 정확히 `1`이어야 한다 — `> 1` 값을 `serializeImagePulls: true`와 조합하면 모순 설정으로 검증 실패.
- `serializeImagePulls: false`면 `maxParallelImagePulls`는 `> 0`이어야 한다 — `0`이나 음수는 검증 실패. `serializeImagePulls: false` 아래 `1`은 기능상 직렬과 동일하며 단지 새 필드로 표현한 것.
- 두 필드를 모두 미설정으로 두면 kubelet은 원래 기본값을 유지한다: 사실상 직렬(`maxParallelImagePulls`가 `1`처럼 동작). 업그레이드하는 기존 클러스터가 조용히 동작을 바꾸지 않도록 하기 위함.

**스코프 뉘앙스**(Kubernetes 문서가 직접 확인): 병렬성은, 켜졌을 때, **같은 노드의 서로 다른 Pod/컨테이너 이미지 pull 사이**에 적용되지, 하나의 멀티컨테이너 Pod 안 여러 이미지를 그 한 Pod를 위해 동시에 가져오는 데 적용되지 않는다.

> The kubelet never pulls multiple images in parallel on behalf of one Pod.

**KEP-3673 승격 일정**: Kubernetes v1.27 Alpha, v1.28+ Beta(블로킹/큐잉 동작의 e2e 커버리지 확대와 함께), GA(stable)는 v1.35 착지 — 이 enhancement의 추적된 승격 기준 기준.

</details>

### 무제한 병렬성이 노드를 조이는 이유

KEP-3673의 동기 절은, 기존 kubelet 플래그가 실제로는 풀지 못했던 혼동하기 쉬운 두 문제를 짚습니다.

1. **레지스트리 요청 QPS/버스트 제한(`--registry-qps`, `--registry-burst`)은 컨테이너 런타임에 pull *요청을 발행하는 속도*만 조절하지, 몇 개가 동시에 *진행 중*인지는 제한하지 않습니다.** 낮은 QPS 설정이라도 동시에 진행 중인 장시간 pull이 많은 상황(예: 수 GB짜리 큰 이미지 여럿이 동시에 다운로드 중)과 공존할 수 있습니다. QPS는 요청 개시 속도를 다스리지 진행 중 작업량을 다스리지 않기 때문입니다.
2. **동시 진행 pull에 대한 노드 레벨 상한이 (`maxParallelImagePulls` 이전에는) 아예 없었습니다** — kubelet도 컨테이너 런타임도 강제하지 않았습니다. 그래서 콜드(캐시 안 된) 이미지를 가진 새 Pod가 몰리면 모두 한꺼번에 다운로드를 시작해, 같은 유한한 노드 리소스를 두고 경쟁했습니다.
   - **디스크 I/O 경합** — 동시 pull마다 압축 해제된 레이어 tarball을 노드의 로컬 이미지 저장소에 동시에 쓴다.
   - **네트워크 대역폭 경합** — 동시 pull마다 레지스트리로의 아웃바운드 대역폭을 소모한다. 너무 많으면 모두의 처리량이 떨어진다(그리고 노드의 다른 트래픽도).
   - 지속적 압박 아래에서는 같은 노드의 무관한 Pod 시작을 늦추거나 멈추게 하고, 극단적으로는 노드 레벨 리소스 고갈에 기여한다.

`maxParallelImagePulls` 세마포어(KEP 설계에 따라 설정값 크기의 채널 기반 게이트로 구현)는 요청 발행 QPS와 독립적으로 동시 진행 pull을 직접 제한해, 요청 속도 스로틀만이 아니라 진짜 노드 레벨 동시성 상한을 제공합니다.

## 프라이빗 레지스트리 실무: 미러와 crictl

**한 줄 요지: pull-through 캐시(레지스트리 미러)는 노드와 업스트림 레지스트리 사이에서 blob을 캐시해 레이턴시·대역폭·rate limit을 완화하고, `crictl`은 kubelet을 우회해 노드의 런타임에 직접 pull을 시켜 문제를 격리합니다.**

### 레지스트리 미러 / pull-through 캐시

**pull-through 캐시**(레지스트리 미러)는 노드와 업스트림 레지스트리(예: Docker Hub) 사이에 놓여, blob이 처음 요청될 때 투명하게 캐시합니다. 그래서 같은 digest를 이후에 pull하면 — 미러 뒤의 어느 노드에서든 — 인터넷 너머 업스트림에서 다시 가져오는 대신 로컬에서 서빙됩니다.

**containerd**에서 현재 권장되는 메커니즘은 `hosts.toml` 호스트 설정 레이아웃입니다(구형 단일 파일 `config.toml`의 `registry.mirrors` 블록은 이것을 위해 deprecated).

1. containerd를 설정 디렉터리로 향하게 합니다.
   ```toml
   # /etc/containerd/config.toml
   [plugins."io.containerd.grpc.v1.cri".registry]
     config_path = "/etc/containerd/certs.d"
   ```
2. 그 디렉터리 아래에 업스트림 레지스트리 호스트명별 하위 디렉터리를 만들고, 각각 `hosts.toml`을 둡니다.
   ```
   /etc/containerd/certs.d/docker.io/hosts.toml
   ```
   ```toml
   server = "https://registry-1.docker.io"

   [host."https://local-mirror.example.com"]
     capabilities = ["pull"]

   [host."https://us-mirror.example.com"]
     capabilities = ["pull"]
   ```
   containerd는 나열된 미러 호스트를 순서대로 시도하고, 하나가 실패하면 다음 항목(그리고 최종적으로 실제 업스트림인 `server`)으로 폴백합니다.

이 `certs.d`/`hosts.toml` 레이아웃이 레거시 `config.toml` 내장 미러 목록보다 나은 핵심 운영 이점은 다음과 같습니다. **`/etc/containerd/certs.d/` 아래 갱신은 containerd 데몬 재시작 없이 반영됩니다.**

Kubernetes 클러스터에서 미러를 쓰는 동기는, pull당 레이턴시 감소(먼 공개 레지스트리 대신 가까운/로컬 캐시에서 서빙), 아웃바운드 대역폭 비용 절감, 업스트림 레지스트리가 잠시 도달 불가일 때의 복원력 향상, 그리고 트래픽을 인증된/캐시된 경로로 몰아 Docker Hub의 익명/IP당 rate limit을 피하는 것입니다.

> [!NOTE] 이미지 pull 타임아웃
> 길거나 멈춘 pull(큰 이미지, 느린/스로틀된 레지스트리, 네트워크 문제)은 kubelet/런타임의 pull 타임아웃을 넘겨 `ErrImagePull`/`ImagePullBackOff` 사이클로 이어질 수 있습니다. 레지스트리 미러, 적절한 `maxParallelImagePulls` 튜닝(노드 레벨 경합 회피), 그리고 이미지를 작게(레이어를 적고 작게) 유지하는 것이 표준 완화책입니다.

### crictl pull — 수동 테스트

`crictl`은 kubelet/Kubernetes API를 거치지 않고 노드의 컨테이너 런타임(containerd, CRI-O)을 직접 실행하는 CRI 호환 CLI입니다. 트러블슈팅 중 "이게 Kubernetes 스케줄링/인증 문제인가, 아니면 노드 레벨의 원시 레지스트리 연결/자격 문제인가"를 가리는 데 유용합니다.

기본 사용:

```bash
crictl pull busybox
```

명시적 자격으로(Kubernetes가 관리하는 `imagePullSecrets`/크리덴셜 프로바이더 배선을 통째로 우회해 원시 레지스트리 인증을 테스트):

```bash
sudo crictl pull --creds username:password private-registry.com/myapp:v1.0
```

디버그 상세 pull(실제로 어떤 manifest/blob 요청이 나가는지 보기에 유용):

```bash
sudo crictl --debug pull nginx:latest
```


pull된 이미지가 로컬 이미지 저장소에 안착했는지 확인하고 메타데이터(config, digest 등 — OCI config JSON 필드)를 조사:

```bash
crictl inspecti busybox
```



`crictl`은 런타임 소켓 엔드포인트를 `/etc/crictl.yaml`(또는 `--runtime-endpoint`/`--image-endpoint` 플래그)에서 읽어, 로컬 containerd/CRI-O gRPC 소켓을 가리킵니다.

## 핵심 값 요약

이 글에서 다룬 미디어 타입·엔드포인트·기본값·필드를 한 곳에 모으면 다음과 같습니다.

| 개념 | 정확한 값 / 이름 |
|---|---|
| OCI manifest 미디어 타입 | `application/vnd.oci.image.manifest.v1+json` |
| OCI config 미디어 타입 | `application/vnd.oci.image.config.v1+json` |
| OCI image index 미디어 타입 | `application/vnd.oci.image.index.v1+json` |
| 레이어 미디어 타입(gzip) | `application/vnd.oci.image.layer.v1.tar+gzip` |
| digest 형식 | `sha256:<64자리 hex>` |
| Distribution API 기본 확인 | `GET /v2/` → `200 OK` |
| manifest pull | `GET /v2/<name>/manifests/<reference>` |
| blob pull | `GET /v2/<name>/blobs/<digest>` |
| 콘텐츠 digest 헤더 | `Docker-Content-Digest` |
| 인증 챌린지 헤더 | `WWW-Authenticate: Bearer realm=...,service=...,scope=...` |
| 인증 헤더(재시도 요청) | `Authorization: Bearer <token>` |
| Docker Hub 익명 제한 | 6시간당 100회 / IP |
| Docker Hub 무료 인증 제한 | 6시간당 200회 |
| K8s 태그 정규식 | `[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}` (최대 128자) |
| 기본 정책: `:latest`/태그 미지정 | `imagePullPolicy: Always` |
| 기본 정책: 명시적 non-latest 태그 또는 digest | `imagePullPolicy: IfNotPresent` |
| ImagePullBackOff 최대 백오프 | 300초 |
| 병렬 pull 필드 | `serializeImagePulls` (bool), `maxParallelImagePulls` (int) — KubeletConfiguration v1beta1 |
| 자격 캐시 재검증 (K8s v1.33 alpha) | feature gate `KubeletEnsureSecretPulledImages` |
| kubelet 크리덴셜 프로바이더 플래그 | `--image-credential-provider-config`, `--image-credential-provider-bin-dir` |
| 수동 pull/디버그 도구 | `crictl pull`, `crictl inspecti` |
| containerd 미러 설정 디렉터리 | `/etc/containerd/certs.d/<registry-host>/hosts.toml` |

## 참고 자료

- OCI, [Image Format Specification](https://github.com/opencontainers/image-spec/blob/main/spec.md) (manifest·config·image-index 하위 문서 포함)
- OCI, [Distribution Specification](https://github.com/opencontainers/distribution-spec/blob/main/spec.md)
- Distribution, [Token Authentication Specification](https://distribution.github.io/distribution/spec/auth/token/)
- Kubernetes, [Images](https://kubernetes.io/docs/concepts/containers/images/)
- Kubernetes, [Configure a kubelet image credential provider](https://kubernetes.io/docs/tasks/administer-cluster/kubelet-credential-provider/)
- Kubernetes, [Debugging Kubernetes nodes with crictl](https://kubernetes.io/docs/tasks/debug/debug-cluster/crictl/)
- Kubernetes Blog, [Kubernetes v1.33: Image Pull Policy the way you always thought it worked!](https://kubernetes.io/blog/2025/05/12/kubernetes-v1-33-ensure-secret-pulled-images-alpha/)
- kubernetes/kubernetes, [Issue #18787](https://github.com/kubernetes/kubernetes/issues/18787)
- Kubernetes Enhancements, [KEP-3673: kubelet parallel image pull limit](https://github.com/kubernetes/enhancements/blob/master/keps/sig-node/3673-kubelet-parallel-image-pull-limit/README.md)
- Docker, [Docker Hub usage and limits](https://docs.docker.com/docker-hub/usage/pulls/)
- containerd, [Registry Configuration — hosts.md](https://github.com/containerd/containerd/blob/main/docs/hosts.md)
- AWS, [Using Amazon ECR Images with Amazon EKS](https://docs.aws.amazon.com/AmazonECR/latest/userguide/ECR_on_EKS.html)
- AWS, [IAM roles for service accounts (IRSA)](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
- awslabs, [amazon-ecr-credential-helper](https://github.com/awslabs/amazon-ecr-credential-helper)
- Google Cloud, [Authenticate to Google Cloud APIs from GKE workloads](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
