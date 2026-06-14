---
title: MongoDB와  MySQL의 이기종 트랜잭션 문제 해결
date: 2025-02-25 22:53:07 +0900
categories: [Back-End, Spring]
tags: [MongoDB, Spring Boot, 트랜잭션]
---

## 문제 상황

채팅 데이터베이스를 MySQL에서 MongoDB로 이전하며 트랜잭션이 적용되지 않는 문제가 발생했습니다.

Spring은 *@Transactional* 어노테이션을 통해 AOP를 사용하여 트랜잭션을 제어하며, 트랜잭션은 *TransactionManager*을 통해 관리됩니다.

Spring Boot는 등록된 라이브러리를 통해 자동으로 스프링 컨테이너에 트랜잭션에 등록됩니다.

![](/assets/img/spring-mongodb-mysql-heterogeneous-transaction/01.png)

그러나 MongoDB 트랜잭션은 선택 사항이기 때문에, Spring Boot는 자동으로 트랜잭션 매니저를 등록하지 않습니다. 따라서 MongoDB 트랜잭션을 사용하기 위해서는 별도로 트랜잭션 매니저를 빈으로 등록해야 합니다.

```java
@Configuration
public class MongoConfig {

    @Bean(name = "mongoTransactionManager")
    public MongoTransactionManager transactionManager(MongoDatabaseFactory mongoDatabaseFactory) {
        return new MongoTransactionManager(mongoDatabaseFactory);
    }
}
```

위 설정을 추가하면 MongoDB에서 트랜잭션을 사용할 수 있습니다.

### Replica Set

또한 Spring Boot에서 MongoDB 트랜잭션을 사용하려면 **Replica Set 환경을 구축**해야 합니다.

MongoDB에서 Replica Set은 여러 인스턴스를 복제하여 데이터의 가용성과 안정성을 높이기 위해 사용됩니다.

공식 답변에 따르면, MongoDB 트랜잭션은 내부적으로 논리적 세션(Logical Session)을 기반으로 동작하며, 이 과정에서 Oplog(Operations Log)를 활용합니다.

이때, Oplog는 Replica Set 환경에서만 동작하기 때문에 싱글 노드 환경에서는 트랜잭션을 지원하지 않는다고 합니다.

[🔗 Why replica set is mandatory for transactions in MongoDB? (MongoDB Community Forums)](https://www.mongodb.com/community/forums/t/why-replica-set-is-mandatory-for-transactions-in-mongodb/9533)

저희 팀은 MongoDB Atlas 를 사용하고 있었기 때문에, 기본으로 제공되는 replicaSet를 사용할 수 있었습니다.

배포 서버에서 MongoDB를 직접 설치하여 사용하시는 분들은 **"MongoDB Replica Set"** 이라는 키워드로 검색하시면 구축 과정을 담은 양질의 블로그가 많으니 참고하여 구축하시면 될 것 같습니다.

이렇게 해서 MongoDB를 다루는 비즈니스 로직에 트랜잭션을 무사히 적용할 수 있었습니다.

### JPA와 MongoDB 트랜잭션 통합 문제

MongoDB 트랜잭션을 활성화했음에도 불구하고, JPA(MySQL)와 MongoDB 트랜잭션을 함께 사용하는 코드에서 트랜잭션이 정상 작동하지 않았습니다.

**GoodsChatMessageService.java**

```java
@Transactional
public void sendMessage(GoodsChatMessageRequest message) {
    Member member = findMemberById(message.getSenderId());
    GoodsChatRoom chatRoom = findByChatRoomById(message.getRoomId());
    GoodsChatMessage chatMessage = createChatMessage(chatRoom.getId(), member.getId(), message.getMessage(), message.getType());

    // 채팅 데이터 저장 & 최신 채팅 내역 업데이트
    GoodsChatMessage savedMessage = messageRepository.save(chatMessage);
    chatRoom.updateLastChat(chatMessage.getContent(), chatMessage.getSentAt());

    // redis 캐시 저장
    goodsChatCacheManager.storeMessageInCache(message.getRoomId(), savedMessage);

    GoodsChatMessageResponse response = GoodsChatMessageResponse.of(savedMessage, member);
    sendToSubscribers(message.getRoomId(), response);
}
```

위 로직은 클라이언트에서 보낸 채팅 메시지를 1. MongoDB에 저장하고, 2. 최신 채팅 정보를 MySQL에 업데이트한 후, 3. 해당 채팅방의 Subscriber들에게 메시지를 전송합니다.

해당 로직에서 MongoDB에 데이터가 저장된 후, 예외가 발생하면 MySQL에 업데이트된 데이터는 롤백되었지만, MongoDB의 데이터는 그대로 유지되었습니다.

위 문제가 발생한 이유는, JPA와 MongoDB의 트랜잭션을 통합적으로 관리할 수 없기 때문이였습니다.

Spring은 기본적으로 단일 트랜잭션 매니저만 지원하며, 여러 데이터 소스 간의 분산 트랜잭션을 지원하지 않습니다.

따라서 해당 로직에는 JPA 트랜잭션만 적용되고, MongoDB의 트랜잭션은 적용이 되지 않았습니다.

---

## 해결 방법

### 1. ChainedTransactionManager

*ChainedTransactionManager*는 *Spring Data Commons*에서 공식으로 지원하는 기술로, 말 그대로 여러 개의 트랜잭션을 묶어서 사용할 수 있는 *TransactionManager*입니다.

여러 개의 DataSource를 다룰 때 여러 개의 *TransactionManager*를 활용하여 트랜잭션을 시작하고 끝내는 작업을 하나의 *TransactionManager*를 사용해 트랜잭션을 손쉽게 다룰 수 있습니다.

하지만, 과거에는 *ChainedTransactionManager*를 사용하여 서로 다른 데이터 소스의 트랜잭션을 통합하여 사용할 수 있었지만 현재는 deprecated 돼서 사용하기 어려운 상황입니다.

또한 *ChainedTransactionManager*는 정상적인 롤백을 보장하지 못한다는 큰 단점을 가지고 있습니다.

### 2. JTA(Java Transaction API)

다른 해결 방법으로는 *JTA(Java Transaction API)*를 사용하여 분산 트랜잭션을 구현하는 것입니다.

*JtaTransactionManager*는 *ChainedTransactionManager*가 *deprecated* 된 이후로 대안으로 사용되고 있습니다.

JTA(Java Transaction API)는 분산 트랜잭션을 지원하는 Java 표준 API 로, 여러 데이터 소스(예: MySQL, MongoDB, 메시지 큐 등) 간의 트랜잭션을 통합적으로 관리할 수 있습니다.

JTA를 사용하려면 Transaction Manager와 Resource Manager를 설정하고, JTA 구현체, XA 데이터 소스 등 복잡한 설정이 필요하고, 러닝 커브가 높다는 단점이 있었습니다.

또한 해당 프로젝트에서 분산 트랜잭션이 필요한 로직은 하나뿐이었습니다. JTA는 대규모 분산 시스템에서 여러 데이터 소스 간의 트랜잭션을 관리하는 데 적합하지만, 이처럼 작은 기능 하나를 위해 JTA를 도입하는 것은 오버 엔지니어링이라고 판단하였습니다.

### 3. TransactionTemplate (채택)

마지막으로 *TransactionTemplate*을 사용해서 직접 트랜잭션을 제어하는 방법이 있습니다.

*Spring*은 *TransactionTemplate* 클래스를 통해 프로그래밍적 트랜잭션 관리를 지원합니다.

일반적으로 트랜잭션 관리는 관심사의 분리를 위해 선언적 트랜잭션(@Transactional)을 사용하지만, 선언적 트랜잭션은 메서드나 클래스 단위로만 적용할 수 있는 반면, *TransactionTemplate*은 동적으로 트랜잭션 경계를 설정할 수 있어, 복잡한 트랜잭션 로직을 유연하게 처리할 수 있습니다.

*TransactionTemplate*은 템플릿 콜백 패턴을 사용하여 트랜잭션을 관리합니다. 이는 트랜잭션의 시작, 커밋, 롤백을 개발자가 직접 제어할 수 있도록 해줍니다.

특히, *execute()* 메서드를 통해 트랜잭션 로직을 실행하며, 예외 발생 시 자동으로 롤백을 수행합니다.

```java
@Nullable
public <T> T execute(TransactionCallback<T> action) throws TransactionException {
    Assert.state(this.transactionManager != null, "No PlatformTransactionManager set");
    PlatformTransactionManager var3 = this.transactionManager;
    if (var3 instanceof CallbackPreferringPlatformTransactionManager cpptm) {
        return cpptm.execute(this, action);
    } else {
        TransactionStatus status = this.transactionManager.getTransaction(this);

        Object result;
        try {
            result = action.doInTransaction(status);
        } catch (Error | RuntimeException var6) {
            Throwable ex = var6;
            this.rollbackOnException(status, ex);
            throw ex;
        } catch (Throwable var7) {
            Throwable ex = var7;
            this.rollbackOnException(status, ex);
            throw new UndeclaredThrowableException(ex, "TransactionCallback threw undeclared checked exception");
        }

        this.transactionManager.commit(status);
        return result;
    }
}
```

실제 코드를 보면, *TransactionCallBack*을 매개변수로 받아서, 트랜잭션 처리 작업을 진행합니다.

1. *TransactionManager*를 통해 *getTransaction()*을 호출하여 트랜잭션을 시작합니다.

2. *doInTransaction()* 메서드 내에서 비즈니스 로직을 실행합니다.

3. 로직에서 예외 또는 에러가 발생했을 때, *rollbackOnException()* 메서드를 호출하여 트랜잭션을 롤백합니다.

4. 비즈니스 로직이 정상적으로 종료되면 *commit()*을 호출하여 트랜잭션을 커밋합니다.

이러한 구조를 통해 개발자는 트랜잭션의 시작과 종료를 명시적으로 제어할 수 있으며, 예외 발생 시 자동으로 롤백이 수행됩니다.

#### MongoCofig.java

```java
@Configuration
public class MongoConfig {

    @Bean(name = "mongoTransactionTemplate")
    public TransactionTemplate transactionTemplate(MongoTransactionManager mongoTransactionManager) {
        return new TransactionTemplate(mongoTransactionManager);
    }
}
```

이전에 *MongoCofig* 클래스에서, *TransactionTemplate*을 빈으로 등록합니다.

*MongoTransactionManager*를 기반으로 *TransactionTemplate*을 생성합니다.

#### GoodsChatMessageService.java

다음으로, 채팅 메시지를 저장하는 비즈니스 로직에 *TransactionTemplate*을 적용합니다. 이때, JPA 트랜잭션과 MongoDB 트랜잭션을 분리하여 관리합니다.

```java
private final TransactionTemplate mongoTransactionTemplate;

@Transactional // JPA 트랜잭션
public void sendMessage(GoodsChatMessageRequest message) {
    // 1. 회원 및 채팅방 조회
    Member member = findMemberById(message.getSenderId());
    GoodsChatRoom chatRoom = findByChatRoomById(message.getRoomId());

    // 2. 채팅 메시지 생성
    GoodsChatMessage chatMessage = createChatMessage(chatRoom.getId(), member.getId(), message, type);

    // 3. 최신 채팅 내역 업데이트 (MySQL)
    chatRoom.updateLastChat(message, chatMessage.getSentAt());

    // 4. MongoDB 트랜잭션 시작
    mongoTransactionTemplate.execute(status -> {
        // 4.1. 채팅 메시지 저장 (MongoDB)
        GoodsChatMessage savedMessage = messageRepository.save(chatMessage);

        // 4.2. Redis 캐시 저장
        goodsChatCacheManager.storeMessageInCache(message.getRoomId(), savedMessage);

        // 4.3. 구독자에게 메시지 전송
        sendToSubscribers(savedMessage.getChatRoomId(), GoodsChatMessageResponse.of(savedMessage, member));

        return null;
    });
}
```

**트랜잭션 동작 흐름**

1. *@Transactional* 어노테이션으로 JPA 트랜잭션이 시작됩니다.
2. 채팅방의 최신 채팅 내역을 업데이트합니다.
3. *TransactionTemplate.execute()*를 통해 MongoDB 트랜잭션이 시작됩니다.
   - 채팅 메시지를 MongoDB에 저장합니다.
   - Redis 캐시에 메시지를 저장합니다.
   - Subscriber에게 메시지를 전송합니다.
4. 예외 발생 시 롤백
   - MongoDB 트랜잭션에서 예외가 발생하면, 해당 트랜잭션은 롤백됩니다.
   - 예외가 JPA 트랜잭션으로 전파되면, MySQL 트랜잭션도 롤백됩니다.
5. 정상 종료 시 커밋:
   - 모든 작업이 정상적으로 완료되면, MongoDB와 JPA 트랜잭션이 커밋됩니다.

이를 통해 JPA와 MongoDB의 트랜잭션을 분리하여 안정적으로 관리할 수 있었습니다.

기존에는 JPA와 MongoDB를 함께 사용하는 경우 트랜잭션을 일관되게 관리하는 것이 어려웠지만, *TransactionTemplate*을 활용함으로써 각 데이터베이스의 트랜잭션을 명확하게 분리하고 제어할 수 있었습니다.

또한, Redis 캐싱 및 실시간 메시지 전송과 같이 트랜잭션과 관련 없는 작업을 트랜잭션 흐름 안에서 유연하게 처리할 수 있었으며, 예외 발생 시 적절한 롤백이 수행됨으로써 데이터 정합성을 유지할 수 있었습니다.

이러한 방식은 JTA와 같은 분산 트랜잭션을 도입하지 않으면서도 다양한 데이터 소스를 효과적으로 관리할 수 있도록 해주었으며, 복잡한 설정 없이 트랜잭션을 명확하게 제어할 수 있다는 점에서 실용적인 해결책이었습니다.
