---
title: "[Spring boot] Redis Cache를 적용한 조회 성능 개선"
date: 2025-01-31 21:57:45 +0900
categories: [Back-End, Spring]
tags: [Cache, Redis, Spring]
---

## 들어가며

현재 진행 중인 프로젝트의 채팅 기능에서 채팅 내역 조회가 빈번하게 발생하고 있습니다. 사용자가 매번 채팅을 조회할 때마다 데이터베이스에 직접 접근한다면, 사용자가 많아질 경우 데이터베이스에 큰 부하가 가해져 전체적인 서비스 성능이 저하될 수 있습니다. 특히, 채팅 서비스는 실시간으로 데이터가 생성되고 조회되는 특성을 가지고 있기 때문에, 데이터베이스의 부하를 줄이고 빠른 응답 속도를 제공하는 것이 중요합니다.

이러한 문제를 해결하기 위해 **캐싱(Caching) 기능**을 도입하기로 결정했습니다. 캐싱은 자주 조회되는 데이터를 임시 저장소에 저장해 두고, 동일한 요청이 들어왔을 때 데이터베이스에 접근하지 않고 캐시에서 빠르게 데이터를 제공하는 기술입니다. 이를 통해 데이터베이스의 부하를 줄이고, 사용자에게 더 나은 성능을 제공할 수 있습니다.  
  
이번 포스팅에서는 Spring 애플리케이션에서 도입할 수 있는 *캐시의 저장소의 종류와 캐싱 전략에*  대해 자세히 알아보고, 실제 프로젝트에 *Redis Cache를 적용하는 과정을*  코드와 함께 살펴보겠습니다.

---

## Cache Store를 Redis로 선택한 이유

![출처 - redis.io](/assets/img/spring-redis-cache-query-performance/01.png)

#### Redis 란 ?

Redis는 캐시 및 메시지 브로커로 사용되는 오픈소스인 **In Memory NoSQL DataBase**입니다.

제가 알아본 Redis의 특징 및 장점은 다음과 같습니다.

1. **데이터 영속성 지원 및 확장성**
   - Redis는 RDB(Snapshot)와 AOF(Append-Only File) 방식으로 데이터 영구 저장 가능  
     - 서버가 돌발 종료되는 경우, Disk에도 데이터를 저장하기 때문에 유실된 데이터를 복구할 수 있음
   - Redis는 Master - Salves구조를 가져 replication(복제)를 지원하여 하나 이상의 레플리카를 가질 수 있음
     - 여러 개의 클러스터를 운용할 수 있고, 높은 가용성을 가짐
2. **다양한 자료구조 및 용량 지원**
   - Memcached는 key 이름을 250 byte까지 제한하지만, Redis는 512mb까지 지원
   - 단순한 Key-Value뿐만 아니라, List, Set, Sorted Set, Hash, HyperLogLog 등 다양한 자료구조 제공
   - 이를 통해, 개발자 입장에게 캐싱 및 캐시된 데이터 조작에 편리함을 제공
3. **Spring Cache 연동 지원**
   - *spring-boot-starter-data-redis* 의존성을 추가하면 Spring Cache 연동이 편리함
   - *@Cacheable, @CachePut, @CacheEvict* 등 어노테이션을 통해 비교적 쉽게 캐시 적용 가능

#### 왜 Redis를 채택했는가 ?

첫째, Redis의 Sorted Set(Zset) 자료구조를 활용하면 Score를 기준으로 데이터를 자동으로 정렬할 수 있습니다.

예를 들어, 채팅 메시지를 캐싱할 때 전송 시간을 Score로 사용하면, 별도의 필터링이나 정렬 작업 없이도 데이터가 정렬된 형태로 관리됩니다. 이는 데이터를 조회한 후 필터링, 정렬을 하지 않아도 되는 편리함이 있었습니다.  
  
둘째, 현재 프로젝트에서는 이미 Redis를 만료된 JWT 액세스 토큰의 블랙리스트 저장 용도로 사용하고 있습니다. 이로 인해 새로운 의존성을 추가할 필요가 없어 애플리케이션을 가볍게 유지할 수 있었습니다. 또한, Redis는 Docker 설정이 완료되어 있어 추가적인 설정이나 고민 없이 쉽게 통합할 수 있었습니다.  
  
결론적으로, **Redis는 다양한 자료구조의 편리함**과 **기존 인프라와의 호환성** 덕분에 채택하게 되었습니다.

---

## 캐싱 전략

채팅 내역 조회의 캐싱 전략으로 **Look Aside + Write Through**패턴 조합을 사용했습니다.

### 캐시 쓰기 전략 - Write Through 패턴

Write Through 패턴은 데이터를 캐시와 데이터베이스에 동시에 저장하여 데이터의 정합성을 유지합니다.  
채팅 메시지가 전송될 때 다음과 같은 흐름으로 저장됩니다.

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

---

### 캐시 읽기 전략 - Look Aside 패턴

Look Aside 패턴은 데이터를 조회할 때 캐시를 먼저 확인하고, 캐시에 데이터가 없을 경우 데이터베이스에서 조회하는 방식입니다.  
채팅 내역을 조회할 때 다음과 같은 흐름으로 동작합니다.

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

> 아래 블로그에 캐시 설계 전략을 참고했습니다 !  
> [[REDIS] 캐시(Cache) 설계 전략 지침 총정리](https://inpa.tistory.com/entry/REDIS-%F0%9F%93%9A-%EC%BA%90%EC%8B%9CCache-%EC%84%A4%EA%B3%84-%EC%A0%84%EB%9E%B5-%EC%A7%80%EC%B9%A8-%EC%B4%9D%EC%A0%95%EB%A6%AC)

---

## Spring에 Redis Cache 적용하기

#### build.gradle

```java
implementation 'org.springframework.boot:spring-boot-starter-data-redis'
```

Redis를 사용하기 위한 *spring-boot-starter-data-redis* 의존성 추가

#### RedisConfig

```java
@Configuration
@RequiredArgsConstructor
public class RedisConfig {

    private final RedisProperties redisProperties;

    @Bean
    public RedisConnectionFactory redisConnectionFactory() {
        return new LettuceConnectionFactory(redisProperties.getHost(), redisProperties.getPort());
    }

    @Bean
    public RedisTemplate<String, String> jwtTokenRedisTemplate() {
        RedisTemplate<String, String> redisTemplate = new RedisTemplate<>();
        redisTemplate.setConnectionFactory(redisConnectionFactory());
        redisTemplate.setKeySerializer(new StringRedisSerializer());
        redisTemplate.setValueSerializer(new StringRedisSerializer());
        return redisTemplate;
    }

    @Bean
    public RedisTemplate<String, GoodsChatMessage> goodsChatCacheRedisTemplate() {
        // PolymorphicTypeValidator 를 생성하여 타입 검증
        BasicPolymorphicTypeValidator validator = BasicPolymorphicTypeValidator.builder()
                .allowIfSubType(Object.class)
                .build();

        // ObjectMapper 생성
        ObjectMapper objectMapper = new ObjectMapper();
        objectMapper.registerModule(new JavaTimeModule());
        objectMapper.activateDefaultTyping(validator, ObjectMapper.DefaultTyping.NON_FINAL);
        GenericJackson2JsonRedisSerializer genericJackson2JsonRedisSerializer = new GenericJackson2JsonRedisSerializer(objectMapper);

        // RedisTemplate 지정
        RedisTemplate<String, GoodsChatMessage> redisTemplate = new RedisTemplate<>();
        redisTemplate.setConnectionFactory(redisConnectionFactory());
        redisTemplate.setKeySerializer(new StringRedisSerializer());
        redisTemplate.setValueSerializer(genericJackson2JsonRedisSerializer);
        return redisTemplate;
    }
}
```

- *redisConnectionFactory()*
  - Redis 연결을 생성하는 *RedisConnectionFactory* 빈을 등록합니다.
  - *LettuceConnectionFactory*를 사용하여 Redis 서버에 연결합니다.

- goodsChatCacheRedisTemplate()
  - 캐싱에 사용되는 *RedisTemplate* 빈을 정의합니다.
  - key는 문자열로 구성되어, 기본 *StringRedisSerializer*를 사용했습니다.
  - value는 *GoodsChatMessage* 객체로 구성되어, *GenericJackson2JsonRedisSerializer*를 사용하여 객체를 JSON 형식으로 직렬화 및 역직렬화합니다.
  - 기본 *GenericJackson2JsonRedisSerializer*는 *Java*의 날짜와 시간 형식을 지원하지 않아, *ObjectMapper*를 생성하여 커스텀 클래스를 구현했습니다.

#### GoodsChatCacheManager

채팅 메시지를 Redis에 캐싱하고 관리하는 *GoodsChatCacheManager* 클래스입니다.

```java
@Component
public class GoodsChatCacheManager {

    private final RedisTemplate<String, GoodsChatMessage> redisTemplate;

    private static final String CACHE_KEY_FORMAT = "goods_chat_message::%d";
    private static final long DEFAULT_TTL_SECONDS = 3600;

    public GoodsChatCacheManager(
            @Qualifier("goodsChatCacheRedisTemplate") RedisTemplate<String, GoodsChatMessage> redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    // Redis Sorted Set 에 메시지를 저장
    public void storeMessageInCache(Long chatRoomId, GoodsChatMessage message) {
        storeMessagesInCache(chatRoomId, List.of(message));
    }

    // Redis Sorted Set 에 메시지 List 저장
    public void storeMessagesInCache(Long chatRoomId, List<GoodsChatMessage> messages) {
        for (GoodsChatMessage message : messages) {
            String cacheKey = formatCacheKey(chatRoomId);
            Double score = convertToScore(message.getSentAt());
            redisTemplate.opsForZSet().add(cacheKey, message, score);
        }
        setTTL(formatCacheKey(chatRoomId));
    }

    /**
     * Redis 에서 특정 채팅방의 메시지를 lastSentAt 기준으로 최신순으로 정렬하여 조회합니다.
     * @param chatRoomId 채팅방 ID (해당 채팅방의 메시지를 조회합니다.)
     * @param lastSentAt 메시지를 조회할 기준 시간 (null 일 경우 가장 최근 메시지를 조회합니다.)
     * @param size 조회할 메시지의 개수
     * @return 최신순으로 정렬된 조회된 메시지 List (메시지가 없으면 빈 리스트를 반환합니다.)
     */
    public List<GoodsChatMessage> fetchMessagesFromCache(Long chatRoomId, LocalDateTime lastSentAt, int size) {
        String cacheKey = formatCacheKey(chatRoomId);
        Set<GoodsChatMessage> messages;

        // lastSentAt이 null 인 경우, 가장 최근 메시지 조회
        if (lastSentAt == null) {
             messages = redisTemplate.opsForZSet().reverseRange(cacheKey, 0, size - 1);
        // lastSentAt을 기준으로 이전의 메시지를 최신순으로 정렬하여 조회
        } else {
            Double score = convertToScore(lastSentAt);
            messages = redisTemplate.opsForZSet().reverseRangeByScore(cacheKey, Double.NEGATIVE_INFINITY, score, 1, size);
        }

        if (messages == null || messages.isEmpty()) {
            return Collections.emptyList();
        }

        return new ArrayList<>(messages);
    }

    // Redis Sorted Set 에서 모든 메시지를 삭제
    public void evictMessagesFromCache(Long chatRoomId) {
        String cacheKey = formatCacheKey(chatRoomId);
        redisTemplate.opsForZSet().removeRange(cacheKey, 0, -1);
    }

    // TTL 설정 - 1시간
    private void setTTL(String cacheKey) {
        redisTemplate.expire(cacheKey, DEFAULT_TTL_SECONDS, TimeUnit.SECONDS);
    }

    private String formatCacheKey(Long chatRoomId) {
        return String.format(CACHE_KEY_FORMAT, chatRoomId);
    }

    // LocalDateTime 을 Redis Sorted Set 에서 사용하는 score 값으로 변환
    private Double convertToScore(LocalDateTime sentAt) {
        return (double) sentAt.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli();
    }
}
```

- *storeMessageInCache(), storeMessagesInCache()*
  - 단일 채팅 메시지와 여러 채팅 메시지를 Redis에 캐싱합니다.
  - 메시지의 전송 시간(*sentAt*)을 *convertToScore()* 메서드를 통해 ZSet에서 사용될 *Score*로 변환하여 저장합니다.
    - 이때, 메시지는 전송 시간(sentAt) 순으로 정렬되어 저장됩니다.
  - 메시지를 저장할 때마다 동일한 채팅방 ID의 TTL을 1시간으로 갱신하여, 해당 채팅방의 데이터들을 함께 유지되도록 관리합니다.

- *fetchMessagesFromCache()*
  - Redis에 캐싱된 특정 채팅방의 채팅 메시지를 *No Offset* 방식으로 조회합니다.
  - 채팅 조회가 처음인 경우 - *lastSentAt ==* *null*
    - ZSet의 *reverseRange()* 메서드를 통해 메시지를 최신 순으로 정렬해서 *size*만큼 가져옵니다.
    - ZSet은 *score*값을 기준으로 오름차순(오래된 순)으로 정렬되기 때문에 *reverse* 메서드를 사용했습니다.
  - 채팅 조회가 처음이 아닌 경우 - *lastSentAt* *!=* *null*
    - 마지막으로 전송된(가장 오래된) 메시지의 전송 시간(*lastSentAt*)을 *Score*로 변환한 후, 그보다 오래된 메시지를 최신 순으로 정렬해서 *size*만큼 가져옵니다.
    - *reverseRangeByScore*()를 사용할 때 *offset*을 1로 설정하는 이유는, *lastSentAt*을 포함한 메시지가 중복 조회되지 않도록 하기 위함입니다.
      - *reverseRangeByScore*()는 **min ≤ score ≤ max** 범위의 데이터를 가져오므로, *lastSentAt*의 메시지가 중복될 수 있습니다.

- *evictMessagesFromCache()*
  - Redis Sorted Set에서 특정 채팅방의 모든 메시지를 삭제합니다.
  - removeRange()를 사용하여 0부터 -1까지의 범위를 지정하여 해당 채팅방의 모든 메시지를 삭제합니다.

- *setTTL()*
  - Redis에 저장된 특정 채팅방의 데이터에 TTL(Time-To-Live, 만료 시간)을 설정합니다.
  - 만약 1시간 동안 새로운 메시지가 저장되지 않으면 해당 채팅방의 메시지는 자동 삭제됩니다.
- *formatCacheKey()*
  - 채팅방의 ID를 기반으로 Redis에서 사용할 캐시 키를 생성합니다.
  - 예를 들어, *chatRoomId = 123*인 경우 캐시 키는 *"goods_chat_message::123"* 이 됩니다.
- *convertToScore()*
  - LocalDateTime을 Redis Sorted Set에서 사용하는 *Score* 값(정렬 기준 값)으로 변환합니다.
  - *sentAt.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()*를 사용하여 *sentAt*을 밀리초 단위의 *Epoch Time(Double)*으로 변환합니다.

#### 실제 서비스에 Redis Cache 적용

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

```reasonml
else if (chatMessages.size() < size) {
    lastSentAt = chatMessages.get(chatMessages.size() - 1).getSentAt();
    List<GoodsChatMessage> additionalMessages = messageRepository.getChatMessages(chatRoomId, lastSentAt, size - chatMessages.size());
    chatMessages.addAll(additionalMessages);
    goodsChatCacheManager.storeMessagesInCache(chatRoomId, additionalMessages);
}
```

- Redis에서 가져온 데이터가 *size*보다 적을 경우,  MongoDB에 직접 접근하여 추가 데이터를 가져옵니다.
- 조회한 메시지는 Redis에서 조회한 결과(*chatMessages*)에 추가하고, Redis 캐시에도 저장하여 다음 조회 시 캐시에서 빠르게 조회될 수 있습니다.

---

## 조회 성능 비교 - Postman API 테스트

MongoDB에 **100만 개**의 더미 데이터를 삽입한 후, Postman을 이용해 API 테스트를 진행하였습니다.

**레디스 캐싱 도입 전**

![레디스 캐싱 도입 전 - 평균 30ms](/assets/img/spring-redis-cache-query-performance/02.png)

**레디스 캐싱 도입 후**

![캐싱되지 않은 상태 - 평균 40ms](/assets/img/spring-redis-cache-query-performance/03.png)

![Redis 저장 후 데이터 조회 - 평균 20ms](/assets/img/spring-redis-cache-query-performance/04.png)

캐싱되지 않은 상태(처음 데이터 조회)에서는 도입 전보다 평균 10ms 느리게 측정되었습니다.

그 이유는 Redis 캐시에 데이터를 저장하는 과정이 추가되었기 때문입니다. 기존에는 단순히 MongoDB에서 데이터를 조회하는 과정만 수행되었지만, 캐싱을 위한 Redis 저장 과정이 추가되면서 약간의 오버헤드가 발생한 것을 알 수 있습니다.

처음 데이터 조회 후, 동일한 데이터를 다시 요청할 경우 Redis에서 즉시 반환되므로 데이터베이스를 거치지 않아도 됩니다.

그 결과, 평균 조회 속도가 **30ms -> 20ms로 33% 개선**된 것을 알 수 있습니다.

> 이번 테스트는 로컬 환경에서 진행된 결과이므로, 실제 운영 환경에서는 추가적인 성능 차이가 발생할 수 있습니다.  
> JMeter 부하 테스트 툴을 사용하여 더욱 자세한 성능 비교 결과가 궁금하시다면 아래 글을 참고해 주세요!

[🔗 [Spring Boot] WebSocket 을 사용하여 채팅 서비스 구현하기(4) - 채팅 서비스 성능 개선 및 부하 테스트](/posts/spring-websocket-chat-4-performance/)

---

## 마치며

이번 경험을 통해 웹 서비스에서 사용되는 다양한 캐싱 전략에 대한 이해를 넓히고, 실제 프로젝트에 Redis 캐싱 기능을 도입하여 성능을 성공적으로 개선할 수 있었습니다.  
  
이전에 Redis를 활용해 JWT refresh token을 블랙리스트에 추가하는 작업을 구현해 본 적은 있었지만, 캐싱 기능을 구현하는 것은 이번이 처음이었습니다. 그래서 웹 서비스에서 사용되는 여러 캐싱 전략과 저장소, 그리고 Redis의 다양한 자료구조에 대해 깊이 공부를 하면서, 현재 CATCH-Mi 서비스의 채팅 기능 특성에 적합한 기술을 하나씩 적용해 나갔습니다.

채팅 조회 코드가 다소 복잡하게 구현되어 있다는 점은 아쉽지만, 꽤나 성공적으로 Redis 캐싱을 도입하고 성능 개선을 이끌어낼 수 있었다는 점에 만족스러운 경험인 것 같습니다.

긴 글을 읽어주셔서 감사합니다 :)

> 참고자료  
> [Spring Data Redis 공식 홈페이지](https://spring.io/projects/spring-data-redis)  
> [Redis Sorted Set 공식 홈페이지](https://redis.io/glossary/redis-sorted-sets/)  
> [REDIS 캐시 설계 전략 지침 총정리](https://inpa.tistory.com/entry/REDIS-%F0%9F%93%9A-%EC%BA%90%EC%8B%9CCache-%EC%84%A4%EA%B3%84-%EC%A0%84%EB%9E%B5-%EC%A7%80%EC%B9%A8-%EC%B4%9D%EC%A0%95%EB%A6%AC#write_through_%ED%8C%A8%ED%84%B4)
