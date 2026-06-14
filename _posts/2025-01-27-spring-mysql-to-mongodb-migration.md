---
title: "[Spring boot] MySQL &rarr; MongoDB 마이그레이션 과정"
date: 2025-01-27 17:22:23 +0900
categories: [Back-End, Spring]
tags: [mongodb, Spring]
---

## 들어가며

이번 포스팅에서는 MySQL로 구현된 채팅 데이터베이스를 MongoDB로 마이그레이션 하고, **bwildvogel** 라이브러리를 사용하여 스프링 내장 MongoDB를 띄워 테스트 코드를 구현하는 과정을 다뤄보겠습니다.

이미 JPA로 구현된 엔티티를 MongoDB로 마이그레이션 하는 이유는 데이터베이스의 스키마가 자주 변경되어 유연성이 필요하거나 관계형 데이터베이스가 필요 없는 경우 등 여러 가지가 있을 수 있습니다.

기존에 MySQL로 저장된 채팅 데이터베이스를 MongoDB로 마이그레이션 한 이유는 크게 두 가지입니다.

#### **1. 유연성과 스키마 변경의 용이성**

채팅 서비스는 기능 추가나 요구사항 변경에 따라 데이터 구조가 자주 바뀔 수 있습니다. MongoDB는 스키마리스(NoSQL) 데이터베이스로, 이러한 변경에 유연하게 대응할 수 있습니다. 예를 들어, 새로운 필드를 추가하거나 기존 필드를 삭제하는 작업이 관계형 데이터베이스보다 훨씬 간단합니다.

#### **2. 수평 확장성과 조회 성능 이점**

채팅 데이터는 사용자가 조금만 증가해도 기하급수적으로 늘어나는 특성이 있습니다. MongoDB는 **수평 확장(Sharding)**이 용이하여 대규모 데이터를 효율적으로 처리할 수 있습니다. 또한, 채팅 서비스는 조회 작업이 매우 빈번하게 발생하므로, 데이터 접근 비용(I/O)을 줄이기 위해 MongoDB의 인메모리 캐싱과 인덱싱 기능을 적극 활용할 수 있습니다.

---

## Spring boot + MongoDB 설정

#### build.gradle

```bash
// Spring Data MongoDB 의존성 추가
implementation 'org.springframework.boot:spring-boot-starter-data-mongodb'
```

MongoDB를 사용하기 위해 **spring-boot-starter-data-mongodb** 의존성을 추가했습니다.  
Spring Data MongoDB의 핵심 기능을 제공하며, MongoDB와의 연동을 쉽게 구현할 수 있도록 도와줍니다.

#### application.yml

```bash
# URI를 사용한 설정
spring:
  data:
    mongodb:
      uri: mongodb://<이름>:<비밀번호>@<호스트명>:<포트번호>/<데이터베이스이름>

# 또는 개별 설정을 사용할 경우
spring:
  data:
    mongodb:
      host: <호스트명>
      port: <포트번호>
      database: <데이터베이스이름>
      username: <이름>
      password: <비밀번호>
      
# 다른 옵션들
spring:
  data:
    mongodb:
      authentication-database: <인증 데이터베이스명>
      uuid-representation: <UUID를 BSON으로 변환할 때 사용할 표현 방식>
      replica-set-name: <replica set 이름>
      field-naming-strategy: <필드 이름 변환 방식>
      auto-index-creation: <인덱스 자동생성 여부>
      ssl:
        bundle: <ssl 접속을 위한 bundle 설정 이름>
        enabled: <ssl 접속 사용 여부>
```

다음으로 application.yml에 MongoDB 연결정보를 추가합니다.

MongoDB에서는 URI에 연결 정보를 모두 포함하여 한 줄로 간편하게 설정할 수 있습니다.

***설명 자세히 보기 (더보기 클릭)***

더보기

**1. URI**

MongoDB에 연결하는 URI에 연결 정보를 모두 포함하여 한 줄로 설정할 수 있습니다.

**2. authentication-database (인증 데이터베이스명)**

MongoDB에서 인증을 처리할 데이터베이스 이름을 지정합니다.

기본적으로 인증은 admin 데이터베이스에서 이루어지지만, 다른 데이터베이스에서 인증을 처리하려면 이 옵션을 설정합니다.

**3. uuid-representation (UUID 표현 방식)**

MongoDB에서 UUID를 저장할 때 사용되는 BSON 표현 방식을 설정합니다.

**4. replica-set-name (Replica Set 이름)**

MongoDB Replica Set을 사용할 경우, 해당 Replica Set 이름을 지정합니다.

**5. field-naming-strategy (필드 이름 변환 방식)**

MongoDB에서 사용하는 필드 이름을 변환하는 전략을 설정할 수 있습니다.

기본적으로 CamelCase가 사용되지만, 다른 네이밍 규칙(예: snake_case)을 적용할 수 있습니다.

**6. auto-index-creation (인덱스 자동 생성 여부)**

MongoDB에서 데이터베이스에 저장될 때, 자동으로 인덱스를 생성할지 여부를 설정합니다.

**7. ssl (SSL 접속 설정)**

**ssl.enabled**: MongoDB와의 연결에서 SSL을 사용할지 여부를 설정합니다.

**ssl.bundle**: SSL 인증서 번들을 사용할 경우 설정하는 항목입니다.

#### MongoConfig.java

```java
@Configuration
public class MongoConfig {

    @Bean
    public MappingMongoConverter mappingMongoConverter(MongoDatabaseFactory mongoDatabaseFactory,
                                                       MongoMappingContext mongoMappingContext) {
        DbRefResolver dbRefResolver = new DefaultDbRefResolver(mongoDatabaseFactory);
        MappingMongoConverter converter = new MappingMongoConverter(dbRefResolver, mongoMappingContext);
        converter.setTypeMapper(new DefaultMongoTypeMapper(null));

        return converter;
    }
}
```

MongoDB는 데이터를 컬렉션에 문서로 저장할 때, 객체를 BSON 형식으로 변환합니다.

이때,  *_class* 라는 필드가 자동으로 추가하여 저장하는데, 이는 MongoDB에서 객체 지향 구조를 문서로 매핑할 때 해당 객체의 타입 정보를 담는 메타 데이터입니다.

*ex) "_class": "com.example.chat.entity.ChatMessage"*

이러한 메타 데이터는 불필요한 저장 공간을 낭비하게 됨으로 위 설정을 통해 저장되는 것을 막을 수 있습니다.

---

## Entity to Document

#### 기존 채팅 엔티티

```java
@Entity
@Table(name = "goods_chat_message")
public class GoodsChatMessage {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumns({
            @JoinColumn(name = "member_id", referencedColumnName = "member_id"),
            @JoinColumn(name = "chat_room_id", referencedColumnName = "chat_room_id")
    })
    @OnDelete(action = OnDeleteAction.CASCADE)
    private GoodsChatPart goodsChatPart;

    @Column(name = "content", nullable = false, columnDefinition = "TEXT")
    private String content;

    @Column(name = "sent_at", nullable = false)
    private LocalDateTime sentAt;

    @Enumerated(EnumType.STRING)
    @Column(name = "message_type", nullable = false)
    private MessageType messageType;

    @PrePersist
    public void prePersist() {
        this.sentAt = LocalDateTime.now();
    }
}
```

#### 

#### 변경된 채팅 도큐먼트

```java
@Document(collection = "goods_chat_message")
@CompoundIndexes({
        @CompoundIndex(name = "idx_chat_room_id_sent_at", def = "{ 'chat_room_id': 1, 'sent_at': -1 }")
})
public class GoodsChatMessage {

    @Id
    private String id;

    @Field(name = "chat_room_id")
    private Long chatRoomId;

    @Field(name = "member_id")
    private Long memberId;

    @Field(name = "content")
    private String content;

    @Field(name = "sent_at")
    private LocalDateTime sentAt;

    @Field(name = "message_type")
    private MessageType messageType;

}
```

- *@Id*는 MongoDB에서 각 문서의 고유 식별자로 사용됩니다.
  - 보통 *ObjectId* 혹은 *String* 타입으로 선언하며, 문서 저장 시 자동으로 매핑됩니다.
- *@Entity → @Document*로 변경하여 MongoDB 컬렉션과 매핑합니다.
  - *@Document(collection = "")* 옵션으로 문서를 저장할 컬렉션을 지정합니다.
- *@CompoundIndexes, @CompoundIndex* 어노테이션을 통해 복합 인덱스를 지정합니다.
  - *name* 옵션에는 인덱스의 이름을, *def* 옵션에는 필드를 정의합니다. 1은 오름차순, -1은 내림차순을 의미합니다.

- *@Column → @Field*로 변경하여 필드 이름을 지정합니다.
  - MongoDB는 *Enum*을 문자열로 저장할 수 있으므로, 추가 설정 없이 *@Field*로 매핑할 수 있습니다.
  - JPA에서 설정한 연관관계는 MongoDB에서 사용할 수 없으므로 해당 *id*를 개별 필드로 대체합니다.

---

## JpaRepository to MongoRepository

#### 기존 채팅 리포지토리

```java
public interface GoodsChatMessageRepository extends JpaRepository<GoodsChatMessage, Long> {

    @Query("""
        SELECT cm
        FROM GoodsChatMessage cm
        WHERE cm.goodsChatPart.goodsChatRoom.id = :chatRoomId
        ORDER BY cm.sentAt DESC
        """)
    Page<GoodsChatMessage> getChatMessages(@Param("chatRoomId") Long chatRoomId, Pageable pageable);
}
```

#### 변경된 채팅 리포지토리

```java
public interface GoodsChatMessageRepository extends MongoRepository<GoodsChatMessage, String> {

    @Query(value = "{ 'chat_room_id': ?0 }", sort = "{ 'sent_at': -1 }")
    Page<GoodsChatMessage> getChatMessages(Long chatRoomId, Pageable pageable);
    
    void deleteAllByChatRoomId(Long chatRoomId);
}
```

- 기존에는 JpaRepository 인터페이스를 사용하여 SQL 기반 데이터베이스와 매핑하였지만, MongoDB는 *MongoRepository*를 사용하여 NoSQL 컬렉션과 매핑됩니다.
- *Spring Data MongoDB* 는 *org.springframework.data.mongodb* 라이브러리의 *@Query* 어노테이션을 통해 쿼리 메서드를 지원합니다.
  - JSON 기반의 MongoDB 쿼리를 작성해야 합니다.
  - value 옵션을 통해 파라미터와 매핑하고, sort 옵션을 통해 정렬 기준을 정합니다.
  - 자세한 내용은 [스프링 몽고디비 공식문서](https://docs.spring.io/spring-data/mongodb/reference/mongodb/repositories/query-methods.html)를)를 참고해 주세요!
- *deleteAllByChatRoomId()* 메서드와 같이 기존 메서드 네이밍을 통한 쿼리도 가능합니다.
  - 기존에는 영속성 전이를 통해 채팅 메시지를 삭제했었는데, DB 변경으로 채팅 메시지만 따로 삭제하는 메서드를 추가했습니다.

#### 실제 저장된 채팅 메시지

![MongoDB Compass](/assets/img/spring-mysql-to-mongodb-migration/01.png)

### [ 트러블 슈팅] MongoDB LocalDateTime 저장 시 UTC로 저장되는 문제

[🔗 [Spring Boot] MongoDB LocalDateTime 저장 시 UTC로 저장되는 문제](/posts/spring-mongodb-localdatetime-utc/)

### [ 트러블 슈팅] MongoDB 트랜잭션 미적용 문제

[🔗 [Spring Boot] MongoDB와 MySQL의 이기종 트랜잭션 문제 해결](/posts/spring-mongodb-mysql-heterogeneous-transaction/)

---

## 테스트 - Embedded MongoDB 사용

JPA 사용 시 H2를 사용하는 것처럼 인메모리 MongoDB를 추가하는 방법입니다 !

관련 내용으로는 여러 가지 방법이 있지만 별 다른 설정 없이 쉽게 구현할 수 있는 *bwaldvogel* 라이브러리를 통해 구현했습니다.

[🔗 GitHub - bwaldvogel/mongo-java-server: Fake implementation of MongoDB in Java that speaks the wire protocol. Fake implementation of MongoDB in Java that speaks the wire protocol. - bwaldvogel/mongo-java-server github.com](https://github.com/bwaldvogel/mongo-java-server)

#### bwaldvogel 의존성 추가

```bash
testImplementation 'de.bwaldvogel:mongo-java-server:1.46.0'
```

테스트 환경에서만 사용되도록 *testImplementation*으로 의존성을 추가해 줍니다.

#### MongoTestServerConfig.java

```java
public class MongoTestServerConfig {

    @Bean
    public MongoTemplate mongoTemplate(MongoDatabaseFactory mongoDbFactory) {
        return new MongoTemplate(mongoDbFactory);
    }

    @Bean
    public MongoDatabaseFactory mongoDbFactory(MongoServer mongoServer) {
        String connectionString = mongoServer.getConnectionString();
        return new SimpleMongoClientDatabaseFactory(connectionString + "/test");
    }

    @Bean(destroyMethod = "shutdown")
    public MongoServer mongoServer() {
        MongoServer mongoServer = new MongoServer(new MemoryBackend());
        mongoServer.bind();

        return mongoServer;
    }
}
```

- 테스트 환경에서 사용할 Embedded MongoDB 서버를 구성하는 설정 클래스입니다.
- *MemoryBackend()* 메서드를 통해 데이터를 메모리에 저장하는 가짜 *MongoServer*를 생성합니다.
- *mongoServer*의 가짜 연결 정보를 통해 *SimpleDataBaseFactory*를 생성할 수 있습니다.

#### EnableMongoTestServer.java

```java
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@Import(MongoTestServerConfig.class)
public @interface EnableMongoTestServer {}
```

- 해당 어노테이션이 붙은 테스트 클래스에서 Embedded MongoDB 서버가 실행됩니다.
- MongoDB를 사용하는 통합 테스트 클래스에서만 사용할 수 있도록 커스텀 어노테이션을 구현했습니다.

#### AcceptanceTestWithMongo

```java
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@EnableMongoTestServer
public abstract class AcceptanceTestWithMongo {

    @Autowired
    MongoTemplate mongoTemplate;

    @BeforeEach
    public void setup() {
        mongoTemplate.getDb().drop();
    }
}
```

- MongoDB를 사용하는 통합 테스트는 앞으로 해당 클래스를 상속받아서 사용합니다.
- 매번 테스트마다 DB를 초기화하여 테스트 환경을 분리했습니다.

## 마치며

이번 마이그레이션을 통해 NoSQL과 MongoDB에 대한 이해를 한층 더 깊이 있게 다질 수 있었습니다. 다양한 NoSQL 데이터베이스 중에서 현재 서비스에 가장 적합한 데이터베이스를 선택하기 위해 여러 NoSQL DB를 비교 분석했고, 이를 통해 RDBMS와는 다른 MongoDB의 특성을 깊이 이해할 수 있었습니다. 특히, 스키마리스 구조, 수평 확장성, 고성능 조회 기능 등 MongoDB의 강점을 직접 체험하며, 이를 어떻게 서비스에 적용할지 고민하는 과정에서 얻은 점이 많았습니다.

이번 마이그레이션을 통해 NoSQL과 MongoDB에 대한 이해를 한층 더 높일 수 있었습니다. 다양하고 많은 NoSQL 데이터베이스 중에서 현재 서비스에 적합한 데이터베이스를 선택하는 과정에서 여러 가지 NoSQL DB를 비교해 보고 RDBMS와는 다른 MongoDB의 특성을 자세히 알 수 있었습니다.

데이터베이스 선택과 설계는 단순히 기술적인 요소만 고려하는 것이 아니라, 비즈니스 요구 사항과도 긴밀히 연결되어 있다는 점을 깨달았습니다. 예를 들어, 채팅 서비스는 데이터의 양이 기하급수적으로 증가할 수 있고, 조회 작업이 매우 빈번하게 발생합니다. 이러한 특성을 고려했을 때, MongoDB는 수평 확장성과 빠른 조회 성능을 제공하여 적합한 선택이었습니다.

이번 경험을 통해 추후 데이터베이스를 선택하고 설계하는 과정에 있어 비즈니스 요구사항을 깊게 고민해 보고, 새로운 기술을 도입할 때 발생할 수 있는 리스크와 비용을 충분히 고려해봐겠습니다..!

MongoDB로 마이그레이션을 한 후, *Jmeter*를 통한 성능 테스트 결과가 궁금하시면 [아래 글](/posts/spring-websocket-chat-4-performance/)을 확인해주세요 !

긴 글 읽어주셔서 감사합니다 :)

[🔗 [Spring Boot] WebSocket 을 사용하여 채팅 서비스 구현하기(4) - 채팅 서비스 성능 개선 및 부하 테스트](/posts/spring-websocket-chat-4-performance/)

#### 참고 자료

[🔗 Spring boot with MongoDB - Spring Data MongoDB를 사용해보자. 들어가기 Springboot로 채팅방을 구현하는 프로젝트를 진행하려고 한다. 채팅방은 실시간으로 채팅 내용을 저장할 수 있게 데이터베이스에 저장하도록 생각하였다. 하지만 채팅내용이 보내질 때 khdscor.tistory.com](https://khdscor.tistory.com/115)

[🔗 [Spring] Embedded MongoDB! 통합테스트를 위한 인메모리 몽고디비 설정하기 현재 mongodb와 mysql 을 함께 사용하고있는 프로젝트에서 통합테스트를 위해 mongodb 도 h2 같은 in-memory db로 사용할 수 있는게 없을까 찾아보다가 알게된 방법에 대해 정리하는 글 입니다. 공식적으 thalals.tistory.com](https://thalals.tistory.com/466)

[🔗 MongoDB-specific Query Methods :: Spring Data MongoDB By adding the org.springframework.data.mongodb.repository.Query annotation to your repository query methods, you can specify a MongoDB JSON query string to use instead of having the query be derived from the method name, as the following example shows: pub docs.spring.io](https://docs.spring.io/spring-data/mongodb/reference/mongodb/repositories/query-methods.html)
