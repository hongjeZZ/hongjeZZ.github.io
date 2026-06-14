---
title: "[Spring Boot] WebSocket 을 사용하여 채팅 서비스 구현하기(4) - 채팅 서비스 성능 개선 및 부하 테스트"
date: 2025-02-14 20:26:03 +0900
categories: [Back-End, Spring]
tags: [JMeter, Redis, Spring]
---

## **들어가며**

야구 직관 서비스 CATCH-Mi 프로젝트에서 실시간 채팅 서비스를 구현한 경험을 기록하고 복습하기 위해 본 글을 작성합니다. 이번 포스팅에서는 현재 CATCH-Mi 채팅 서비스의 **문제점과 잠재적인 장애 요소를 고민**하고, 이에 대한 **성능 개선 과정과 *Jmeter*를 통한 성능 테스트** 결과를 비교해 보겠습니다.

**SpringBoot**와 **웹소켓**을 통해 채팅 서비스 구현과정이 궁금하신 분은 [이전 글](/posts/spring-websocket-chat-3-stomp/)을 참고해 주세요!

[🔗 [Spring boot] WebSocket 을 사용하여 채팅 서비스 구현하기(3) - STOMP를 사용하여 실시간 채팅 구현 (비동기 처리)](/posts/spring-websocket-chat-3-stomp/)

## **1. MySQL -> MongoDB로 마이그레이션**

### **데이터베이스 변경의 필요성**

현재 CATCH-Mi 서비스의 채팅 데이터는 MySQL 데이터베이스의 *ChatMessage* 테이블에 저장되고 있습니다. 사용자가 채팅을 보낼 때마다 데이터베이스에 접근하여 데이터를 저장하는 방식입니다. 하지만 채팅 데이터는 사용자가 증가함에 따라 기하급수적으로 늘어나는 특성을 가지고 있습니다. 이로 인해 추후 사용자가 증가할 경우, 데이터베이스에 접근하는 I/O 비용과 트랜잭션 비용이 증가하며, 트래픽이 많아질수록 성능 저하가 우려됩니다. 이는 결국 전체 서비스의 성능 저하로 이어질 수 있습니다.

또한, 채팅 데이터는 실시간성이 매우 중요하기 때문에 낮은 지연 시간을 유지할 수 있는 데이터 저장 방식을 고민해야 했습니다. 더불어 채팅 데이터는 주로 읽기/쓰기 연산이 이루어지며, JOIN과 같은 관계형 연산을 사용하지 않기 때문에 관계형 데이터베이스(RDB)를 사용할 필요가 없다고 판단했습니다. 데이터와 트래픽의 증가에 따라 수평 확장(scale-out)이 용이한 **NoSQL**을 선택해야 대규모 데이터를 효율적으로 관리할 수 있습니다.

이러한 이유로, 우리 팀은 **MySQL에서 NoSQL 데이터베이스로 마이그레이션을 결정**했습니다.

### **MongoDB 를 선택한 이유**

**1. 다양한 데이터 포맷 지원**

채팅 데이터에는 이모지, 파일, 메시지 등 다양한 유형의 데이터가 저장될 수 있습니다. 또한, 채팅 유형도 일대일 채팅, 굿즈 거래 채팅, 메이트 단체 채팅 등 다양합니다. 이러한 다양한 데이터 포맷을 유연하게 저장할 수 있는 데이터베이스가 필요했습니다. MongoDB는 스키마가 유연한 NoSQL 데이터베이스로, 데이터 포맷을 신경 쓰지 않고 저장할 수 있어 이에 적합합니다.

**2. 빈번한 읽기/쓰기 연산에 최적화**

채팅 서비스는 사용자들이 실시간으로 메시지를 주고받는 환경이기 때문에, 읽기/쓰기 연산이 매우 빈번하게 발생합니다. MongoDB는 이러한 많은 연산이 짧은 시간에 일어나도 수행 시간에 문제가 없도록 설계되어 있습니다. 따라서, 실시간 채팅 서비스에 적합한 데이터베이스입니다.

**3. 높은 사용 레퍼런스와 스프링과의 호환성**

MongoDB는 NoSQL 데이터베이스 중 가장 많은 사용 레퍼런스를 보유하고 있습니다. 또한, 스프링(Spring) 프레임워크와의 호환성이 뛰어나 **Spring Data MongoDB**를 통해 간편하게 구현할 수 있습니다.

**4. 인덱스 및 복잡한 쿼리 지원**

MongoDB는 인덱스를 지원하며, 복잡한 쿼리도 처리할 수 있는 기능을 제공합니다. 이는 채팅 데이터를 효율적으로 관리하고 검색하는 데 큰 도움이 됩니다. 또한, 수평 확장이 용이하여 대규모 데이터를 처리하는 데 적합합니다.

### **MySQL -> MongoDB 마이그레이션 과정**

자세한 MySQL -> MongoDB 마이그레이션 과정에 대해 더 자세히 알고 싶으시다면 아래 링크를 통해 확인해 주세요!

[🔗 [Spring boot] MySQL &rarr; MongoDB 마이그레이션 과정](/posts/spring-mysql-to-mongodb-migration/)

---

## **2. 채팅 조회 기능에 No-Offset 페이지네이션 적용**

현재 채팅 조회 기능은 Offset 페이지네이션 방식을 사용하고 있습니다. 이 방식은 *Page<GoodsChatMessage>* 객체를 반환하며, 다음과 같은 쿼리로 구현되어 있습니다. Offset 페이지네이션은 데이터가 많아질수록 성능 저하가 심해지는 문제가 있습니다.

```java
@Query(value = "{ 'chat_room_id': ?0 }", sort = "{ 'sent_at': -1 }")
Page<GoodsChatMessage> getChatMessages(Long chatRoomId, Pageable pageable);
```

### **Offset 페이지네이션의 문제점**

**1. 데이터베이스의 비효율적인 스캔**

Offset 페이지네이션은 데이터베이스가 OFFSET 값에 해당하는 위치까지 모든 데이터를 스캔해야 합니다. 예를 들어, OFFSET이 10,000인 경우, 데이터베이스는 처음부터 10,000개의 데이터를 모두 읽은 후, 10,001번째 데이터부터 반환합니다. 이때, 사용하지 않지만 버려지는 데이터가 많아지면서 데이터베이스에 불필요한 부하를 주게 됩니다.

**2. 전체 데이터 개수(totalCount) 계산의 비용**

전체 데이터 개수(*totalCount*)를 반환하기 위해 별도의 *COUNT* 쿼리를 실행합니다. 이 *COUNT* 쿼리는 전체 데이터를 스캔해야 하기 때문에 데이터 양이 많을수록 실행 시간이 길어집니다. 이는 데이터와 무관한 추가적인 부하를 발생시키며, 성능 저하로 이어집니다.

(단, *Page* 객체를 *List*를 반환한다면 *COUNT* 쿼리가 실행되지 않아 문제가 발생하지 않습니다.)

특히 이러한 문제점들은 채팅 데이터베이스와 같이 대규모 데이터를 다루는 환경에서 사용자가 많아질수록 심각한 성능 저하로 이어질 수 있습니다. 처음 채팅 조회 기능을 구현할 때는 Offset 페이지네이션 방식만 알고 있었기 때문에 이러한 문제점을 인지하지 못했던 것 같습니다.

이러한 잠재적인 성능 문제를 해결하기 위해 우리 팀은 채팅 조회 기능을 No-Offset 방식으로 변경하기로 결정했습니다. No-Offset 방식은 기존의 Offset 페이지네이션과 비교해 구현이 복잡하다는 단점이 있지만, 접근 방식을 달리하여 성능 개선을 할 수 있습니다.

### **No-Offset 방식으로 전환 이유**

**Offset에 비해 빠른 조회 속도**

No-Offset 방식은 키 값(예: 마지막으로 조회한 데이터의 ID 또는 타임스탬프)을 기준으로 다음 데이터를 조회합니다. 따라서, OFFSET 전까지 불필요한 데이터를 조회하지 않아 데이터베이스의 부하를 크게 줄이고, 조회 속도를 크게 개선할 수 있습니다.

또한 No-Offset 방식을 통해 조회된 데이터를 *List*로 반환합니다. 전체 데이터 개수를 계산하지 않아도 되기 때문에, COUNT 쿼리를 실행할 필요가 없습니다. 이는 추가적인 부하를 줄이고, 쿼리 실행 시간을 단축시킵니다.

### **No-Offset 적용 페이징 성능 개선 과정**

```java
@Override
public List<GoodsChatMessage> getChatMessages(Long chatRoomId, LocalDateTime lastSentAt, int size) {
    // 동적으로 조건 생성
    Criteria criteria = createCriteria(chatRoomId, lastSentAt);

    // Query 생성 및 조건 추가
    Query query = new Query(criteria);
    query.limit(size);
    query.with(Sort.by(Direction.DESC, "sent_at"));

    return mongoTemplate.find(query, GoodsChatMessage.class);
}

private Criteria createCriteria(Long chatRoomId, LocalDateTime lastSentAt) {
    Criteria criteria = Criteria.where("chat_room_id").is(chatRoomId);

    // lastSentAt 가 null 일 경우, 최신 메시지 조회
    if (lastSentAt != null) {
        criteria = criteria.and("sent_at").lt(lastSentAt);
    }

    return criteria;
}
```

1. *createCriteria()*
   - *MongoTemplate*과 *Criteria*를 통해 동적으로 조회 조건(*Criteria*)을 생성합니다.
   - *lastSentAt*이 *null*인 경우, 최신 메시지부터 조회하기 위함입니다.
2. *getChatMessages()*
   - 마지막 채팅 전송 시간(*lastSentAt*)보다 오래된 메시지를 최신순으로 *size*만큼 조회 후 반환합니다.

No-Offset을 적용한 페이징 성능 개선 과정에 대해 더 자세히 알고 싶으시다면 아래 링크를 통해 확인해 주세요!

[🔗 [Spring boot] No Offset 적용한 페이징 성능 개선 - MongoDB](/posts/spring-no-offset-paging-mongodb/)

---

## **3. 채팅 조회 기능에 Redis 캐싱 도입**

### **Redis 캐시 도입 배경**

채팅 서비스는 사용자들이 실시간으로 메시지를 주고받는 환경이기 때문에, 채팅 내역 조회가 빈번하게 발생합니다. 이미 이전에 No-Offset 페이지네이션을 도입하여 데이터베이스의 부하를 줄이고 조회 속도를 개선했습니다. 하지만 사용자가 매번 채팅을 조회할 때마다 데이터베이스에 직접 접근하는 것은 여전히 데이터베이스에 큰 부하를 줄 수 있습니다. 이러한 문제를 해결하고 조회 속도를 더욱 향상하기 위해 **Redis 캐싱을 도입**하기로 결정했습니다.

여러 캐시 스토어 중 Redis를 채택한 이유는 Redis의 풍부하고 편리한 자료구조와 높은 성능 때문이었습니다. Redis의 *Sorted Set* 자료구조를 활용하면 *Score*를 기준으로 데이터를 자동으로 정렬할 수 있습니다. 채팅 메시지를 캐싱할 때, 채팅 전송 시간(*sentAt*)을 *Score*로 사용하면 별도의 필터링이나 정렬 작업 없이도 데이터가 정렬된 형태로 관리됩니다. 이는 데이터를 조회한 후 필터링, 정렬을 하지 않아도 되는 편리함이 있었습니다.

또한 현재 프로젝트에서는 이미 Redis를 만료된 JWT 액세스 토큰의 블랙리스트 저장 용도로 사용하고 있습니다. 이로 인해 새로운 의존성을 추가할 필요가 없어 애플리케이션을 가볍게 유지할 수 있었습니다. 또한, Redis는 Docker 설정이 완료되어 있어 추가적인 설정이나 고민 없이 쉽게 통합할 수 있었습니다.

### **캐싱 전략**

채팅 내역 조회의 캐싱 전략으로 **Look Aside + Write Through 패턴**을 사용했습니다.

#### **캐시 쓰기 전략 - Write Through 패턴**

Write Through 패턴은 데이터를 캐시와 데이터베이스에 동시에 저장하여 데이터의 정합성을 유지합니다. 채팅 메시지가 전송될 때 다음과 같은 흐름으로 저장됩니다.

1. 채팅 메시지 전송
   - 사용자가 채팅 메시지를 전송하면, 서버는 해당 메시지를 처리합니다.
2. Redis 캐시에 저장
   - 메시지를 Redis 캐시에 저장됩니다.
   - Redis는 Sorted Set 자료구조를 사용하며, 전송 시간을 ***score***로 설정하여 메시지를 정렬합니다.
   - 저장된 메시지는 TTL(Time-To-Live)이 1시간으로 설정했습니다.
     - 이는 같은 채팅방에 속한 메시지들의 생명주기를 동일하게 유지하기 위함입니다.
3. MongoDB에 저장
   - 동시에 메시지는 MongoDB에 저장됩니다.
   - Write Through 패턴의 특징으로, 캐시와 데이터베이스 간의 데이터 정합성을 보장합니다.

#### **캐시 읽기 전략 - Look Aside 패턴**

Look Aside 패턴은 데이터를 조회할 때 캐시를 먼저 확인하고, 캐시에 데이터가 없을 경우 데이터베이스에서 조회하는 방식입니다. 채팅 내역을 조회할 때 다음과 같은 흐름으로 동작합니다.

1. 채팅 내역 조회 요청
   - 클라이언트가 특정 채팅방의 채팅 내역을 조회합니다.
   - 이때, 마지막 메시지의 전송 시간과 조회할 메시지 개수가 파라미터로 전달됩니다.
2. Redis 캐시에서 조회
   - Redis 캐시에서 마지막 메시지의 전송 시간을 기준으로 최신 메시지를 조회합니다.
   - 조회된 메시지가 요청한 메시지 개수만큼 충분하다면, 해당 메시지를 반환합니다.
3. Redis 캐시에 데이터가 없는 경우
   - MongoDB에 직접 접근하여 메시지의 전송 시간을 기준으로 최신 메시지를 조회합니다.
     - Redis 캐시에서 가져온 데이터가 있는 경우, 부족한 만큼만 데이터를 조회합니다.
4. 추가 데이터를 Redis에 캐싱
   - MongoDB에서 조회한 추가 데이터를 Redis 캐시에 저장합니다.
5. 데이터 반환
   - Redis 캐시와 MongoDB에서 조회한 데이터를 합쳐 클라이언트에게 반환합니다.

### **Redis 캐싱 도입 과정**

아래는 Redis 캐싱을 적용한 채팅 내역 조회 기능의 구현 코드입니다.

```java
// 채팅 내역 조회
private List<GoodsChatMessage> fetchMessagesFromCacheOrDB(Long chatRoomId, LocalDateTime lastSentAt, int size) {
    // 1. redis 캐싱 데이터 조회
    List<GoodsChatMessage> chatMessages = goodsChatCacheManager.fetchMessagesFromCache(chatRoomId, lastSentAt, size);

    // 2. 데이터가 비어있는 경우, DB 에서 size 만큼 조회
    if (chatMessages.isEmpty()) {
        chatMessages = messageRepository.getChatMessages(chatRoomId, lastSentAt, size);
        // 2-1. redis 저장
        goodsChatCacheManager.storeMessagesInCache(chatRoomId, chatMessages);
    }
    // 3. 데이터가 size 보다 적은 경우
    else if (chatMessages.size() < size) {
        // 3-1. 캐싱 데이터의 마지막 보낸 시간 추출
        lastSentAt = chatMessages.get(chatMessages.size() - 1).getSentAt();

        // 3-2. 부족한 개수만큼 DB 에서 조회 후 추가
        List<GoodsChatMessage> additionalMessages = messageRepository.getChatMessages(chatRoomId, lastSentAt, size - chatMessages.size());
        chatMessages.addAll(additionalMessages);

        // 3-3. redis 저장
        goodsChatCacheManager.storeMessagesInCache(chatRoomId, additionalMessages);
    }
    return chatMessages;
}
```

특정 채팅방의 메시지를 Redis 캐시에서 먼저 조회하고, 필요한 경우 MongoDB에서 추가로 가져오는 메서드입니다. 이를 통해 캐싱된 데이터가 존재하면 빠르게 조회하고, 부족한 경우 DB를 활용하여 효율적으로 데이터를 가져옵니다.

**1. Redis 캐시에서 메시지 조회**

```java
List<GoodsChatMessage> chatMessages = goodsChatCacheManager.fetchMessagesFromCache(chatRoomId, lastSentAt, size);
```

- Redis에 캐싱된 특정 채팅방의 채팅 메시지를 *No Offset* 방식으로 조회합니다.

**2. 캐시 데이터가 없는 경우 (DB에서 조회 후 캐싱)**

```java
if (chatMessages.isEmpty()) {
    chatMessages = messageRepository.getChatMessages(chatRoomId, lastSentAt, size);
    goodsChatCacheManager.storeMessagesInCache(chatRoomId, chatMessages);
}
```

- Redis 캐시에 메시지가 없다면, MongoDB에 직접 접근하여 데이터를 가져옵니다.
- 가져온 데이터는 **Redis 캐시에 저장(storeMessagesInCache())**하여 다음 조회 시 캐시에서 빠르게 조회될 수 있습니다.

**3. 캐시 데이터가 있지만, size보다 부족한 경우**

```java
else if (chatMessages.size() < size) {
    lastSentAt = chatMessages.get(chatMessages.size() - 1).getSentAt();
    List<GoodsChatMessage> additionalMessages = messageRepository.getChatMessages(chatRoomId, lastSentAt, size - chatMessages.size());
    chatMessages.addAll(additionalMessages);
    goodsChatCacheManager.storeMessagesInCache(chatRoomId, additionalMessages);
}
```

- Redis에서 가져온 데이터가 *size*보다 적을 경우, MongoDB에 직접 접근하여 추가 데이터를 가져옵니다.
- 조회한 메시지는 Redis에서 조회한 결과(*chatMessages*)에 추가하고, Redis 캐시에도 저장하여 다음 조회 시 캐시에서 빠르게 조회될 수 있습니다.

Redis 캐싱을 적용한 조회 성능 개선 과정에 대해 더 자세히 알고 싶으시다면 아래 링크를 통해 확인해 주세요!

[🔗 [Spring boot] Redis Cache를 적용한 조회 성능 개선](/posts/spring-redis-cache-query-performance/)

---

## **4. 성능 개선 결과 - with Jmeter**

앞으로 채팅 서비스의 성능 개선을 위해 데이터베이스 마이그레이션, No-Offset 페이지네이션, Redis 캐싱을 단계적으로 적용하며, 각 단계별로 조회 속도를 확인하여 실제로 성능 개선이 얼마만큼의 수치적인 차이를 보일 수 있는지 알아보고자 합니다.

테스트는 크게 **채팅 전송 테스트**, **채팅 조회 테스트**로 나누어서 테스트 플로우를 구성하였습니다.

채팅 전송은 **Jmeter**의 **WebScoket Sampler**를 통해 실제 웹소켓 통신 테스트를 구성하였고, MySQL vs MongoDB 환경만 비교하였습니다.

채팅 조회는 **Jmeter**의 **HTTP Request Sampler**를 통해 API 테스트를 구성하였습니다. 해당 테스트는 MySQL, MongoDB, No-Offset 페이지네이션 + Redis 캐싱 적용 후 3가지 환경으로 비교하였습니다.

성능 테스트 툴은 **Apache Jmeter**를 사용하였습니다.

k6, ngrinder, locust 등 다른 테스트 툴도 있었지만, 웹소켓 테스트를 지원하고, GUI를 통해 테스트를 구성할 수 있어 러닝 커브가 비교적 작은 Jmeter를 사용하였습니다. Jmeter는 1998년에 출시되고 현재까지 발전해 오면서 자세한 공식문서와 많은 개발자들이 작성한 레퍼런스들이 많기 때문에 처음 성능 테스트를 접하는 분들께 추천합니다.

### **테스트 환경**

- **Number of Threads (users) - 100**: 테스트에 사용할 쓰레드(유저 수)의 개수
- **Ramp-up period (seconds) - 50**: 쓰레드를 만드는데 소요되는 시간
- **Loop Count - 150**: 하나의 쓰레드에서 보내는 요청의 수

서버에 점진적으로 부하를 증가시켜 **응답 속도**와 **TPS(초당 처리 건수)**를 측정하기 위해, *쓰레드 수를 100, 반복 횟수를 150, 램프업 시간을 50초*로 설정했습니다. 이는 50초 동안 1초당 2명씩 사용자가 증가하며, 총 100명의 사용자가 각자 150건의 요청을 보내는 상황을 시뮬레이션합니다. 이를 통해 동시 접속 사용자 수가 증가할 때 서버가 처리 성능을 얼마나 안정적으로 유지하는지, 그리고 초당 처리 건수(TPS)와 응답 속도의 변화를 확인하고자 합니다.

> [!note]
> 최대한 테스트 환경을 동일하게 유지하기 위해 MySQL, MongoDB를 로컬 환경에서 실행하였습니다.
> 또한, 두 데이터베이스 모두 미리 20만 개의 더미 데이터를 생성한 후 성능 측정을 진행하였습니다.

### **테스트 플로우**

#### **1. WebSocket Sampler - 채팅 전송 테스트**

![WebSocket Thread Group](/assets/img/spring-websocket-chat-4-performance/01.dat)

웹소켓 기반의 채팅 성능 테스트를 위해 JMeter의 WebSocket Sampler를 활용하여 다음과 같은 테스트 플로우를 구성했습니다.

5개의 Sampler를 구성하였기 때문에 총 75,000번의 요청을 하게 됩니다.

1. OPEN CONNECT - 웹소켓 연결
2. SEND CONNECT - STOMP 프로토콜의 CONNECT 프레임을 통해 채팅 서버에 연결
3. SEND SUB - SUBSCRIBE 프레임을 통해 특정 채팅방을 구독
4. SEND MESSAGE - 채팅 메시지 전송
5. CLOSE CONNECT - DISCONNECT 프레임을 통해 서버와 연결 종료

> [!tip]
> 4번 Sampler에서 **senderId**, **roomId** 값을 다양하게 보내기 위해 **Counter** 변수를 사용했습니다. Jmeter에서는 Counter를 통해 동적으로 데이터를 생성하여 요청에 포함시킬 수 있습니다.
>
> ex) `[ "${counter}\",\"type\":\"TALK\",\"senderId\":\"1\", \"message\":\"부하테스트\"} ]`

#### **2. HTTP Request Sampler - 채팅 조회 테스트**

![HTTP Request Sampler](/assets/img/spring-websocket-chat-4-performance/02.png)

HTTP 요청 샘플러로는 채팅방 입장, 채팅 조회 API로 구성했습니다.

1. ENTER CHATROOM : 채팅방 입장 성공 시, 채팅방 정보와 최신 채팅 내역 20개를 반환합니다.
2. GET CHAT MESSAGES : 특정 채팅방의 채팅 내역을 조회합니다.
3. JWT Header Manager : **HTTP Header Manager**를 통해 각 요청마다 헤더에 JWT 토큰을 담습니다.
4. RandomDateTime Generator : **JSR223** 을 사용하여 무작위 시간대를 생성한 후 변수로 저장합니다.

**No-Offset 방식 적용을 위한 랜덤 시간 생성**

GET CHAT MESSAGES 샘플러에서 No-Offset 방식에 파라미터로 **마지막 채팅 전송 시간(*lastSentAt*)**이 필요합니다. Jmeter에서는 JSR223를 사용하여 코드를 통해 동적으로 변수를 생성할 수 있습니다.

```groovy
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.concurrent.ThreadLocalRandom

// 시작 시간 (MongoDB와 동일한 범위)
Instant startTime = Instant.parse("2025-01-28T13:48:00.000Z")
Instant endTime = Instant.parse("2025-02-14T12:10:00.000Z")

// 무작위 Timestamp 생성
long randomEpochMillis = ThreadLocalRandom.current().nextLong(startTime.toEpochMilli(), endTime.toEpochMilli())
Instant randomTimestamp = Instant.ofEpochMilli(randomEpochMillis)

// ISO 8601 포맷 변환 (밀리초 포함)
String formattedTimestamp = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS")
        .withZone(ZoneOffset.UTC)
        .format(randomTimestamp)

// JMeter 변수에 저장
vars.put("lastSentAt", formattedTimestamp)
```

위에서 생성한 lastSentAt 값을 JMeter의 Path Parameter에 삽입하여 No-Offset 기반의 채팅 메시지 조회 API를 호출했습니다.

ex) *api/v1/example/chat?lastSentAt=${lastSentAt}*

### **측정 결과**

#### **1. 채팅 전송 성능 비교 - WebSocket**

**MySQL 환경**

![MySQL 환경 요약 보고서](/assets/img/spring-websocket-chat-4-performance/03.dat)

**MongoDB 환경**

![MongoDB 환경 요약 보고서](/assets/img/spring-websocket-chat-4-performance/04.dat)

채팅 메시지를 전송하는 SEND MESSAGE 샘플러에서 최대 응답 시간이 MySQL 환경이 10ms로 MongoDB 환경보다 높게 나오긴 하였지만, 두 환경 모두 WebSocket을 사용한 채팅 시스템의 평균 응답 속도를 0ms로 성능이 우수하고 성능 차이가 난다고 보기에는 어려운 수준입니다.

테스트 전에는 MongoDB가 MySQL보다 훨씬 빠른 쓰기 성능을 제공할 것이라고 예상했습니다. 특히 MongoDB는 NoSQL 데이터베이스로, 쓰기 작업에서 일반적으로 더 나은 성능을 보이는 것으로 알려져 있기 때문입니다. 하지만 실제 테스트 결과는 예상과 달랐습니다.

이러한 결과가 나타난 이유는 채팅 전송 시 단순 메시지 저장뿐만 아니라, 해당 채팅방의 최근 메시지 및 최근 메시지 전송 시간 등을 함께 업데이트하기 때문에 트랜잭션이 포함되어 비슷한 성능이 나오지 않았나 싶습니다. MySQL은 트랜잭션 처리에 빠른 성능을 보이기 때문에 단순 쓰기 성능을 테스트했다고 보긴 어렵습니다.

#### **2. 채팅 조회 성능 비교 - HTTP Request**

**MySQL 환경**

![MySQL 환경 요약 보고서](/assets/img/spring-websocket-chat-4-performance/05.dat)

![MySQL 환경 통합 보고서](/assets/img/spring-websocket-chat-4-performance/06.dat)

![MySQL 환경 응답속도 그래프](/assets/img/spring-websocket-chat-4-performance/07.dat)

**MongoDB 환경**

![MongoDB 환경 요약 보고서](/assets/img/spring-websocket-chat-4-performance/08.dat)

![MongoDB 환경 통합 보고서](/assets/img/spring-websocket-chat-4-performance/09.dat)

![MongoDB 환경 응답속도 그래프](/assets/img/spring-websocket-chat-4-performance/10.dat)

**No-Offset 페이지네이션 + Redis 캐싱 적용**

![No-Offset + Redis 캐싱 도입 후 요약 보고서](/assets/img/spring-websocket-chat-4-performance/11.dat)

![No-Offset + Redis 캐싱 도입 후 통합 보고서](/assets/img/spring-websocket-chat-4-performance/12.dat)

### **결과 요약**

| 환경 | 평균 응답시간(ms) | 응답시간(95%) | TPS |
| --- | --- | --- | --- |
| 개선 전 (MySQL) | 592 | 736 | 132.7/sec |
| 개선 후 (MongoDB) | 396 | 577 | 176.0/sec |
| 개선 후2 (No-Offset + Redis) | 2 | 4 | 981.8/sec |

MySQL 환경에서 MongoDB 환경으로 마이그레이션 이후 평균 응답시간과 TPS는 **약 33% 성능 개선**을 확인할 수 있습니다.

MongoDB 환경에서 No-Offset 페이지네이션과 Redis 캐싱을 적용 후, TPS는 **약 639% 개선**되었습니다.

결론적으로 크게 3번의 성능 개선을 거치며 기존보다 **약 9배 정도 성능이 개선**된 것을 알 수 있었습니다.

> [!note]
> 3번째 환경에서 성능이 매우 좋아졌는데, 이는 로컬 환경에서 테스트를 진행하여 실제 배포 환경에서 발생하는 네트워크 지연, 데이터베이스 부하 등이 없는 이상적인 환경이기도 하고 캐시 적중률이 매우 높기 때문인 것 같습니다.
> 따라서 **실제 배포 환경에서 성능 테스트**를 하는 것이 더욱 정확하다고 할 수 있습니다..!

---

## **마치며**

이번 성능 개선 과정을 통해 채팅 서비스의 성능을 높이는 다양한 방법을 배울 수 있었습니다. 단순한 데이터베이스 변경만으로는 성능을 극적으로 개선하는 데 한계가 있다는 것을 깨달았고, No-Offset 페이지네이션, Redis 캐싱과 같은 최적화 기법이 얼마나 효과적인지 직접 경험할 수 있었습니다. 또한 이번 경험을 바탕으로 실시간 채팅 시스템을 설계할 때 어떤 방식으로 접근해야 할지에 대한 방향성을 더욱 명확히 할 수 있었습니다.

성능 개선을 하는 것 자체는 크게 어렵지 않았으나 JMeter를 활용하여 성능 테스트를 진행하면서 부하 테스트 툴을 제대로 이해하고, 적절한 테스트 환경을 설계하는 과정이 어려웠던 것 같습니다. 단순히 많은 요청을 보내는 것이 아니라, 적절한 쓰레드 수, 루프 카운트, Ramp-Up 시간 등을 설정하여 실제 환경과 유사한 조건에서 테스트를 진행하는 것이 중요하다는 것을 배웠습니다. 또한 이번 성능 테스트에서는 편의를 위해 로컬 환경에서 테스트를 진행하였지만, 테스트 환경에 따라 성능 수치가 다르게 나올 수 있다는 점도 배울 수 있었습니다.

성능 개선 과정은 단순히 기술을 적용하여 성능을 높이는 것뿐만 아니라, 시스템을 더 깊이 이해하고 최적의 환경을 구성하는 것입니다. 이번 경험을 통해 배운 지식들을 바탕으로 더 나은 서비스를 만들기 위해 노력해야겠습니다!

긴 글 읽어주셔서 감사합니다 :)
