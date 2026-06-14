---
title: "[Spring boot] No Offset 적용한 페이징 성능 개선 - MongoDB"
date: 2025-01-29 23:59:45 +0900
categories: [Back-End, Spring]
tags: [MongoDB, Spring]
---

## **들어가며**

CATCH-Mi 서비스의 성능 개선을 진행하면서, **No Offset Pagination**을 통해 페이징 기능을 효과적으로 개선할 수 있다는 것을 알게 되었습니다. 이번 글에는 *기존 Offset 방식과 No Offset 방식의 장단점을 비교*하고, 실제 서비스에 *No Offset 방식을 어떻게 적용했는지* 코드와 함께 그 과정을 정리해보고자 합니다.

> 페이지네이션이란 ?  
>   
> 페이지네이션(Pagination)은 대량의 데이터를 효율적으로 조회하기 위해 데이터를 일정한 크기(Page)로 나누어 조회하는 방식입니다. 이를 통해 사용자는 한 번에 모든 데이터를 처리하지 않고, 원하는 부분만 빠르게 조회할 수 있습니다. 페이지네이션은 웹 애플리케이션, 모바일 앱, API 등 다양한 환경에서 널리 사용되고 있습니다.

---

## **Offset Pagination**

#### **Offset 이란 ?**

Offset은 데이터 조회 시 **시작 위치를 지정하는 값**입니다.

예를 들어, 데이터베이스에서 100개의 데이터가 있을 때, *OFFSET* *= 20*은 21번째 데이터부터 조회하라는 의미입니다.

이는 페이지네이션에서 특정 페이지의 데이터를 가져오기 위해 사용됩니다.

```sql
SELECT *
FROM users
ORDER BY id
LIMIT 10	# 10개 데이터 조회
OFFSET 20;	# 20번째 데이터부터
```

위 쿼리는 *21번째 데이터 ~ 30번째 데이터*를 조회하게 됩니다.

#### **Offset Pagination**

offset Pagination은 페이징 정보(*pageNum*, *pageSize*)를 통해 다음과 같은 형태로 구성됩니다.

```sql
SELECT *
FROM users
WHERE 조건문
ORDER BY id DESC
OFFSET pageNum * pageSize
LIMIT pageSize
```

- **pageNum**: 현재 페이지 번호 (예: 1페이지, 2페이지)
- **pageSize**: 한 페이지에 표시할 데이터의 개수 (예: 10개, 20개)
- **OFFSET**: 조회를 시작할 위치 (예: pageNum * pageSize)
- **LIMIT**: 조회할 데이터의 개수 (예: pageSize)

offset Pagination은 페이징 정보를 통해 *LIMIT*, *OFFSET*을 설정하여 **손쉽게 페이지네이션을 적용**할 수 있다는 장점이 있습니다. 또한 사용자 입장에서 페이지 번호를 요청하여 **원하는 페이지를 바로 조회**할 수 있고, **이전/다음 페이지로 이동이 쉽습니다.**

![출처 - Okky](/assets/img/spring-no-offset-paging-mongodb/01.png)

#### **Offset Pagination 단점**

**1. 데이터가 많아질수록 성능 저하됩니다.**

offset Pagination은 데이터가 많아질수록 성능 저하가 매우 심해지는데, 그 이유는 offset 방식의 데이터베이스 동작 방식에 있습니다.

데이터베이스는 *OFFSET* 값이 커질수록 처음부터 해당 위치까지 모든 데이터를 스캔합니다.

예를 들어, *OFFSET*이 10,000인 경우, 데이터베이스는 10,000개의 데이터를 모두 읽은 후 10,001번째 데이터부터 반환하게 됩니다.

이러한 이유로 사용하지 않지만 버려지는 **즉, 의미 없이 읽어야 하는 행의 개수가 많아지면서** DB에 더욱 많은 부하를 주게 됩니다.

또한 전체 데이터 개수(*totalCount*) 반환할 경우, *totalCount*를 계산하기 위해 **별도의 *COUNT* 쿼리가 실행**됩니다.

이때, *COUNT* 쿼리는  전체 데이터를 스캔해야 하기 때문에 데이터의 양이 많을수록 실행 시간이 더욱 길어지게 되고, 데이터와 무관한 추가적인 부하를 주게 됩니다.

**2. 데이터 정합성 문제가 생길 수 있습니다.**

OFFSET Pagination은 데이터가 실시간으로 추가되거나 삭제될 때 데이터 정합성 문제가 발생할 수 있습니다.

- 데이터가 추가되는 경우 발생하는 중복 문제
  - 사용자가 1페이지를 조회한 후 새로운 데이터가 추가되는 경우, 기존 1 페이지에 있던 데이터 일부가 2 페이지로 밀려날 수 있습니다.
  - 밀려난 데이터가 2페이지에서 **다시 조회되는 데이터 중복**이 발생합니다.
- 데이터가 삭제되는 경우 발생하는 누락 문제
  - 사용자가 1 페이지를 조회한 후, 일부 데이터가 삭제되는 경우, 기존 2 페이지의 데이터가 앞으로(1 페이지) 당겨질 수 있습니다.
  - *OFFSET*은 고정된 개수만큼 건너뛰므로, 앞으로 당겨진 데이터를 **건너뛴 후 조회**하게 되어 **일부 데이터가 누락되는 현상**이 발생합니다.

Offset Pagination은 구현이 간단하고 직관적이라는 장점이 있지만, 데이터 양이 많아질수록 성능 저하, 불필요한 COUNT 쿼리 실행, 데이터 정합성 문제 등의 단점이 있습니다. 이러한 문제는 **No Offset Pagination**을 통해 해결할 수 있습니다. No Offset 방식은 데이터베이스 부하를 줄이고, 실시간 데이터 변경에 대한 정합성 문제도 해결할 수 있는 효과적인 방법입니다.

---

## **No Offset Pagination**

No Offset Pagination은 *OFFSET*을 사용하지 않고, **마지막으로 읽은 데이터**를 기반으로 조건문을 통해 다음 데이터를 조회하는 방식입니다. *OFFSET*을 사용하지 않고 특정 데이터 이후의 값을 가져올 수 있기 때문에 필요한 *pageSize*만큼의 데이터만 스캔함으로 첫 번째 페이지를 읽는 것과 동일한 성능을 유지할 수 있습니다.

이러한 특징으로 No Offset 방식은 대량의 데이터를 조회할지라도 성능이 저하되지 않습니다. 또한 **특정 기준**(예: 마지막 조회 ID)을 통해 정확한 범위를 조회하기 때문에 데이터가 변동되어도 중복되거나 누락되는 **데이터의 정합성 문제**도 발생하지 않습니다.

Offset Pagination

```sql
SELECT *
FROM users
WHERE 조건문
ORDER BY id DESC
OFFSET pageNum * pageSize
LIMIT pageSize
```

No Offset Pagination

```sql
SELECT *
FROM users
WHERE 조건문
AND id < 마지막 조회 id 
ORDER BY id DESC
LIMIT pageSize
```

#### **No Offset Pagination 단점**

No Offset 방식은 성능이 빠르고, 데이터 정합성 문제가 없다는 장점이 있지만, 몇 가지 단점도 존재합니다.

**1. Where절에 사용되는 기준 Key 값이 중복이 가능할 경우 사용할 수 없습니다.**

No Offset 방식은 일반적으로 정렬된 데이터 집합에서 특정 기준 Key 값을 사용하여 다음 페이지를 가져오는 방식입니다. 그러나 기준 Key 값이 중복될 경우, 어떤 데이터가 다음 페이지에 포함되어야 하는지 명확히 결정할 수 없습니다.

예를 들어, 여러 개의 데이터가 같은 기준 Key 값을 가질 경우, 페이지네이션이 불확실해지며, 결과적으로 데이터의 일관성이 떨어질 수 있습니다.

**2. 원하는 페이지로 바로 접근할 수 없습니다.**

No Offset 방식은 페이지 번호를 기반으로 데이터를 가져오는 것이 아니라, 특정 기준값(예: 마지막으로 읽은 데이터의 ID)을 기반으로 다음 데이터를 가져옵니다. 따라서 사용자가 특정 페이지(예: 5페이지)로 바로 접근하고 싶을 경우, 그 페이지에 마지막으로 읽은 데이터를 알 수 없기 때문에 바로 접근할 수 없습니다.

**3. Offset Pagination보다 구현이 다소 복잡합니다.**

No Offset 방식은 기준 Key 값을 추적하고, 이를 기반으로 쿼리를 작성해야 하므로 더 많은 로직이 필요합니다.

예를 들어, 첫 페이지를 조회할 때는 기준 Key 값이 없기 때문에 일반적으로 *null* 값이나 특정 초기 값을 사용하여 쿼리를 작성해야 하므로 동적 쿼리를 구현하는 것이 필요하게 됩니다. 따라서 페이징 조건이 복잡해질수록 쿼리 또한 상당히 복잡해질 수 있습니다.

#### **결론 - No Offset Pagination VS Offset Pagination**

#### **No Offset Pagination이 적합한 경우**

1. **대량의 데이터를 다루는 경우**
   - 실시간 채팅, 로그 조회, 무한 스크롤처럼 순차적으로 데이터를 보여줘야 하는 경우에 적합합니다.
   - 필요한 데이터만 스캔하기 때문에 데이터베이스 부하가 적고, 빠르게 데이터를 가져올 수 있습니다.
   - 데이터가 아무리 많아도 성능이 크게 떨어지지 않습니다.
2. **데이터 정합성이 중요할 때**
   - 데이터가 실시간으로 추가되거나 삭제되더라도 중복이나 누락 없이 일관된 데이터를 제공할 수 있습니다.

#### 

#### **Offset Pagination이 적합한 경우**

1. **사용자 경험(UX)이 중요할 때**
   - 사용자가 특정 페이지 번호를 눌러 원하는 페이지로 바로 이동해야 하는 경우에 적합합니다.
   - 예: 게시판, 상품 목록처럼 페이지 번호를 통해 이동하는 서비스.
2. **데이터 양이 적을 때**
   - 데이터가 많지 않아 성능 저하가 크게 문제되지 않는 경우, 간단하게 구현할 수 있습니다.
   - *LIMIT*과 *OFFSET*을 사용하여 쉽게 페이지네이션을 구현할 수 있어 빠른 개발이 가능합니다.

결국, 서비스의 특성과 요구사항을 면밀히 분석하여 상황에 맞는 페이징 방식을 선택하는 것이 중요합니다.

각 방식마다 명확한 장단점이 존재하기 때문에, **서비스의 특성과 요구사항**을 면밀히 살펴보고 현재 서비스의 적합한 최적의 방식을 적용하면 효과적인 성능 개선을 이룰 수 있습니다.

---

## **실제 서비스에 No Offset Pagination 적용하기**

#### **GoodsChatMessageRepository.java**

```java
public interface GoodsChatMessageRepository extends MongoRepository<GoodsChatMessage, String> {
    /**
     * 특정 채팅방의 메시지를 페이징 처리하여 조회합니다.
     * 메시지는 전송된 시간(sent_at) 기준으로 오름차순으로 정렬됩니다.
     */
    @Query(value = "{ 'chat_room_id': ?0 }", sort = "{ 'sent_at': -1 }")
    Page<GoodsChatMessage> getChatMessages(Long chatRoomId, Pageable pageable);
}
```

- 현재 채팅방 ID를 통해 채팅 내역을 조회하는 getChatMessages() 메서드는 Offset Pagination을 사용하고 있습니다.
- *Pageable* 파라미터의 *pageSize, pageNum*을 통해 페이징 요청 정보를 받습니다.
- *Page <T>는* 페이지네이션 결과를 담는 객체로, 전체 데이터 개수(*totalCount*)와 함께 페이지 단위의 데이터를 반환합니다.

해당 메서드에서는 총 두 개의 **offset 기반 페이징 쿼리**와 **전체 데이터 개수를 가져오는 count 쿼리**가 실행됩니다.

```java
// offset Pagination
db.goodsChatMessage.find({ "chat_room_id": <chatRoomId> })
                   .sort({ "sent_at": -1 })
                   .skip(offset)
                   .limit(pageSize)
                   
// count
db.goodsChatMessage.count({ "chat_room_id": <chatRoomId> })
```

> 현재 getChatMessages()는 Pageable을 사용하므로, 내부적으로 skip()과 limit()이 적용됩니다.  
> MongoDB에서 Offset 기반 페이지네이션은 skip()과 limit()을 사용하여 구현됩니다.  
> MongoDB에서 skip()은 MySQL의 offset()과 동일한 동작 원리를 가집니다.

#### **No Offset 구현하기**

기존 채팅 내역 조회에는 데이터를 전송 시간 기준 최신순으로 정렬하고 있습니다.

No Offset 방식을 구현하기 위해서는 기준 값을 가장 오래된(마지막) 채팅의 전송 시간을 저장하고, 다음 페이지를 요청할 때 해당 시간을 기준으로 더 오래된 메시지를 *pageSize*만큼 가져오는 방식으로 구현할 수 있습니다.

그리고 처음 채팅을 조회할 때는 마지막으로 조회한 채팅 데이터가 없기 때문에 이를 어떻게 처리할지 고민해야 합니다.

저의 경우 클라이언트로부터 마지막 채팅 전송 시간(*lastSentAt*)을 *null* 값으로 요청받고, *MongoTemplate*을 통해 동적 쿼리를 구현하였습니다.

#### **GoodsChatMessageRepositoryCustom.java**

```java
public interface GoodsChatMessageRepositoryCustom {
    List<GoodsChatMessage> getChatMessages(Long chatRoomId, LocalDateTime lastSentAt, int size);
}
```

- Spring Data MongoDB의 기본 제공 기능만으로는 No Offset 방식의 페이징을 지원하기 어렵기 때문에, 커스텀 리포지토리 인터페이스를 별도로 정의했습니다.
- *getChatMessages(Long chatRoomId, LocalDateTime lastSentAt, int size)* 메서드를 선언하고, 실제 구현은 *GoodsChatMessageRepositoryCustomImpl*에서 수행합니다.
- *GoodsChatMessageRepository* 인터페이스는 해당 인터페이스를 상속받아서 메서드를 사용합니다.

#### **GoodsChatMessageRepositoryCustomImpl.java**

```java
@RequiredArgsConstructor
public class GoodsChatMessageRepositoryCustomImpl implements GoodsChatMessageRepositoryCustom {

    private final MongoTemplate mongoTemplate;

    /**
     * 주어진 chatRoomId의 메시지 중에서
     * lastSentAt 보다 오래된 메시지를 최대 size 만큼 반환
     * 메시지는 sent_at 기준으로 내림차순 정렬됩니다.
     */
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
}
```

- *createCriteria()* 메서드를 통해 동적으로 조회 조건(*Criteria*)을 생성합니다.
- *Query* 객체를 생성하여 해당 *Criteria*를 적용하고, 결과를 *sent_at* 기준 내림차순 정렬 후, *size*만큼 제한하여 조회합니다.

변경된 메서드는 하나의 **No Offset 기반 페이징 쿼리가** 실행됩니다.

```java
db.goodsChatMessage.find(
  { 
    "chat_room_id": <chatRoomId>,
    "sent_at": { "$lt": ISODate(<lastSentAt>) }  // lastSentAt보다 오래된 메시지만 조회
  }
).sort(
  { "sent_at": -1 }          // 최신 메시지부터 정렬 (내림차순)
).limit(<pageSize>);
```

이를 통해 기존에 발생했던 불필요한 **count() 쿼리가 실행되지 않도록**하여 성능을 개선할 수 있습니다. 또한, **offset()을 사용하지 않기 때문에** 데이터의 양이 증가해도 **첫 페이지를 읽는 것과 같은 성능을 유지**할 수 있습니다.

---

## **조회 성능 비교 - Postman API 테스트**

MongoDB에 **100만 개**의 더미 데이터를 삽입한 후, Postman을 이용해 API 테스트를 진행하였습니다.

**기존 Offset 페이지네이션 (인덱스 O)**

![첫번째 페이지 조회 속도 (평균 200ms)](/assets/img/spring-no-offset-paging-mongodb/02.png)

![마지막 페이지 조회 속도 (평균 400ms)](/assets/img/spring-no-offset-paging-mongodb/03.png)

**변경 후 No-Offset 페이지네이션 (인덱스 O)**

![첫번째 페이지 조회 속도(평균 30ms)](/assets/img/spring-no-offset-paging-mongodb/04.png)

![마지막 페이지 조회 속도 (평균 30ms)](/assets/img/spring-no-offset-paging-mongodb/05.png)

- 첫 번째 페이지 조회 속도
  - 기존 Offset 페이지네이션 로직을 사용할 때 첫번째 페이지 조회 속도가 200ms로 느리게 조회되는 이유는 count 쿼리 때문입니다.
  - COUNT 쿼리를 제거한 결과, 조회 속도가 **6.6배 개선**된 것을 확인할 수 있습니다.
- 마지막 페이지 조회 속도
  - Offset 페이지네이션 방식에서 마지막 페이지 조회 속도가 2배가 더 느리게 측정되었습니다.
  - 그 이유는 Offset 때문에 필요없는 데이터까지 스캔하기 때문입니다.
  - No-Offset 방식으로 변경한 결과, 마지막 페이지 조회 속도는 **13.3배 개선**된 것을 확인할 수 있습니다.

결과적으로 No-Offset 페이지네이션 방식에서는 **조회 페이지에 관계없이 일정한 크기의 데이터만 조회**하므로, **조회 속도의 차이가 발생하지 않음**을 확인할 수 있었습니다. 또한 데이터가 많아질수록 **Offset 페이지네이션과 No-Offset 페이지네이션 간의 성능 차이는 더욱 커질 것으로 예상**됩니다.

> 이번 테스트는 로컬 환경에서 진행된 결과이므로, 실제 운영 환경에서는 추가적인 성능 차이가 발생할 수 있습니다.  
> JMeter 부하 테스트 툴을 사용하여 더욱 자세한 성능 비교 결과가 궁금하시다면 아래 글을 참고해주세요!

---

## **마치며**

이번 경험을 통해 *No Offset Pagination* 방식을 실제 서비스에 적용하여, 성능 개선을 할 수 있었습니다. *Offset Pagination* 방식은 단순하고 직관적이지만, 데이터 양이 많아질수록 성능이 저하되는 단점이 있었습니다. 이에 반해 *No Offset Pagination*은 **첫 페이지와 같은 성능을 유지**하면서, **데이터 정합성 문제도 해결**할 수 있음을 알 수 있었습니다.

하지만 사용자의 경험(UX)이 중요한 서비스와 같이 *Offset* *Pagination*을 사용하는 것이 더 적합한 경우가 있습니다.  결국 *No Offset Pagination* 방식도 하나의 방법일 뿐, **서비스 특성과 현재 상황을 고려하여 적합한 기술을 선택하는 것**이 매우 중요합니다.

긴 글 읽어주셔서 감사합니다 :)

[🔗 [Spring Boot] WebSocket 을 사용하여 채팅 서비스 구현하기(4) - 채팅 서비스 성능 개선 및 부하 테스트](/posts/spring-websocket-chat-4-performance/)
