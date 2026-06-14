---
title: WebSocket 을 사용하여 채팅 서비스 구현하기(3) - STOMP를 사용하여 실시간 채팅 구현 (비동기 처리)
date: 2025-01-21 22:03:30 +0900
categories: [Back-End, Spring]
tags: [STOMP, 웹소켓]
---

## 들어가며

야구 직관 서비스 캐치미 프로젝트에서 실시간 채팅 서비스를 구현한 내용을 기록 및 복습의 목적으로 본 글을 포스팅합니다. 이번 포스팅에서는 STOMP 프로토콜과 스프링 내장 메시지 브로커를 사용해서 실제 채팅 애플리케이션을 구현하는 과정을 다뤄보려고 합니다. 캐치미 서비스의 **채팅 도메인 규칙**과 **채팅 ERD 설계 과정**이 궁금하신 분은 [이전 글](/posts/spring-websocket-chat-2-data/)을 참고해주세요!

[🔗 [Spring boot] WebSocket 을 사용하여 채팅 서비스 구현하기(2) - 채팅 데이터베이스 설계하기](/posts/spring-websocket-chat-2-data/)

## WebSocket 설정

#### build.gradle

```groovy
// WebSocket
implementation 'org.springframework.boot:spring-boot-starter-websocket'
```

#### WebSocketConfig.java

```java
@Configuration
@EnableWebSocketMessageBroker  // WebSocket 메시지 브로커 활성화
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        // 구독 경로 설정 - 클라이언트가 구독할 수 있는 endpoint 설정
        // 클라이언트는 이 prefix로 시작하는 주제를 구독할 수 있음
        registry.enableSimpleBroker(
                "/sub/chat/goods"
        );

        // 발행 경로 설정 - 클라이언트가 메시지를 발행할 때 사용할 prefix
        // 클라이언트가 메시지를 보낼 때는 이 prefix로 시작하는 endpoint로 메시지를 전송
        registry.setApplicationDestinationPrefixes("/pub");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        // WebSocket 연결 endpoint 설정
        // 클라이언트는 이 경로로 WebSocket 연결을 맺음
        registry.addEndpoint("/ws/chat")
                // CORS 설정 - 허용할 origin 패턴 설정
                .setAllowedOriginPatterns("*")
                // SockJS 지원 추가 (WebSocket을 지원하지 않는 브라우저를 위한 fallback)
                .withSockJS();
    }
}
```

- **@EnableWebSocketMessageBroker** : *WebSocket* 메시지 브로커를 활성화하는 어노테이션입니다.
- **cofigureMessageBroker()**: 메시지 브로커 설정을 정의합니다.
  - **enableSimpleBroker("/sub/chat/goods")**: 스프링 내장 메시지 브로커를 활성화합니다. 클라이언트가 구독할 주제의 prefix를 설정하고, 클라이언트는 /sub/chat/goods로 시작하는 경로를 구독하여 메시지를 받을 수 있습니다.
  - **setApplicationDestinationPrefixes("/pub")**: 클라이언트가 메시지를 발행할 때 사용할 경로의 prefix를 설정합니다.
- **registerStompEndpoints()**: 웹소켓 연결 엔드포인트 정의합니다.
  - **addEndpoint("/ws/chat")**: WebSocket 연결의 엔드포인트를 설정합니다. 클라이언트는 /ws/chat 경로로 WebSocket 연결을 시도합니다.
  - **setAllowedOriginPatterns("*")**: CORS 설정으로, 모든 도메인에서의 요청을 허용합니다.
  - **withSockJS()**: *SockJS*를 활성화하여 *WebSocket*을 지원하지 않는 브라우저에서 HTTP 기반 폴백 옵션을 사용할 수 있도록 합니다.

## 채팅 엔티티

#### GoodsChatRoom.java (채팅방)

```java
@Entity
@Table(name = "goods_chat_room")
public class GoodsChatRoom {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "post_id", nullable = false)
    private GoodsPost goodsPost;

    @Column(name = "last_chat_content", columnDefinition = "TEXT")
    private String lastChatContent;

    @Column(name = "last_chat_sent_at")
    private LocalDateTime lastChatSentAt;

    @Column(name = "is_active", nullable = false)
    @Builder.Default
    private Boolean isActive = true;

    @OneToMany(mappedBy = "goodsChatRoom", cascade = CascadeType.ALL, orphanRemoval = true)
    @Builder.Default
    private List<GoodsChatPart> chatParts = new ArrayList<>();

    // 연관관계 생성 메서드
    public void addChatParticipant(Member member, Role role) {
        GoodsChatPart chatPart = GoodsChatPart.builder()
                .goodsChatRoom(this)
                .member(member)
                .role(role)
                .build();

        chatParts.add(chatPart);
    }

    // 최신 메시지 정보 업데이트
    public void updateLastChat(String lastChatContent, LocalDateTime lastChatSentAt) {
        this.lastChatContent = lastChatContent;
        this.lastChatSentAt = lastChatSentAt;
    }
    ...
}
```

- GoodsChatRoom 엔티티는 **판매글**(*GoodsPost*)에 대한 채팅방 정보를 관리합니다.
- 채팅참여(**GoodsChatPart**)와 일대다 관계를 맺음으로 하나의 채팅방에 다수의 인원이 참여할 수 있습니다. 또한 *CascadeType.ALL*과 *orphanRemoval = true* 설정을 통해 채팅참여의 생명주기를 함께 관리합니다.

#### GoodsChatPart.java (채팅 참여)

```java
@Data
public class GoodsChatPartId implements Serializable {
    private Long membeId;
    private Long goodsChatRoomId;
}

@Entity
@IdClass(GoodsChatPartId.class)	// 복합키 사용
@Table(name = "goods_chat_part")
@Getter
public class GoodsChatPart {

    @Id
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "member_id")
    private Member member;

    @Id
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "chat_room_id")
    private GoodsChatRoom goodsChatRoom;

    @Enumerated(EnumType.STRING)
    private Role role;

    @Column(name = "is_active")
    @Builder.Default
    private Boolean isActive = true;

    @OneToMany(mappedBy = "goodsChatPart", cascade = CascadeType.ALL, orphanRemoval = true)
    List<GoodsChatMessage> goodsChatMessages;

    // 채팅방 나가기 및 채팅방 삭제 여부 확인
    public boolean leaveAndCheckRoomStatus() {
        if (!goodsChatRoom.isRoomActive()) {
            return true;
        }
        goodsChatRoom.deactivateRoom();
        this.isActive = false;
        return false;
    }
}
```

- *GoodsChatPart* 엔티티는 특정 **채팅방**(*GoodsChatRoom*)에서 사용자의 참여 정보를 관리합니다
- *GoodsChatPartId* :*memberId*와 *goodsChatRoomId*를 사용하여 복합키를 정의하였고, *@IdClass* 어노테이션을 통해 복합키 클래스를 지정했습니다.
- 사용자의 역할(*role*) 필드를 정의하여, 사용자가 판매자 혹은 구매자인지 구별하였습니다.

#### GoodsChatMessage.java (채팅 메시지)

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
}
```

- **GoodsChatMessage 엔티티는 특정 채팅방에서 주고받은 메시지 정보를 관리합니다.**
- 채팅참여(*GoodsChatPart*)와 다대일 관계를 가지며, 복합 키(*member_id*, *chat_room_id*)를 외래 키로 참조합니다.
- *MessageType* 필드를 통해 메시지 유형을 구분합니다. 다양한 유형의 메시지를 저장할 수 있습니다.

## 비즈니스 로직 구현

#### GoodsChatMessageController.java

```java
@Controller
@RequiredArgsConstructor
public class GoodsChatMessageController {

    private final GoodsChatMessageService goodsChatMessageService;

    @MessageMapping("/chat/goods/message")
    public void handleMessage(@Validated @Payload GoodsChatMessageRequest message) {
        goodsChatMessageService.sendMessage(message);
    }
}
```

- **WebSocket**을 통해 채팅 메시지를 처리하는 컨트롤러입니다. 클라이언트로부터 메시지를 수신하고 검증을 마친 후, 서비스 계층으로 전달하여 비즈니스 로직을 처리합니다.
- **@MessageMapping** 어노테이션을 사용하여 특정 경로로 수신된 메시지를 매핑하고, **@Payload**를 통해 메시지 내용을 DTO로 변환하여 서비스 계층에 전달합니다.

#### GoodsChatMessageService

```java
@Service
@RequiredArgsConstructor
@Transactional
public class GoodsChatMessageService {

    ... (관련 의존성)
    private final SimpMessagingTemplate messagingTemplate;
    
    private static final String GOODS_CHAT_SUBSCRIBE_PATH = "/sub/chat/goods/";


    public void sendMessage(GoodsChatMessageRequest message) {
        Member sender = findMemberById(message.getSenderId());
        GoodsChatRoom chatRoom = findByChatRoomById(message.getRoomId());
        GoodsChatPart chatPart = findByChatPartById(sender.getId(), chatRoom.getId());

        // DB 메시지 저장
        GoodsChatMessage chatMessage
                = messageRepository.save(createChatMessage(message.getMessage(), chatPart, message.getType()));
        chatRoom.updateLastChat(chatMessage.getContent(), chatMessage.getSentAt());

	// 메시지 전송
        GoodsChatMessageResponse response = GoodsChatMessageResponse.of(chatMessage);
        sendToSubscribers(message.getRoomId(), response);
    }

    private GoodsChatMessage createChatMessage(String message, GoodsChatPart chatPart, MessageType type) {
        return GoodsChatMessage.builder()
                .goodsChatPart(chatPart)
                .content(message)
                .messageType(type)
                .build();
    }

    private void sendToSubscribers(Long chatRoomId, GoodsChatMessageResponse message) {
        messagingTemplate.convertAndSend(GOODS_CHAT_SUBSCRIBE_PATH + chatRoomId, message);
    }
    
    ...
}
```

- **SimpMessagingTemplate**: 스프링에서 제공하는 메시징 템플릿으로, 웹소켓 통신에서 메시지를 생성하고 전송하는 데 사용됩니다. convertAndSend(), convertAndSendToUser() 등 메시징 작업을 추상화하여 간결한 API를 제공하는 클래스입니다.
- **GOODS_CHAT_SUBSCRIBE_PATH**: 굿즈거래 채팅방의 TOPIC를 정의한 상수입니다. 사용자가 채팅방에 입장할 때, 클라이언트에서 해당 TOPIC 를 구독 처리합니다.
- **sendMessage**(): 메시지 DTO의 유효성을 검증한 후, 새로운 채팅 데이터를 저장하고 메시징 템플릿을 통해 구독 경로로 메시지를 브로드캐스트 합니다. 이를 통해 해당 TOPIC을 구독 중인 모든 클라이언트에게 실시간으로 메시지를 주고받을 수 있습니다.

### 비동기 이벤트 처리 (입장, 퇴장, 거래완료 메시지)

#### GoodsChatEvent.java

```java
public record GoodsChatEvent(Long chatRoomId, Member member, MessageType type) {

    public static GoodsChatEvent from(Long chatRoomId, Member member, MessageType type) {
        return new GoodsChatEvent(chatRoomId, member, type);
    }
}
```

- GoodsChatEvent 클래스는 이벤트 처리에 필요한 정보를 담는 record 클래스입니다.
- 채팅방 id, 회원 객체, 메시지 유형을 저장합니다.

#### GoodsChatEventPublisher

```java
@Component
@RequiredArgsConstructor
public class GoodsChatEventPublisher {

    private final ApplicationEventPublisher applicationEventPublisher;

    public void publish(GoodsChatEvent goodsChatEvent) {
        applicationEventPublisher.publishEvent(goodsChatEvent);
    }
}
```

- *GoodsChatEventPublisher* 클래스는 *ApplicationEventPublisher* 클래스를 주입받아 채팅 관련 이벤트를 발행합니다.

> [!note] ApplicationEventPublisher를 직접 사용하지 않은 이유
> 추후 이벤트 발행 로직에 변화가 생겼을 때, 코드 변경을 최소화할 수 있도록 ApplicationEventPublisher를 직접 사용하지 않고 GoodsChatEventPublisher 커스텀 클래스를 구현했습니다. 이를 통해 다른 코드에 미치는 영향을 최소화할 수 있습니다.

#### GoodsChatService.java

```java
@Service
@Transactional
@RequiredArgsConstructor
public class GoodsChatService {

    ...(관련 의존성)
    private final GoodsChatEventPublisher eventPublisher;

    // 채팅방 입장 메서드 - 새로운 채팅방 생성
    private GoodsChatRoomResponse createChatRoom(GoodsPost goodsPost, Member buyer, Member seller) {
        ... (채팅방 생성, 연관관계 설정)

        // 입장 메시지 전송
        eventPublisher.publish(GoodsChatEvent.from(goodsChatRoom.getId(), buyer, MessageType.ENTER));

        return GoodsChatRoomResponse.of(savedChatRoom, null);
    }

    // 채팅방 퇴장 메서드
    public void deactivateGoodsChatPart(Long memberId, Long chatRoomId) {
        ... (검증 메서드)

        if (!goodsChatPart.leaveAndCheckRoomStatus()) {
            // 퇴장 메시지 전송
            eventPublisher.publish(GoodsChatEvent.from(chatRoomId, member, MessageType.LEAVE));
        } else {
           ... (채팅방, 채팅 참여, 채팅 삭제)
        }
    }

    ...
}
```

- 실제 서비스 코드에서 *GoodsChatEventPublisher* 사용 예시입니다.
- 채팅방 입장, 채팅방 나가기 기능을 처리한 후 해당 이벤트에 맞는 *MessageType*을 지정하여 이벤트를 발행합니다.

#### GoodsChatEventHandler.java

```java
@Component
@RequiredArgsConstructor
public class GoodsChatEventHandler {

    private final GoodsChatMessageService messageService;

    @Async
    @TransactionalEventListener
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void handle(GoodsChatEvent event) {
        messageService.sendChatEventMessage(event);
    }
}
```

- *GoodsChatEvent*가 발행된 후, 해당 이벤트를 처리하는 클래스입니다.
- **@Async**
  - 해당 어노테이션은 메서드를 비동기적으로 실행되도록 합니다.
  - 실제 메시지 전송 로직은 별도의 스레드에서 진행되기 때문에 응답 속도가 저하되는 것을 방지할 수 있습니다.
  - **@Async** 어노테이션을 사용할 경우, **@EnableAsync** 어노테이션을 함께 선언해 주어야 합니다.
- **@TransactionalEventListener**
  - 해당 어노테이션은 이벤트가 발행될 때 트랜잭션의 상태를 고려하여 이벤트를 처리합니다.
  - Default 옵션은 *TranactionPhase.AFTER_COMMIT*으로, 트랜잭션이 커밋되었을 때 메서드가 동작합니다.
  - 이를 통해 비동기적으로 이벤트를 처리하면서 데이터의 일관성을 유지할 수 있습니다.
- **@Transactional(propagation = Propagation.REQUIRES_NEW)**
  - 이벤트 채팅 전송 로직과 메인 로직의 트랜잭션을 분리합니다.
  - 이를 통해 이벤트 메시지 전송이 실패하더라도, 메인 로직에 영향을 주지 않음으로 안정성을 유지할 수 있습니다.

### **@Async** 사용 시 주의사항

1. **@TransactionalEventListener**와 **@Async**가 함께 사용된 경우

- 이벤트 처리 로직에서 발생한 트랜잭션 롤백이 이벤트를 호출한 메서드의 트랜잭션에 영향을 미치지 않습니다.
- 예를 들어, 입장 메시지 저장이 실패한 경우 채팅방 입장은 정상적으로 수행됩니다.
- 채팅방 입장 메시지가 전송된 시간(*sent_at*)을 통해 채팅 내역을 조회하는 단체 채팅방의 경우에는 입장 메시지가 누락될 가능성이 있기 때문에, 동기적으로 이벤트 처리 로직을 수행해야 합니다.

2. @Async 어노테이션은 기본적으로 **Spring AOP 프록시 방식으로 동작**합니다. 따라서 제약사항이 존재합니다.

- 같은 클래스의 메서드를 호출하는 경우(*self-invocation*) 사용이 불가능합니다.
- *public* 메서드에서만 사용이 가능합니다.

3. 기본적으로 Spring 환경에서 *Executor*를 Bean에 등록하지 않으면 ***SimpleAsyncTaskExecutor***을 사용해서 쓰레드를 알아서 관리합니다.

- ***SimpleAsyncTaskExecutor***는 매 실행마다 새로운 쓰레드를 생성하여 작업을 실행함으로, 쓰레드를 재사용하지 않기 때문에 성능상 이슈가 존재할 수 있습니다.
- Spring Boot를 사용하는 경우에는, *autoConfiguration*으로 ***ThreadPoolTaskExecutor***가 자동으로 등록되어 쓰레드를 관리하게 되고, *application.yml* 에서 옵션을 지정할 수 있습니다.
- 따라서 아래 AsyncConfig 설정 클래스에서 직접  ***ThreadPoolTaskExecutor***를 직접 설정하는 것이 안전합니다.

#### **AsyncConfig.java**

```java
@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean
    public ThreadPoolTaskExecutor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);                            // 기본 스레드 풀 크기
        executor.setMaxPoolSize(10);                            // 최대 스레드 풀 크기
        executor.setQueueCapacity(100);                         // 대기 큐의 크기
        executor.setThreadNamePrefix("Event Executor-");        // 스레드 이름

        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.setAllowCoreThreadTimeOut(true);               // 유휴 스레드 제거 활성화
        executor.setKeepAliveSeconds(60);                       // 유휴 스레드 유지 시간

        executor.setWaitForTasksToCompleteOnShutdown(true);     // shutdown 시 남은 queue 작업 처리
        executor.setAwaitTerminationSeconds(60);	            // 최대 60초 대기

        executor.initialize();
        return executor;
    }
}
```

- corePoolSize(5)
  - 기본 스레드 풀의 스레드 개수를 지정합니다.
- maxPoolSize(10)
  - 최대 생성 가능한 스레드 개수를 지정합니다.
  - corePoolSize(5)를 넘는 요청이 들어올 때 스레드 개수를 최대 10개까지 확장합니다.
  - 하지만 QueueCapacity가 가득 차야만 CorePoolSize를 초과하여 추가 스레드가 생성됩니다.
- queueCapacity(100)
  - 작업을 대기하는 큐의 크기를 설정합니다.
  - 스레드 풀이 가득 차면, 추가 요청은 큐에 저장되며, 대기 중인 작업이 완료되면 실행됩니다.
- setAllowCoreThreadTimeOut(true), setKeepAliveSeconds(60)
  - corePoolSize 이하의 스레드도 사용하지 않는 상태일 경우 종료할 수 있도록 허용합니다.
  - 60초 동안 추가 요청이 없으면 종료되도록 설정합니다.
- setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy())
  - 스레드와 큐가 모두 가득 찬 경우, 예외 처리 정책을 지정합니다.
  - CallerRunsPolicy를 사용한다면, 현재 실행중인 **메인 스레드에 해당 작업을 직접 실행**합니다.
  - 요청이 거부되지 않고, 이벤트를 확실하게 처리할 수 있지만, 메인 스레드의 응답 시간이 저하될 수 있습니다.
    - 기본값은 AbortPolicy로, 스레드와 큐가 가득 찰 경우 예외를 발생시킵니다.
    - DiscardPolicy 정책은, 새로운 작업을 그냥 버리고 예외도 발생시키지 않습니다.
    - DiscardOldestPolicy 정책은, 큐에 대기 중인 가장 오래된 작업을 제거한 후, 새로운 작업을 추가합니다.
    - 이외에도 RejectedExecutionHandler 인터페이스를 구현하여 커스텀 예외 정책을 생성할 수 있습니다.
- setWaitForTasksToCompleteOnShutdown(true), setWaitForTasksToCompleteOnShutdown(true)
  - 애플리케이션 종료 시, 대기 중인 작업을 모두 완료한 후 종료하도록 설정합니다.
  - 최대 60초 동안 대기 후, 남아있는 작업이 있더라도 강제 종료합니다.

> [!note]
> 해당 설정은 소규모 EC2(t3a.small) 환경에서 효율적으로 비동기 작업을 처리하기 위해 적용되었습니다.
> 기본 5개 스레드로 운영하다가 부하가 증가하면 최대 10개까지 확장하며, 100개의 대기 큐로 요청을 수용합니다.
> 사용량이 적을 때는 유휴 스레드를 제거하여 리소스를 절약하고, 서버 종료 시에도 작업을 안정적으로 마무리하도록 구성했습니다.

#### GoodsChatMessageService.java - 이벤트 처리 추가

```java
// 이벤트 메시지 전송
public void sendChatEventMessage(GoodsChatEvent event) {
    Member member = event.member();
    Long chatRoomId = event.chatRoomId();
    GoodsChatRoom chatRoom = findByChatRoomById(chatRoomId);

    // 메시지 생성
    String message = member.getNickname();
    switch (event.type()) {
        case ENTER -> message += MEMBER_ENTER_MESSAGE;
        case LEAVE -> message += MEMBER_LEAVE_MESSAGE;
        case GOODS -> message += MEMBER_TRANSACTION_MESSAGE;
    }
    GoodsChatMessage chatMessage = createChatMessage(chatRoomId, member.getId(), message, event.type());

    // 채팅 데이터 저장 & 최신 채팅 내역 업데이트
    GoodsChatMessage savedMessage = messageRepository.save(chatMessage);
    chatRoom.updateLastChat(message, chatMessage.getSentAt());

    // 이벤트 메시지 전송
    sendToSubscribers(chatRoomId, GoodsChatMessageResponse.of(savedMessage, member));
}

private void sendToSubscribers(Long chatRoomId, GoodsChatMessageResponse message) {
    messagingTemplate.convertAndSend(GOODS_CHAT_SUBSCRIBE_PATH + chatRoomId, message);
}
```

- 이벤트 처리 로직에서는 해당 이벤트의 *MessageType*을 통해 해당 이벤트 메시지를 생성합니다.
  - ex) *"?? 님이 대화를 시작했습니다.", "?? 님이 거래를 완료했습니다. 상품에 대한 거래후기를 남겨주세요!"*
- 이후 생성된 이벤트 메시지를 DB에 저장하고, *SimpleMessageTemplate*을 통해 웹소켓 구독 경로로 *broadcast* 하게 됩니다.

## 실제 동작 GIF

![실제 구현 화면](/assets/img/spring-websocket-chat-3-stomp/01.gif)

## 마치며

이번 포스팅을 통해 스프링 내장 메시지 브로커를 활용한 실시간 채팅 서비스 구현의 전반적인 과정을 살펴보았습니다. WebSocket과 STOMP 프로토콜을 활용한 실시간 채팅 시스템의 구조와 작동 방식을 이해할 수 있었고, 비동기 이벤트 처리를 효율적으로 구현하기 위해 더욱 고민할 필요성을 느꼈습니다.

그러나 이번 포스팅에서 작성된 코드에는 몇 가지 성능적인 문제점이 존재합니다.

**첫째, 예시로 사용한 스프링 내장 메시지 브로커는 설정이 간편하다는 장점이 있지만, 성능과 확장성 측면에서 명확한 한계가 있습니다.**

스프링 내장 브로커는 단일 JVM 내에서만 작동하므로 여러 서버 인스턴스 간의 메시지 공유가 불가능합니다. 이로 인해, 대규모 사용자 환경에서는 메시지 전송의 일관성이 보장되지 않으며, 이로 인해 메시지 손실이나 중복 전송과 같은 문제가 발생할 수 있습니다. 따라서 대규모 사용자 환경에서는 **Kafka, RabbitMQ와 같은 외부 메시지 브로커**를 도입해야 할 필요성이 큽니다. 이러한 외부 브로커는 분산 시스템에서의 메시지 전송을 효율적으로 처리할 수 있는 기능을 제공하므로, 성능과 안정성을 높일 수 있습니다.

**둘째, 현재 구현된 서비스는 사용자 수가 증가함에 따라 성능 저하가 발생할 우려가 큽니다.**

채팅 데이터베이스가 RDBMS로 구성되어 있기 때문에 메시지 전송 간의 지연 시간이 증가할 가능성이 있습니다. 이는 사용자 경험에 부정적인 영향을 미칠 수 있으며, 특히 실시간성이 중요한 채팅 서비스에서는 더욱 중요한 문제입니다. 또한, 채팅 서비스의 특성상 데이터베이스 조회가 빈번하게 발생하기 때문에 I/O 비용이 상당히 클 것으로 예상되어 DB 서버에 과부하가 걸릴 수 있으며, 이는 전체 시스템의 응답 속도를 저하시킬 수 있습니다.

이러한 문제점을 해결하기 위해, 다음 포스팅에서는 채팅 데이터베이스를 MongoDB로 마이그레이션 하는 과정과 함께, 채팅 조회를 No-Offset 방식으로 변경하고 Redis 캐싱을 도입하여 전체 채팅 서비스의 성능을 향상시키는 방안을 다뤄보겠습니다!

긴 글 읽어주셔서 감사합니다 :)

[🔗 [Spring Boot] WebSocket 을 사용하여 채팅 서비스 구현하기(4) - 채팅 서비스 성능 개선 및 부하 테스트](/posts/spring-websocket-chat-4-performance/)
