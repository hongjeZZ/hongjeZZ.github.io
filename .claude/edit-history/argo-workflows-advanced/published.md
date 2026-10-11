---
title: "Argo Workflows 고급 운영 패턴 정리 - 2"
date: 2026-06-28 14:57:01 +0900
categories: [Infra, Kubernetes]
tags: [TIL, Argo Workflows, Kubernetes, 재시도, 동시성, 메모이제이션, RBAC]
source_wiki: argo-workflows-advanced
provenance: cite-only
---

![Argo Workflows](/assets/img/argo-workflows/cover.png)

{% raw %}

[Argo Workflows](https://argo-workflows.readthedocs.io/en/latest/)를 프로덕션에서 운영하려면 워크플로우를 정의하는 것 이상이 필요합니다. 스텝이 실패했을 때 어떻게 재시도할지, 동시에 몇 개까지 돌릴지, 비싼 연산 결과를 어떻게 캐시할지, 누구에게 어떤 권한을 줄지, 컨트롤러가 대규모 부하에서 버티도록 어떻게 튜닝할지 — 이런 운영 관심사가 별도의 설정 레이어로 존재합니다.

이 글은 Argo Workflows 공식 문서의 운영 패턴을 정리한 노트입니다. 재시도·오류 처리, 동시성 제어(Mutex·Semaphore), 메모이제이션, 보안·RBAC, 성능·스케일링을 실제 YAML과 함께 다룹니다. 컨트롤러·CRD·템플릿 타입 같은 기본 아키텍처는 [1편](/posts/argo-workflow/)에서 다뤘습니다. 아래 내용은 v3.5~v3.6에서 추가된 기능까지 포함합니다.

> [!NOTE] 전제 지식
> Workflow·WorkflowTemplate·CronWorkflow 같은 CRD의 기본 구조와 템플릿(Container·Script·Steps·DAG) 개념을 안다고 가정합니다. 이 개념들은 [1편](/posts/argo-workflow/)에서 정리했습니다.

## 재시도와 오류 처리

스텝은 여러 이유로 실패합니다. 컨테이너가 비정상 종료 코드로 끝나기도 하고, 노드가 드레인되거나 스팟 인스턴스가 회수되기도 하며, 네트워크나 외부 API가 일시적으로 흔들리기도 합니다. `retryStrategy`는 이런 실패를 어떤 조건에서 몇 번, 얼마의 간격으로 다시 시도할지 선언하는 필드입니다. 단순한 횟수 제한을 넘어 종료 코드·상태·실행 시간·오류 메시지를 조합한 조건부 재시도(v3.2+)와 지수 백오프를 함께 걸 수 있습니다.

### retryStrategy 전체 필드

`retryStrategy`는 템플릿 레벨에 붙습니다. 재시도 횟수 상한, 재시도 정책, 백오프, 재시도 노드 배치까지 한 블록에 담깁니다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: retry-demo-
spec:
  entrypoint: retry-example
  templates:
  - name: retry-example
    retryStrategy:
      limit: "5"                  # 최대 재시도 횟수 (문자열 또는 정수)
      retryPolicy: "OnTransientError"  # Always | OnFailure | OnError | OnTransientError
      backoff:
        duration: "2s"            # 첫 번째 재시도 대기 시간 (필수)
        factor: "2"               # 지수 백오프 배율
        maxDuration: "1m"         # 최대 대기 시간 상한
      affinity:
        nodeAntiAffinity: {}      # 재시도를 다른 노드에서 실행
    container:
      image: alpine:3.18
      command: [sh, -c]
      args: ["exit 1"]
```

`backoff.duration`은 필수이며 첫 재시도까지 대기하는 시간입니다. `factor`가 지수 배율이고 `maxDuration`이 대기 시간 상한입니다. `affinity.nodeAntiAffinity`를 두면 재시도가 실패한 노드를 피해 다른 노드에서 실행됩니다.

### retryPolicy 옵션 비교

`retryPolicy`는 어떤 종류의 실패를 재시도 대상으로 볼지 정합니다. 네 가지 값이 있고, 무엇을 잡느냐가 다릅니다.

| 값 | 설명 | 사용 시점 |
|---|---|---|
| `OnFailure` | 컨테이너 종료 코드가 비정상(기본값) | 명시적 실패만 재시도 |
| `Always` | 실패와 에러 모두 재시도 | expression 사용 시 v3.5+ 기본값 |
| `OnError` | Argo 컨트롤러 오류, init/wait 컨테이너 실패 | 인프라 문제 처리 |
| `OnTransientError` | 일시적 오류(v3.0+), `TRANSIENT_ERROR_PATTERN` env 패턴 매칭 | 네트워크·API 일시 오류 |

`OnFailure`가 기본값으로 컨테이너가 비정상 종료 코드로 끝난 경우만 재시도합니다. `OnError`는 컨트롤러 오류나 init/wait 컨테이너 실패 같은 인프라 문제를 잡습니다. `OnTransientError`는 v3.0에서 추가됐고 `TRANSIENT_ERROR_PATTERN` 환경 변수의 패턴에 매칭되는 오류를 일시적 오류로 분류합니다.

### expression 기반 조건부 재시도 (v3.2+)

`expression` 필드는 v3.2에서 추가됐고, 종료 코드·상태·실행 시간·오류 메시지를 조합해 재시도 여부를 세밀하게 결정합니다. 표현식에서 쓸 수 있는 변수는 네 가지입니다.

| 변수 | 타입 | 설명 |
|---|---|---|
| `lastRetry.exitCode` | string | 마지막 재시도 종료 코드 (불가 시 "-1") |
| `lastRetry.status` | string | "Error" 또는 "Failed" |
| `lastRetry.duration` | string | 마지막 재시도 실행 시간(초) |
| `lastRetry.message` | string | 출력 메시지 (v3.5+) |

```yaml
retryStrategy:
  limit: "10"
  retryPolicy: "Always"   # expression 사용 시 Always 권장
  expression: >
    asInt(lastRetry.exitCode) >= 2 &&
    lastRetry.status != "Error"
  backoff:
    duration: "5s"
    factor: "2"
    maxDuration: "10m"
```

`expression`을 지정하면 `retryPolicy`를 `Always`로 두는 것이 권장됩니다(v3.5부터 이때 기본값이 `Always`로 바뀌었습니다). 실무에서 자주 쓰는 표현식은 다음과 같습니다.

- `asInt(lastRetry.exitCode) == 1` — 종료 코드 1에서만 재시도
- `lastRetry.duration < "300"` — 300초 미만 실행 시에만 재시도 (무한 루프 방지)
- `"OOM" in lastRetry.message` — OOM 오류 메시지 포함 시 재시도 (v3.5+)

### onExit 핸들러 — 항상 실행되는 후처리

`onExit` 핸들러는 워크플로우가 성공·실패·오류 어느 경우에도 실행되는 후처리 템플릿입니다. 알림 발송, 리소스 정리, 감사 로그를 남길 때 사용합니다. 핸들러 안에서 `{{workflow.status}}` 변수로 성공/실패를 분기합니다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: exit-handler-demo-
spec:
  entrypoint: main
  onExit: cleanup-handler       # 워크플로우 종료 시 항상 실행
  templates:
  - name: main
    steps:
    - - name: do-work
        template: flaky-job

  - name: flaky-job
    container:
      image: alpine:3.18
      command: [sh, -c]
      args: ["exit 1"]

  - name: cleanup-handler
    steps:
    - - name: notify
        template: send-notification
        when: "{{workflow.status}} != Succeeded"

  - name: send-notification
    container:
      image: curlimages/curl:8.6.0
      command: [sh, -c]
      args: ["echo 'Workflow {{workflow.name}} ended with {{workflow.status}}'"]
```

### failFast — 병렬 실패 시 즉시 중단

`failFast`는 병렬 실행 중 하나가 실패했을 때 나머지를 즉시 취소할지 정합니다. `steps`/`dag` 템플릿에서 **기본값이 `true`**이므로, 병렬 태스크 하나가 실패하면 나머지가 자동으로 취소됩니다. 이 동작을 끄려면 각 태스크에 `continueOn.failed: true`를 지정합니다.

```yaml
templates:
- name: parallel-steps
  steps:
  - - name: job-a
      template: worker
    - name: job-b        # job-b 실패 시 job-a도 즉시 취소
      template: worker
  parallelism: 2

spec:
  # 전체 워크플로우 레벨 failFast
  # dag/steps 템플릿 내 개별 태스크에는 failFast가 없음
  # 대신 activeDeadlineSeconds로 전체 시간 제한 가능
  activeDeadlineSeconds: 300
```

### Pod Disruption 처리 — 스팟 인스턴스·노드 드레인

노드 드레인이나 스팟 인스턴스 회수는 명시적 실패가 아니라 중단입니다. 이런 중단을 일시적 오류로 분류해 자동 재시도하려면 `retryPolicy: "OnError"`와 `TRANSIENT_ERROR_PATTERN` 환경 변수를 조합합니다.

```yaml
spec:
  templates:
  - name: long-running-job
    retryStrategy:
      limit: "3"
      retryPolicy: "OnError"   # 컨트롤러가 Pod 실패를 Error로 감지
    podDisruptionBudget:        # 워크플로우 레벨에서 PDB 설정 가능
      minAvailable: 1
    container:
      image: alpine:3.18
      command: [sh, -c]
      args: ["sleep 300"]
```

`TRANSIENT_ERROR_PATTERN`은 컨트롤러 ConfigMap의 executor 환경 변수로 설정합니다. 파이프로 구분한 패턴 중 하나라도 오류 메시지에 포함되면 일시적 오류로 분류됩니다.

```yaml
# workflow-controller-configmap
data:
  config: |
    executor:
      envVars:
        - name: TRANSIENT_ERROR_PATTERN
          value: "transient|timeout|429|503"
```

## 동시성 제어

동시성 제어는 한 번에 실행되는 워크플로우나 스텝의 수를 제한하는 장치입니다. 공유 데이터베이스 마이그레이션처럼 동시에 하나만 돌아야 하는 작업, 또는 외부 시스템 부하 때문에 동시 실행 수를 N개로 묶어야 하는 작업에 씁니다. 잠금은 한 번에 하나만 허용하는 Mutex와 N개까지 허용하는 Semaphore 두 종류로 나뉩니다.

### Mutex — 단일 잠금

Mutex는 동시에 워크플로우 또는 템플릿 하나만 실행되도록 보장합니다. Semaphore와 달리 ConfigMap이 필요 없고 이름만 지정하면 됩니다.

```yaml
# 워크플로우 레벨 Mutex (네임스페이스 내)
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: mutex-demo-
  namespace: argo
spec:
  synchronization:
    mutexes:
      - name: db-migration    # ConfigMap 불필요, 이름만 지정
  entrypoint: main
  templates:
  - name: main
    container:
      image: alpine:3.18
      command: [echo]
      args: ["Running exclusive migration"]
```

### Semaphore — N개 동시 실행 제한

Semaphore는 동시 실행 수를 N개로 제한합니다. 허용 개수를 ConfigMap 키에 정의하고, 워크플로우가 그 키를 참조합니다.

```yaml
# 1. ConfigMap으로 세마포어 크기 정의
apiVersion: v1
kind: ConfigMap
metadata:
  name: semaphore-config
  namespace: argo
data:
  max-parallel-jobs: "3"      # 동시 3개까지 허용
  etl-workers: "2"

---
# 2. 워크플로우 레벨 세마포어
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: semaphore-demo-
spec:
  synchronization:
    semaphores:
      - configMapKeyRef:
          name: semaphore-config
          key: max-parallel-jobs
  entrypoint: main
  templates:
  - name: main
    container:
      image: alpine:3.18
      command: [echo]
      args: ["Working..."]
```

### 템플릿 레벨 세마포어

Semaphore를 워크플로우가 아니라 템플릿에 걸면, 여러 워크플로우에 걸쳐 특정 템플릿의 동시 실행 수를 클러스터 전체에서 제한할 수 있습니다. 예를 들어 `etl-workers: "2"`로 지정하면, 어느 워크플로우에서 실행되든 해당 템플릿이 동시에 2개를 넘지 않습니다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: tmpl-semaphore-
spec:
  entrypoint: fan-out
  templates:
  - name: fan-out
    steps:
    - - name: worker
        template: heavy-task
        withItems: [a, b, c, d, e]

  - name: heavy-task
    synchronization:
      semaphores:
        - configMapKeyRef:
            name: semaphore-config
            key: etl-workers   # 전체 워크플로우 중 이 템플릿은 최대 2개 동시 실행
    container:
      image: alpine:3.18
      command: [sh, -c]
      args: ["sleep 10"]
```

### 데이터베이스 기반 잠금 (멀티 컨트롤러, v3.6+)

ConfigMap 기반 잠금은 단일 컨트롤러 안에서만 유효합니다. 여러 Argo Workflows 컨트롤러 인스턴스가 같은 클러스터에 존재하면 컨트롤러 간에 잠금이 공유되지 않습니다. v3.6부터 [PostgreSQL](https://www.postgresql.org/)/[MySQL](https://www.mysql.com/)을 잠금 저장소로 쓰면 컨트롤러 간 뮤텍스·세마포어를 공유할 수 있습니다.

```yaml
# workflow-controller-configmap
data:
  syncConfig: |
    driver: postgres
    host: postgres-host
    port: 5432
    database: argo
    username: argo_user
    passwordSecret:
      name: postgres-secret
      key: password
    stateTableName: sync_state      # 기본값
    limitTableName: sync_limit      # 기본값
    controllerTableName: sync_controller

---
# 데이터베이스 Mutex 사용
spec:
  synchronization:
    mutexes:
      - name: global-lock
        database: true     # 이 플래그로 DB 기반 잠금 선택
```

`database: true` 플래그로 DB 기반 잠금을 선택합니다. `stateTableName`·`limitTableName`은 기본값이 각각 `sync_state`·`sync_limit`입니다. DB 상태는 직접 조회할 수 있습니다.

```sql
-- 현재 잠금 대기 중인 워크플로우 확인
SELECT * FROM sync_state WHERE held = false ORDER BY priority DESC, time ASC;
```

### parallelism 계층 구조

`parallelism`은 동시 실행 수 상한을 거는 또 다른 축이며, 네 개의 계층에 각각 존재합니다. 상위 계층이 하위 전체를 덮습니다.

- 컨트롤러 전역 `parallelism`: 컨트롤러 내 동시 워크플로우 수
- `namespaceParallelism`: 네임스페이스당 동시 워크플로우 수
- 워크플로우 레벨 `spec.parallelism`: 해당 워크플로우 내 최대 동시 Pod 수
- 템플릿 레벨 `parallelism`: steps/dag 내 동시 실행 스텝 수

```yaml
# 워크플로우 레벨 — 이 워크플로우 내 최대 동시 Pod 수
spec:
  parallelism: 5

  # 템플릿 레벨 — steps/dag 내 동시 실행 수
  templates:
  - name: fan-out
    parallelism: 3         # 최대 3개 스텝 동시 실행
    steps:
    - - name: task
        template: worker
        withParam: "{{workflow.parameters.items}}"
```

컨트롤러 전역 제한은 `workflow-controller-configmap`에 둡니다.

```yaml
data:
  parallelism: "50"          # 전체 컨트롤러 내 동시 워크플로우 수
  namespaceParallelism: "10" # 네임스페이스당 동시 워크플로우 수
```

## 메모이제이션

메모이제이션은 비용이 큰 연산의 결과를 캐시해 중복 실행을 막는 기능입니다. 같은 입력으로 다시 실행되면 컨테이너를 띄우지 않고 저장된 output을 바로 반환합니다(Cache Hit). 캐시 저장소로는 ConfigMap을 씁니다. 모델 학습, 대용량 데이터 처리처럼 같은 입력에 같은 결과가 나오는 결정적 연산에 적합합니다.

### 기본 설정

캐시용 ConfigMap에는 반드시 `workflows.argoproj.io/configmap-type: Cache` 레이블이 있어야 합니다.

```yaml
# 1. 캐시용 ConfigMap 생성 (반드시 레이블 필요)
apiVersion: v1
kind: ConfigMap
metadata:
  name: ml-model-cache
  labels:
    workflows.argoproj.io/configmap-type: Cache  # 필수 레이블
```

`memoize` 블록은 캐시 키, 유효기간(`maxAge`), 캐시 저장소를 지정합니다.

```yaml
# 2. 메모이제이션이 적용된 워크플로우
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: memoized-ml-
spec:
  entrypoint: train-model
  templates:
  - name: train-model
    inputs:
      parameters:
      - name: dataset-version
      - name: hyperparams
    memoize:
      key: "{{inputs.parameters.dataset-version}}-{{inputs.parameters.hyperparams}}"
      maxAge: "24h"           # 캐시 유효기간 (s/m/h 단위)
      cache:
        configMap:
          name: ml-model-cache
    container:
      image: python:3.11
      command: [python]
      args: [train.py]
      resources:
        requests:
          cpu: "4"
          memory: 16Gi
    outputs:
      parameters:
      - name: model-accuracy
        valueFrom:
          path: /tmp/accuracy.txt
```

### 캐시 키 설계 전략

캐시 키가 너무 광범위하면 서로 다른 입력이 같은 키를 공유해 캐시가 오염됩니다. 입력 파라미터를 조합해 고유 키를 만들어야 합니다.

```yaml
# 나쁜 예: 너무 광범위한 키 → 캐시 오염
memoize:
  key: "model-v1"

# 좋은 예: 입력 파라미터 조합으로 고유 키 생성
memoize:
  key: "{{inputs.parameters.dataset}}-{{inputs.parameters.model-type}}-{{inputs.parameters.version}}"

# 날짜 기반 키 (일별 캐시 갱신)
memoize:
  key: "daily-report-{{workflow.creationTimestamp.Y}}-{{workflow.creationTimestamp.m}}-{{workflow.creationTimestamp.d}}"
  maxAge: "25h"
```

### 캐시 히트/미스 동작

캐시 상태에 따른 동작은 다음과 같습니다.

- **Cache Hit**: 이전에 저장된 output을 그대로 반환. 컨테이너 실행하지 않음.
- **Cache Miss**: 템플릿 정상 실행 후 결과를 ConfigMap에 저장.
- **maxAge 만료**: 만료된 항목은 무시되고 재실행 후 갱신.
- **v3.5 이전**: output이 없는 템플릿에는 memoize 불가.
- **v3.5+**: 모든 템플릿에 memoize 적용 가능.

### 제약사항 — ConfigMap 1MB 한도

ConfigMap 용량 제한은 1MB입니다. 캐시가 누적되어 이 한도를 넘으면 업데이트가 실패합니다. 두 가지 해결책이 있습니다. 캐시를 여러 ConfigMap으로 샤딩하거나, `maxAge`를 짧게 설정해 자동 만료를 유도합니다.

```yaml
# ConfigMap 용량 제한: 1MB
# 해결책 1: 캐시 분리 (다른 ConfigMap 이름 사용)
memoize:
  key: "{{inputs.parameters.shard}}-{{inputs.parameters.id}}"
  cache:
    configMap:
      name: "cache-shard-{{inputs.parameters.shard}}"  # 샤드별 캐시

# 해결책 2: maxAge를 짧게 설정해 자동 만료·삭제 유도
memoize:
  maxAge: "1h"
```

메모이제이션을 쓰는 워크플로우는 ConfigMap에 대한 `get`, `create`, `update` 권한이 필요합니다. `create`와 `update`는 캐시를 새로 쓰고 갱신하는 데 필수입니다.

```yaml
rules:
- apiGroups: [""]
  resources: [configmaps]
  verbs: [get, create, update]   # create, update 필수
```

## 고급 패턴

앞의 기능들 위에 재사용·백그라운드 서비스·스케줄링 제어 같은 패턴을 얹을 수 있습니다. 아래는 운영에서 자주 조합하는 설정 조각입니다.

### WorkflowTemplate 재사용 (Workflow of Workflows)

공통 스텝을 [WorkflowTemplate](https://argo-workflows.readthedocs.io/en/latest/workflow-templates/)에 라이브러리로 정의해 두고, 여러 워크플로우에서 `templateRef`로 참조합니다. Slack 알림, SQL 실행 같은 반복 스텝을 한 곳에 모을 때 씁니다.

```yaml
# 공유 라이브러리 정의
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: shared-steps
  namespace: argo
spec:
  templates:
  - name: send-slack
    inputs:
      parameters:
      - name: message
      - name: channel
    container:
      image: curlimages/curl:8.6.0
      command: [sh, -c]
      args:
      - |
        curl -X POST -H 'Content-type: application/json' \
          --data '{"text":"{{inputs.parameters.message}}","channel":"{{inputs.parameters.channel}}"}' \
          ${SLACK_WEBHOOK_URL}

  - name: run-sql
    inputs:
      parameters:
      - name: query
    script:
      image: postgres:16
      command: [psql]
      args: ["-c", "{{inputs.parameters.query}}"]
      env:
      - name: PGPASSWORD
        valueFrom:
          secretKeyRef:
            name: db-secret
            key: password
```

```yaml
# 재사용하는 워크플로우
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: etl-pipeline-
spec:
  entrypoint: pipeline
  templates:
  - name: pipeline
    steps:
    - - name: extract
        templateRef:
          name: shared-steps
          template: run-sql
        arguments:
          parameters:
          - name: query
            value: "SELECT * FROM orders WHERE date = '{{workflow.parameters.date}}'"
    - - name: notify
        templateRef:
          name: shared-steps
          template: send-slack
        arguments:
          parameters:
          - name: message
            value: "ETL 완료: {{workflow.name}}"
          - name: channel
            value: "#data-eng"
```

### ClusterWorkflowTemplate — 멀티 네임스페이스 공유

`ClusterWorkflowTemplate`은 클러스터 전역에서 접근 가능한 템플릿입니다. 네임스페이스가 없으며, 여러 네임스페이스가 공통으로 쓰는 표준 스텝(보안 스캔 등)을 정의할 때 씁니다. 참조할 때는 `clusterScope: true`가 필수입니다.

```yaml
# 클러스터 전체에서 접근 가능한 템플릿
apiVersion: argoproj.io/v1alpha1
kind: ClusterWorkflowTemplate
metadata:
  name: org-standard-steps   # 네임스페이스 없음
spec:
  templates:
  - name: security-scan
    inputs:
      parameters:
      - name: image
    container:
      image: aquasec/trivy:latest
      command: [trivy]
      args: ["image", "--exit-code", "1", "{{inputs.parameters.image}}"]
```

```yaml
# 다른 네임스페이스에서 참조
spec:
  templates:
  - name: build-and-scan
    steps:
    - - name: scan
        templateRef:
          name: org-standard-steps
          template: security-scan
          clusterScope: true   # ClusterWorkflowTemplate 참조 시 필수
        arguments:
          parameters:
          - name: image
            value: "myapp:{{workflow.parameters.tag}}"
```

### Daemon 컨테이너 — 여러 스텝에 걸친 백그라운드 서비스

Daemon 컨테이너는 여러 스텝에 걸쳐 지속되는 백그라운드 프로세스입니다. 단일 스텝에만 붙는 Sidecar와 달리, 템플릿 스코프 전체 동안 살아 있어 뒤 스텝들이 그 서비스에 접근할 수 있습니다. 테스트용 DB나 모니터링 서버를 띄워 여러 스텝에서 쓸 때 적합합니다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: daemon-demo-
spec:
  entrypoint: main
  templates:
  - name: main
    steps:
    - - name: start-db
        template: influxdb-daemon    # 1단계: DB 시작
    - - name: run-benchmark
        template: load-test          # 2단계: DB 활용
    - - name: collect-results
        template: query-results      # 3단계: 결과 조회
    # 템플릿 스코프 종료 시 daemon 자동 종료

  - name: influxdb-daemon
    daemon: true              # 백그라운드 실행 플래그
    retryStrategy:
      limit: "3"
    container:
      image: influxdb:1.8
      readinessProbe:         # 준비 완료 확인 후 다음 스텝 진행
        httpGet:
          path: /ping
          port: 8086
        initialDelaySeconds: 5
        periodSeconds: 5

  - name: load-test
    container:
      image: alpine:3.18
      command: [sh, -c]
      # daemon IP는 steps.start-db.ip 로 참조
      args: ["curl http://{{steps.start-db.ip}}:8086/write?db=test -d 'metric,host=a value=1'"]
```

`daemon: true` 플래그로 백그라운드 실행을 선언하고, `readinessProbe`로 준비 완료를 확인한 뒤 다음 스텝으로 넘어갑니다. daemon의 IP는 `{{steps.NAME.ip}}`로 참조합니다. Daemon과 Sidecar의 차이는 다음과 같습니다.

| 특성 | Daemon | Sidecar |
|---|---|---|
| 생명주기 | 템플릿 스코프 전체 | 단일 스텝 |
| 여러 스텝에서 접근 | 가능 | 불가 |
| IP 참조 | `{{steps.NAME.ip}}` | 같은 Pod 내 localhost |
| 용도 | 테스트 DB, 모니터링 서버 | 로그 수집, 파일 변환 |

### Init 컨테이너

Init 컨테이너는 메인 컨테이너보다 먼저 실행되어 준비 작업을 하는 컨테이너입니다. S3에서 설정 파일을 내려받는 것 같은 선행 작업에 씁니다. `mirrorVolumeMounts: true`를 두면 메인 컨테이너의 볼륨 마운트를 그대로 복사합니다.

```yaml
templates:
- name: with-init
  initContainers:
  - name: download-config
    image: amazon/aws-cli:2.15.0
    command: [aws]
    args: [s3, cp, "s3://my-bucket/config.yaml", "/shared/config.yaml"]
    mirrorVolumeMounts: true    # 메인 컨테이너의 볼륨 마운트를 그대로 복사
  container:
    image: myapp:latest
    command: [./run]
    args: [--config, /shared/config.yaml]
    volumeMounts:
    - name: shared-data
      mountPath: /shared
  volumes:
  - name: shared-data
    emptyDir: {}
```

### 노드 선택 및 스케줄링 제어

`nodeSelector`·`tolerations`·`affinity`로 스텝이 어느 노드에서 실행될지 제어합니다. GPU 워크로드를 GPU 노드에 배치할 때 씁니다. v3.6부터는 워크플로우 레벨뿐 아니라 템플릿 레벨에서도 `nodeSelector`/`tolerations`를 오버라이드할 수 있습니다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: gpu-workflow
spec:
  entrypoint: train
  # 워크플로우 전체 노드 선택
  nodeSelector:
    cloud.google.com/gke-nodepool: gpu-pool
  tolerations:
  - key: "nvidia.com/gpu"
    operator: "Exists"
    effect: "NoSchedule"

  templates:
  - name: train
    # 템플릿 레벨에서 오버라이드 가능 (v3.6+)
    nodeSelector:
      accelerator: nvidia-tesla-a100
    tolerations:
    - key: "high-memory"
      operator: "Exists"
      effect: "NoSchedule"
    affinity:
      nodeAffinity:
        requiredDuringSchedulingIgnoredDuringExecution:
          nodeSelectorTerms:
          - matchExpressions:
            - key: node.kubernetes.io/instance-type
              operator: In
              values: [a2-highgpu-1g, a2-highgpu-2g]
      podAntiAffinity:
        preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels:
                workflows.argoproj.io/workflow: "{{workflow.name}}"
            topologyKey: kubernetes.io/hostname
    container:
      image: tensorflow/tensorflow:2.15.0-gpu
      resources:
        limits:
          nvidia.com/gpu: 1
```

### Pod GC 정책

`podGC`는 완료된 Pod를 언제 삭제할지 정하는 정책입니다. 리소스를 빨리 반환할수록 실패 Pod의 로그가 사라지므로, 반환 속도와 로그 보존 사이에서 전략을 고릅니다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: pod-gc-demo-
spec:
  podGC:
    strategy: OnWorkflowSuccess   # 성공한 워크플로우의 Pod만 삭제
    # 옵션:
    # OnPodCompletion    — 각 Pod 완료 즉시 삭제 (가장 공격적)
    # OnPodSuccess       — 성공한 Pod만 즉시 삭제
    # OnWorkflowCompletion — 워크플로우 완료 시 모든 Pod 삭제
    # OnWorkflowSuccess  — 워크플로우 성공 시만 Pod 삭제 (실패 시 로그 보존)
    deleteDelayDuration: "5m"   # 삭제 전 유예 시간 (v3.5+)
    labelSelector:
      matchLabels:
        workflows.argoproj.io/completed: "true"
  entrypoint: main
```

전략 선택 기준은 목적에 따라 갈립니다.

- 디버깅 환경: `OnWorkflowSuccess` (실패 시 Pod 로그 보존)
- 비용 절감: `OnPodCompletion` (즉시 리소스 반환)
- 프로덕션 기본: `OnWorkflowCompletion` (감사 목적으로 워크플로우 완료까지 보존)

## 스케줄링과 트리거

워크플로우를 주기적으로 실행하거나 외부 이벤트로 트리거하는 두 가지 방식이 있습니다. Cron 주기 실행은 CronWorkflow가, 이벤트 기반 트리거는 [Argo Events](https://argoproj.github.io/argo-events/)가 담당합니다.

### CronWorkflow 전체 필드

`CronWorkflow`는 Cron 주기마다 워크플로우를 실행하는 CRD입니다. v3.6부터 복수 스케줄, 자동 중단 조건, 조건부 실행이 추가됐습니다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: CronWorkflow
metadata:
  name: daily-etl
  namespace: argo
spec:
  # v3.6+: 복수 스케줄 지원
  schedules:
  - "0 2 * * *"       # 매일 오전 2시
  - "0 14 * * *"      # 매일 오후 2시

  timezone: "Asia/Seoul"          # IANA 타임존
  concurrencyPolicy: "Forbid"     # Allow | Forbid | Replace
  startingDeadlineSeconds: 30     # 컨트롤러 다운 후 놓친 실행 허용 유예(초)
  suspend: false                  # true 시 스케줄 일시 중지
  successfulJobsHistoryLimit: 5   # 성공 이력 보관 수 (기본 3)
  failedJobsHistoryLimit: 3       # 실패 이력 보관 수 (기본 1)

  # v3.6+ 추가 기능
  stopStrategy:
    expression: "cronworkflow.failed >= 3"   # 연속 3회 실패 시 자동 중단
  when: "{{= cronworkflow.lastScheduledTime != '' }}"  # 조건부 실행

  workflowSpec:
    entrypoint: main
    ttlStrategy:
      secondsAfterCompletion: 86400   # 24시간 후 워크플로우 삭제
    templates:
    - name: main
      container:
        image: alpine:3.18
        command: [echo]
        args: ["Daily ETL at {{workflow.creationTimestamp}}"]
```

`concurrencyPolicy`는 이전 실행이 끝나지 않았을 때의 동작을 정합니다.

- `Allow`: 이전 실행 완료 여부 무관하게 새 워크플로우 생성
- `Forbid`: 실행 중인 워크플로우가 있으면 새 스케줄 건너뜀
- `Replace`: 실행 중인 워크플로우를 종료하고 새 워크플로우 시작

`startingDeadlineSeconds`는 컨트롤러가 재시작되거나 일시 중지 후 재개할 때, 이 기간 내 놓친 스케줄을 실행하게 합니다. `0`으로 설정하면 항상 현재 시각 기준으로만 판단합니다.

> [!WARNING] DST 전환 주의
> DST(일광절약시간) 전환 구간에서는 스케줄이 건너뛰거나 두 번 실행될 수 있습니다. 중요한 작업은 UTC 타임존 사용을 권장합니다.

### Argo Events 통합 패턴

Argo Events는 GitHub webhook 같은 외부 이벤트를 받아 워크플로우를 트리거합니다. `EventSource`가 이벤트를 수신하고, `Sensor`가 조건에 맞는 이벤트에서 워크플로우를 생성하는 구조입니다.

```
EventSource → Sensor → WorkflowEventBinding → Workflow
```

`EventSource`는 GitHub push 이벤트를 받는 webhook 엔드포인트를 정의합니다.

```yaml
# EventSource: GitHub Webhook 수신
apiVersion: argoproj.io/v1alpha1
kind: EventSource
metadata:
  name: github-eventsource
  namespace: argo-events
spec:
  github:
    push-events:
      repositories:
      - owner: myorg
        names: [myrepo]
      events:
      - push
      webhook:
        endpoint: /push
        port: "12000"
        method: POST
      apiToken:
        name: github-access
        key: token
      webhookSecret:
        name: github-webhook-secret
        key: secret
      insecure: false
      active: true
      contentType: json
```

`Sensor`는 이벤트를 받아 필터를 적용하고 워크플로우를 트리거합니다. 아래 예시는 `main` 브랜치 푸시만 트리거합니다.

```yaml
# Sensor: 이벤트 수신 → 워크플로우 트리거
apiVersion: argoproj.io/v1alpha1
kind: Sensor
metadata:
  name: github-sensor
  namespace: argo-events
spec:
  template:
    serviceAccountName: argo-events-sa
  dependencies:
  - name: push-dep
    eventSourceName: github-eventsource
    eventName: push-events
    filters:
      data:
      - path: body.ref
        type: string
        value: ["refs/heads/main"]    # main 브랜치 푸시만 트리거
  triggers:
  - template:
      name: trigger-ci
      argoWorkflow:
        group: argoproj.io
        version: v1alpha1
        resource: workflows
        operation: create
        source:
          resource:
            apiVersion: argoproj.io/v1alpha1
            kind: Workflow
            metadata:
              generateName: ci-build-
              namespace: argo
            spec:
              workflowTemplateRef:
                name: ci-pipeline
        parameters:
        - src:
            dependencyName: push-dep
            dataKey: body.head_commit.id
          dest: spec.arguments.parameters.0.value
```

## 보안과 RBAC

보안 설정은 워크플로우가 최소 권한으로 실행되도록 하고, 누가 무엇을 할 수 있는지를 역할로 나누는 두 축입니다. 워크플로우 실행용 [ServiceAccount](https://kubernetes.io/docs/concepts/security/service-accounts/)를 최소 권한으로 분리하고, UI 조회·제출·관리를 역할별로 [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)에 정의합니다.

### ServiceAccount 분리 전략

워크플로우 실행용 SA는 최소 권한 원칙에 따라 별도 생성합니다. `automountServiceAccountToken: false`로 불필요한 토큰 마운트를 막습니다. 메모이제이션을 쓰는 워크플로우는 ConfigMap `create`·`update` 권한이 추가로 필요합니다.

```yaml
# 1. 워크플로우 실행용 SA (최소 권한)
apiVersion: v1
kind: ServiceAccount
metadata:
  name: workflow-runner
  namespace: argo
automountServiceAccountToken: false   # 불필요한 토큰 마운트 방지

---
# 2. 워크플로우 Runner용 RBAC
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: workflow-runner-role
  namespace: argo
rules:
- apiGroups: ["argoproj.io"]
  resources: [workflows, workflowtemplates]
  verbs: [get, list, watch, create, update, patch]
- apiGroups: [""]
  resources: [pods, pods/log]
  verbs: [get, list, watch]
- apiGroups: [""]
  resources: [configmaps]
  verbs: [get, create, update]   # memoize 사용 시

---
# 3. 워크플로우 Spec에서 SA 지정
apiVersion: argoproj.io/v1alpha1
kind: Workflow
spec:
  serviceAccountName: workflow-runner
```

### 역할 분리 패턴

권한은 세 역할로 나눕니다. UI 읽기 전용은 조회만, 제출자는 `create`를 더하고, 관리자는 `delete`·`patch`까지 갖습니다.

- UI 읽기 전용: `workflows`, `workflowtemplates`, `cronworkflows`에 `get, list, watch`만 부여
- 워크플로우 제출: 위 권한에 `create` 추가
- 관리자: `delete`, `patch` 포함 전체 권한

```yaml
# UI 읽기 전용 사용자
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: argo-ui-readonly
  namespace: argo
rules:
- apiGroups: [""]
  resources: [events, pods, pods/log]
  verbs: [get, list, watch]
- apiGroups: [argoproj.io]
  resources: [workflows, workflowtemplates, cronworkflows, workfloweventbindings]
  verbs: [get, list, watch]

---
# 워크플로우 제출 사용자
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: argo-submitter
  namespace: argo
rules:
- apiGroups: [argoproj.io]
  resources: [workflows, workflowtemplates]
  verbs: [get, list, watch, create]
- apiGroups: [""]
  resources: [pods, pods/log]
  verbs: [get, list, watch]
```

### Pod Security Context

Pod Security Context는 컨테이너를 non-root로, 권한 상승 없이 실행하도록 강제하는 설정입니다. 워크플로우 레벨에서 모든 Pod에 적용하고, 개별 템플릿에서 오버라이드합니다. `seccompProfile: RuntimeDefault`는 v3.6부터 기본 활성화가 권장됩니다.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
spec:
  securityContext:              # 모든 Pod에 적용
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 2000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault      # v3.6+ 기본 활성화 권장
  templates:
  - name: secure-job
    securityContext:            # 개별 템플릿 오버라이드
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: [ALL]
    container:
      image: alpine:3.18
      command: [echo]
      args: ["secure execution"]
```

컨테이너 레벨에서 `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`을 더하는 것이 보안 강화의 표준 패턴입니다.

### SSO with Dex (OIDC)

[Dex](https://dexidp.io/)를 통한 SSO는 OIDC 그룹 기반으로 RBAC을 정의합니다. ServiceAccount의 `workflows.argoproj.io/rbac-rule` 어노테이션에 CEL 표현식으로 그룹 규칙을 걸고, `rbac-rule-precedence` 숫자가 높을수록 우선순위가 높습니다. `filterGroupsRegex`로 불필요한 그룹을 걸러 RBAC 평가 부하를 줄입니다.

```yaml
# workflow-controller-configmap
apiVersion: v1
kind: ConfigMap
metadata:
  name: workflow-controller-configmap
  namespace: argo
data:
  sso: |
    issuer: https://dex.example.com/dex
    clientId:
      name: argo-sso-secret
      key: client-id
    clientSecret:
      name: argo-sso-secret
      key: client-secret
    redirectUrl: https://argo.example.com/oauth2/callback
    scopes:
    - openid
    - profile
    - email
    - groups
    rbac:
      enabled: true
    sessionExpiry: 240h
    filterGroupsRegex:
    - ".*argo-.*"
    customGroupClaimName: argo_groups   # 비표준 groups 클레임 매핑
```

```yaml
# ServiceAccount에 RBAC 규칙 어노테이션
apiVersion: v1
kind: ServiceAccount
metadata:
  name: admin-sa
  namespace: argo
  annotations:
    workflows.argoproj.io/rbac-rule: "'argo-admin' in groups"
    workflows.argoproj.io/rbac-rule-precedence: "10"   # 높은 숫자 = 높은 우선순위

---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: readonly-sa
  namespace: argo
  annotations:
    workflows.argoproj.io/rbac-rule: "'argo-viewer' in groups"
    workflows.argoproj.io/rbac-rule-precedence: "1"
```

SSO는 복수 auth-mode를 동시에 지정해 시작합니다.

```bash
argo server \
  --auth-mode sso \
  --auth-mode client    # 복수 auth-mode 동시 지원
```

### Argo Server API 인증

Argo Server API는 Bearer Token으로 인증합니다. 토큰은 `argo auth token`으로 발급하거나 ServiceAccount Token을 직접 씁니다.

```bash
# Bearer Token 방식
ARGO_TOKEN=$(kubectl exec -n argo deploy/argo-server -- argo auth token)
curl -H "Authorization: Bearer ${ARGO_TOKEN}" \
  https://argo.example.com/api/v1/workflows/argo

# ServiceAccount Token 직접 사용
SA_TOKEN=$(kubectl get secret -n argo workflow-runner-token -o jsonpath='{.data.token}' | base64 -d)
curl -H "Authorization: Bearer ${SA_TOKEN}" \
  https://argo.example.com/api/v1/workflows/argo

# UI 토큰 갱신
argo auth token --namespace argo
```

## 성능과 스케일링

대규모 환경에서는 컨트롤러가 처리량 병목이 됩니다. 컨트롤러의 API 요청 속도(QPS/Burst), 병렬 처리 워커 수, Pod 생성 속도, TTL과 GC 주기를 함께 조율해야 [etcd](https://etcd.io/) 부하를 막고 처리량을 확보할 수 있습니다.

### Controller QPS/Burst 설정

컨트롤러의 처리량은 Deployment args로 튜닝합니다. Kubernetes API 요청 속도(`--qps`/`--burst`)와 워크플로우·Pod 처리 병렬도(`--workflow-workers` 등)가 핵심 파라미터입니다.

```yaml
# Argo Workflows 컨트롤러 Deployment args
apiVersion: apps/v1
kind: Deployment
metadata:
  name: workflow-controller
  namespace: argo
spec:
  template:
    spec:
      containers:
      - name: workflow-controller
        args:
        - --qps=50             # Kubernetes API 초당 평균 요청 수 (기본 20)
        - --burst=75           # 버스트 허용 요청 수 (기본 30)
        - --workflow-workers=32   # 워크플로우 병렬 처리 goroutine (기본 8)
        - --pod-cleanup-workers=8  # Pod GC 병렬 처리 (기본 4)
        - --workflow-ttl-workers=4 # TTL 삭제 병렬 처리 (기본 4)
        - --cron-workflow-workers=8 # CronWorkflow 처리 (기본 2, v3.5+)
        resources:
          requests:
            cpu: "1"
            memory: 2Gi
          limits:
            cpu: "4"
            memory: 8Gi
```

CNOE 2024 EKS 확장성 테스트 결과는 다음과 같습니다. QPS/Burst 40/50·workers=32에서 분당 540 워크플로우에 도달했고, QPS를 더 높여도(50/60) 처리량이 늘지 않는 포화점이었습니다.

| QPS/Burst | Workers | 최대 워크플로우/분 |
|---|---|---|
| 20/30 | 8 | 270 |
| 30/40 | 16 | 420 (+55%) |
| 40/50 | 32 | 540 (+28%) |
| 50/60 | 32 | 540 (포화점) |

### Pod 생성 속도 제한

`resourceRateLimit`은 초당 Pod 생성 요청 수를 제한합니다. 이 설정은 Pod에만 적용되며, ConfigMap·PVC 등 다른 리소스는 `--qps`/`--burst`로 제어합니다.

```yaml
# workflow-controller-configmap
data:
  resourceRateLimit: |
    limit: 15      # 초당 평균 Pod 생성 요청 수
    burst: 30      # 버스트 허용 Pod 생성 수
```

### Workflow TTL 설정

`ttlStrategy`는 완료된 Workflow 객체를 얼마나 남길지 정합니다. 성공·실패·완료별로 보존 기간을 다르게 줄 수 있습니다. 실패한 워크플로우는 디버깅을 위해 더 길게 남기는 것이 일반적입니다.

```yaml
spec:
  ttlStrategy:
    secondsAfterCompletion: 86400    # 완료 후 24시간
    secondsAfterSuccess: 3600        # 성공 후 1시간
    secondsAfterFailure: 604800      # 실패 후 7일 (디버깅 목적)
```

전역 기본값은 `workflow-controller-configmap`의 `workflowDefaults`에 둡니다.

```yaml
data:
  workflowDefaults: |
    spec:
      ttlStrategy:
        secondsAfterCompletion: 86400
      podGC:
        strategy: OnWorkflowCompletion
```

### 대규모 withParam 최적화

`withParam`으로 수천 개 아이템을 처리하면 etcd 메모리가 급증합니다. 아이템 수가 만 개를 넘으면 문제가 되므로, 배치로 나누거나 `parallelism`으로 동시 실행 수를 제한합니다.

```yaml
# 위험: withParam으로 수천 개 아이템 처리 시 etcd 메모리 급증
- name: fan-out-dangerous
  steps:
  - - name: process
      template: worker
      withParam: "{{workflow.parameters.huge-list}}"  # 10,000+ 아이템 → 문제

# 해결책 1: 배치 처리로 분할
- name: fan-out-batched
  steps:
  - - name: process-batch
      template: batch-worker
      withParam: "{{workflow.parameters.batch-ids}}"  # 배치당 100개

# 해결책 2: maxConcurrency 제한
- name: fan-out-limited
  steps:
  - - name: process
      template: worker
      withParam: "{{workflow.parameters.items}}"
  parallelism: 50   # 한 번에 50개만 실행
```

v3.6 환경에서는 파라미터가 256KB를 초과하면 자동으로 오브젝트 스토리지에 오프로딩됩니다.

```yaml
# 자동 오프로딩: 파라미터가 256KB 초과 시 자동으로 오브젝트 스토리지에 저장
data:
  config: |
    artifactRepository:
      s3:
        bucket: argo-artifacts
        endpoint: s3.amazonaws.com
    offloadNodeStatusVersion: "v1"
```

<details markdown="1">
<summary>심화: 재귀 깊이 제한과 세마포어 캐시, 샤딩</summary>

**재귀 깊이 제한.** 기본 최대 재귀 깊이는 100입니다. `DISABLE_MAX_RECURSION` 환경 변수로 끌 수 있지만, 무한 루프 위험이 있습니다.

```yaml
# 기본 최대 재귀 깊이: 100
# 비활성화 (주의: 무한 루프 위험)
containers:
- name: workflow-controller
  env:
  - name: DISABLE_MAX_RECURSION
    value: "true"
```

**세마포어 ConfigMap 캐시.** `semaphoreLimitCacheSeconds`는 세마포어 한도를 담은 ConfigMap의 조회 캐시 TTL을 초 단위로 정합니다(기본 60초).

```yaml
# workflow-controller-configmap
data:
  config: |
    semaphoreLimitCacheSeconds: 60   # ConfigMap 조회 캐시 TTL (초)
```

**샤딩(대규모 멀티테넌트 환경).** 컨트롤러를 네임스페이스별로 분리하거나 `instanceID`로 논리적으로 격리합니다.

```yaml
# 네임스페이스별 컨트롤러 분리
containers:
- name: workflow-controller
  args:
  - --namespaced           # 이 네임스페이스만 관리
  - --managed-namespace=team-a

---
# instanceID로 논리적 분리
data:
  instanceID: "cluster-a"   # 같은 클러스터 내 다른 컨트롤러와 격리
```

</details>

## v3.5 / v3.6 주요 변경사항

버전별로 동시성·스케줄링·보안·성능 영역에서 기능이 추가됐습니다. 아래는 v3.5와 v3.6의 주요 변경과 deprecated 항목입니다.

### v3.5 (2023-08)

| 기능 | 설명 |
|---|---|
| 크로스 네임스페이스 잠금 | 세마포어·뮤텍스를 다른 네임스페이스에서 참조 가능 |
| 아티팩트 스트리밍 | S3/Azure Blob/HTTP/Artifactory 디스크 버퍼 없이 스트리밍 다운로드 |
| 통합 워크플로우 목록 | 라이브 CRD + 아카이브 DB 워크플로우 통합 뷰 |
| `--selector` 플래그 | `argo cron list --selector` 레이블 기반 필터링 |
| 성공 워크플로우 재시도 | `--node-field-selector` 설정 시 성공한 워크플로우도 재시도 가능 |
| expression retryPolicy 기본값 | expression 지정 시 retryPolicy 기본값이 `Always`로 변경 |
| `--cron-workflow-workers` | CronWorkflow 전용 워커 수 설정 추가 |
| `filterGroupsRegex` | SSO 그룹 필터링 정규식 지원 |

### v3.6 (2024)

| 기능 | 설명 |
|---|---|
| 복수 CronWorkflow 스케줄 | `schedules` 리스트로 한 CronWorkflow에 여러 스케줄 정의 |
| CronWorkflow 중단 전략 | `stopStrategy.expression`으로 자동 중단 조건 설정 |
| CronWorkflow 조건부 실행 | `when` 필드로 동적 실행 여부 결정 |
| 데이터베이스 기반 동기화 | PostgreSQL/MySQL/MariaDB로 멀티컨트롤러 뮤텍스·세마포어 |
| 동적 템플릿 참조 | 파라미터로 `templateRef.name` 동적 지정 가능 |
| 템플릿 레벨 nodeSelector/Tolerations | v3.6에서 공식 지원 (이전에는 워크플로우 레벨만) |
| OSS 아티팩트 GC | Alibaba Cloud OSS 아티팩트 자동 정리 |
| Seccomp 기본값 | `RuntimeDefault` seccomp 프로파일 자동 적용 |
| 병렬 Pod 정리 | 재시도 완료 처리 속도 대폭 향상 |
| Pod Kubernetes finalizer | Pod 조기 삭제 오류 방지 |
| 메트릭 개편 | Prometheus 메트릭 구조 전면 재설계 |
| 큐 기반 아카이빙 | 대규모 아카이빙 시 메모리 효율성 개선 |

### deprecated 항목

| 기능 | 대안 | 비고 |
|---|---|---|
| `archiveLogs: true` (전역) | 아티팩트 기반 로그 저장 | v3.x에서 동작 변경 |
| `argo server --auth-mode hybrid` | `--auth-mode sso --auth-mode client` | 명시적 복수 모드 지정 |
| PNS executor | Emissary executor | v3.4+에서 Emissary가 기본값 |
| Docker executor | Emissary executor | 완전 제거됨 |
| Kubelet executor | Emissary executor | 완전 제거됨 |
| `withSequence.count` string → int | `withSequence.count`를 정수로 | 타입 변경 |
| Argo Server Deployment의 `--port` | `--http-port`, `--https-port` | 분리됨 |

## 운영 환경 설정과 트러블슈팅

앞의 설정들을 프로덕션 기준으로 모으면 컨트롤러 ConfigMap 하나로 정리됩니다. 동시성, 리소스 속도 제한, 기본 워크플로우 설정, Executor 리소스를 한곳에 둡니다.

```yaml
# workflow-controller-configmap 종합 예시
apiVersion: v1
kind: ConfigMap
metadata:
  name: workflow-controller-configmap
  namespace: argo
data:
  # 동시성
  parallelism: "100"
  namespaceParallelism: "20"

  # 리소스 속도 제한
  resourceRateLimit: |
    limit: 20
    burst: 40

  # 세마포어 캐시
  semaphoreLimitCacheSeconds: "60"

  # 기본 워크플로우 설정
  workflowDefaults: |
    spec:
      ttlStrategy:
        secondsAfterCompletion: 604800
        secondsAfterFailure: 2592000
      podGC:
        strategy: OnWorkflowSuccess
        deleteDelayDuration: "10m"
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault

  # Executor 리소스
  executor: |
    resources:
      requests:
        cpu: 100m
        memory: 64Mi
      limits:
        cpu: 500m
        memory: 512Mi
```

프로덕션에서는 `podGC.strategy: OnWorkflowSuccess`를 기본으로 두는 것이 권장됩니다. 실패한 워크플로우의 Pod 로그가 보존되어 디버깅이 가능하기 때문입니다. 자주 쓰는 트러블슈팅 명령은 다음과 같습니다.

```bash
# 잠금 대기 중인 워크플로우 확인
kubectl get workflows -n argo -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\t"}{.status.synchronization}{"\n"}{end}'

# ConfigMap 캐시 수동 삭제 (메모이제이션 리셋)
kubectl delete configmap -n argo ml-model-cache

# 특정 워크플로우 재시도
argo retry -n argo <workflow-name> --node-field-selector phase=Failed

# 컨트롤러 메트릭 확인
kubectl port-forward -n argo svc/workflow-controller-metrics 9090
curl localhost:9090/metrics | grep argo_workflows
```

## 참고 자료

- Argo Workflows, [공식 문서](https://argo-workflows.readthedocs.io/en/latest/) — Retries·Synchronization·Memoization·Scaling·Security·CronWorkflows 등 세부 페이지 포함
- Argo Project, [Argo Events](https://argoproj.github.io/argo-events/)
- Alibaba Cloud, [Argo Workflows 3.6: Key New Features in Cloud-Native Orchestration](https://www.alibabacloud.com/blog/argo-workflows-3-6-key-new-features-in-cloud-native-orchestration_601872)
- CNOE, [Argo Workflow Scalability (Amazon EKS)](https://cnoe.io/blog/argo-workflow-scalability)
- Pipekit, [Argo Workflows 3.6](https://pipekit.io/blog/argo-workflows-3-6)

{% endraw %}
