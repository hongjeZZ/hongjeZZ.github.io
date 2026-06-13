---
title: Spring 트랜잭션 전파(propagation), 헷갈리지 않게 정리
date: 2026-06-12 11:00:00 +0900
categories: [개발, 백엔드]
tags: [Spring, Kotlin, 트랜잭션, 백엔드]
---

`@Transactional`을 붙이긴 했는데, 메서드가 다른 트랜잭션 메서드를 호출하면 트랜잭션이 어떻게 묶이는지 매번 헷갈렸다. 전파(propagation) 옵션을 한 번 제대로 정리해 둔다.

## 전파가 왜 필요한가

전파는 "이미 진행 중인 트랜잭션이 있을 때 새 트랜잭션 경계를 어떻게 처리할지"를 정하는 규칙이다. 서비스 A가 서비스 B를 호출하고, 둘 다 `@Transactional`이라면 — 하나로 묶을지, 각자 따로 커밋할지 결정해야 한다.

기본값은 `REQUIRED`다. 진행 중인 트랜잭션이 있으면 거기에 참여하고, 없으면 새로 만든다. 대부분의 경우 이걸로 충분하다.

## REQUIRED vs REQUIRES_NEW

가장 많이 비교되는 두 가지다.

- `REQUIRED`: 부모 트랜잭션에 **참여**한다. 안쪽에서 예외가 나면 바깥까지 통째로 롤백된다.
- `REQUIRES_NEW`: 부모를 **잠시 멈추고** 독립된 새 트랜잭션을 연다. 안쪽이 롤백돼도 바깥은 영향받지 않는다(그 반대도 마찬가지).

로그 적재나 알림 발송처럼 "본 작업이 실패해도 이건 남겨야 하는" 경우에 `REQUIRES_NEW`가 유용하다.

```kotlin
// file: OrderService.kt
@Service
class OrderService(
    private val auditService: AuditService,
) {
    @Transactional
    fun placeOrder(cmd: PlaceOrder) {
        // ... 주문 저장 ...
        // 주문이 롤백되더라도 감사 로그는 남기고 싶다
        auditService.record(cmd)
    }
}

@Service
class AuditService {
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    fun record(cmd: PlaceOrder) { /* 별도 트랜잭션으로 커밋 */ }
}
```

## 자주 만나는 함정

> [!warning] self-invocation은 프록시를 타지 않는다
> 같은 클래스 안에서 `this.record(...)`처럼 직접 호출하면 Spring AOP 프록시를 거치지 않아 전파 옵션이 **무시된다**. 반드시 다른 빈을 주입받아 호출해야 한다.

또 하나, `REQUIRES_NEW`는 커넥션을 하나 더 점유한다. 루프 안에서 남발하면 커넥션 풀이 금방 마른다. 트랜잭션을 쪼개는 건 항상 비용이라는 걸 기억하자.

## 정리

- 헷갈리면 일단 기본값 `REQUIRED`.
- "본 작업과 생사를 같이하면 안 되는" 부수 작업만 `REQUIRES_NEW`.
- 전파 옵션은 프록시 경유 호출에서만 동작한다.
