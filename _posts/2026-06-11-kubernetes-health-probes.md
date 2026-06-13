---
title: Kubernetes 헬스체크 — liveness, readiness, startup 구분
date: 2026-06-11 14:00:00 +0900
categories: [개발, 인프라]
tags: [Kubernetes, DevOps, 인프라, 헬스체크]
---

쿠버네티스 프로브 세 종류를 매번 비슷하게 적다가 사고를 낸 적이 있다. 이름은 비슷하지만 하는 일이 완전히 다르다.

## 세 가지 프로브

- **liveness**: 컨테이너가 살아있는가? 실패하면 **재시작**한다.
- **readiness**: 트래픽을 받을 준비가 됐는가? 실패하면 **서비스에서 제외**(엔드포인트에서 빠짐)된다. 재시작은 하지 않는다.
- **startup**: 느린 초기화가 끝났는가? 끝나기 전까지 liveness/readiness를 **유보**시킨다.

## liveness — 재시작 트리거

liveness는 "데드락에 빠졌거나 응답 불능이 된 컨테이너를 살려내는" 용도다. 그래서 가볍고 확실한 체크여야 한다. DB 연결까지 확인하는 무거운 헬스 엔드포인트를 liveness에 걸면, DB가 잠깐 흔들릴 때 멀쩡한 파드가 줄줄이 재시작되는 참사가 난다.

> [!danger] liveness에 외부 의존성을 넣지 말 것
> liveness 실패 = 재시작이다. 외부 의존성(DB, 캐시, 다른 서비스)을 liveness에 넣으면, 의존성 장애가 곧 파드 재시작 폭풍으로 번진다. 외부 의존성 확인은 readiness에 둔다.

## readiness — 트래픽 차단

readiness는 트래픽을 받아도 되는지를 판단한다. 부팅 직후 워밍업, 일시적인 다운스트림 장애처럼 "지금은 빼고 곧 복귀할" 상황에 적합하다. 실패해도 파드는 죽지 않고, 준비되면 자동으로 다시 엔드포인트에 등록된다.

## startup — 느린 시작 보호

JVM 애플리케이션처럼 초기화가 오래 걸리는 경우, startup 프로브가 끝날 때까지 liveness를 미뤄준다. 이게 없으면 "아직 부팅 중인데 liveness가 실패로 판단 → 재시작 → 또 부팅 중 → 무한 재시작" 루프에 빠진다.

```yaml
# file: deployment.yaml
livenessProbe:
  httpGet: { path: /healthz, port: 8080 }
  periodSeconds: 10
readinessProbe:
  httpGet: { path: /readyz, port: 8080 }
  periodSeconds: 5
startupProbe:
  httpGet: { path: /healthz, port: 8080 }
  failureThreshold: 30
  periodSeconds: 5   # 최대 150초까지 부팅 대기
```

## 정리

> [!tip] 한 줄 요약
> liveness는 "재시작", readiness는 "트래픽 차단", startup은 "느린 시작 보호". 외부 의존성은 readiness에만.

세 프로브의 책임을 섞지 않는 것이 핵심이다. 이름이 비슷하다고 같은 엔드포인트를 재활용하면 장애가 증폭된다.
