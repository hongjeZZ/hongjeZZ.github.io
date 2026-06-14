---
title: "WebSocket 을 사용하여 채팅 서비스 구현하기(1) - 웹소켓(WebSocket), STOMP 이해하기"
date: 2025-01-13 18:35:13 +0900
categories: [Back-End, Spring]
tags: [STOMP, 네트워크, 웹소켓]
---

## 들어가며

야구 직관 서비스 캐치미 프로젝트에서 실시간 채팅 서비스를 구현한 내용을 기록 및 복습의 목적으로 본 글을 포스팅합니다. 이번 포스팅에서는 **소켓**과 **웹소켓**, **STOMP 프로토콜**에 대한 개념, **HTTP 통신과의 차이점**을 알아보려고 합니다. 채팅에 관련된 채팅방, 채팅 데이터 테이블의 **ERD 설계**부터 **실제 코드 구현**, MongoDB로 마이그레이션을 통한 **성능 개선**까지 실제 프로젝트를 참여하며 겪었던 고민들에 대해 이야기해 보겠습니다.

> 이미 웹소켓에 대한 기본 개념이 있으시다면 다음 글로 넘어가셔도 좋습니다.

## 웹소켓(WebSocket) 이란 ❓

서버와 클라이언트 간의 메시지를 교환하기 위한 통신 방법입니다.

일반적으로 서버와 클라이언트는 HTTP 통신을 통해 메시지를 주고받지만, 아래와 같은 웹소켓의 특징 때문에 현재 인터넷 환경(HTML5)에서 채팅, 주식, 비디오 데이터 등을 전송할 때 주로 사용됩니다.

### 웹소켓의 특징

#### 1. 양방향 통신 (Full-Duplex)

- 데이터 송수신을 동시에 처리할 수 있는 통신 방법
- 클라이언트와 서버가 서로에게 원할 때 데이터를 주고받을 수 있다.
- 통상적인 HTTP 통신은 클라이언트가 요청을 보내는 경우에만 서버가 응답하는 단방향 통신

#### 2. 실시간 네트워킹 (Real Time-Networing)

- 웹 환경에서 연속된 데이터를 빠르게 노출시킬 수 있다.
- 여러 단말기에서 빠르게 정보를 교환할 수 있다.

위 두 가지 특징을 가진 웹소켓과 달리, HTTP 통신은 클라이언트에서 서버에 요청을 보내야만 서버에서 응답을 할 수 있는 단방향 통신입니다.

또한 웹소켓 이전에는 HTTP를 이용한 **Polling**, **LongPolling**, **Streaming**과 같은 실시간 통신을 구현한 기술이 있었습니다. 이러한 기술에는 불필요한 request와 connection을 생성하고, 클라이언트에서 서버로의 데이터 송신이 어렵다는 단점이 있습니다. 무엇보다 HTTP 통신의 가장 큰 한계점은 HTTP를 통해 통신하기 때문에 **Request와 Response의 헤더가 불필요하게 크다**는 것입니다.

웹소켓 프로토콜 또한 커넥션을 맺을 때는 HTTP를 사용하지만, 그 이후 통신은 웹소켓의 독자적인 프로토콜로 이루어지며 헤더가 HTTP 통신에 비해 상대적으로 작습니다.

이러한 이유로 정식으로 클라이언트와 서버 간의 실시간 양방향 통신이 가능하게 하기 위해 HTML5 표준으로 웹소켓이 만들어졌습니다.

> [!tip] 참고
> Polling, Long Polling, Streaming에 관한 자세한 내용이 궁금하시다면 아래 링크를 참고해 주세요!

[🔗 Polling / Long Polling / Streaming](https://velog.io/@hahan/Polling-Long-Polling-Streaming)

### 웹소켓 동작원리

![출처 - ITNext](/assets/img/spring-websocket-chat-1-websocket/01.png)

빨간색으로 표시된 부분이 웹소켓을 연결하기 위해 클라이언트는 웹소켓 핸드셰이크 요청을 보내는 과정입니다. 클라이인트가 HTTP Upgrade, 즉 웹소켓 연결 요청을 보내면 응답으로 101 코드를 받습니다. 101 코드는 프로토콜 전환을 승인한다는 의미입니다. 요청과 응답의 자세한 헤더 내용은 아래와 같습니다.

#### 핸드셰이크 요청

```http
GET /chat HTTP/1.1
Host: server.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==
Sec-WebSocket-Protocol: chat, superchat
Sec-WebSocket-Version: 13
Origin: http://example.com
```

- GET /chat HTTP/1.1: 웹소켓 연결 시 HTTP 버전은 1.1 이상을 사용해야 하고 반드시 GET 메서드를 사용해야 합니다.
- Host: 웹소켓 서버의 주소입니다.
- Upgrade: 프로토콜 전환을 위해 사용하는 헤더입니다. 웹소켓 요청 시 websocket 이라는 값을 가지고, 이 값이 누락되거나 다른 경우 연결할 수 없습니다.
- Connection: 현재 전송이 완료된 후 네트워크 접속을 유지할 것인지에 대한 정보입니다. 웹소켓 요청 시 Upgrade 라는 값을 가지고, 이 값이 누락되거나 다른 경우 연결할 수 없습니다.
- Sec-WebSocket-Key : 유효한 요청인지 확인하기 위해 사용하는 키 값입니다.
- Sec-WebSocket-Protocol : 사용하고자 하는 하나 이상의 웹 소켓 프로토콜 지정. 필요한 경우에만 사용합니다.

#### 연결 성공 응답

```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: HSmrc0sMlYUkAGmm5OPpG2HaGWk=
Sec-WebSocket-Protocol: chat
```

- 101 Switching Protocols: 프로토콜 전환을 승인한다는 의미입니다. (웹소켓이 연결됨)
- Sec-WebSocket-Accept: 클라이언트로 받은 Sec-WebSocket-Key를 사용하여 계산된 값으로, 클라이언트에서 계산한 값과 일치하지 않으면 연결이 되지 않습니다.

웹소켓 연결 이후로는 프로토콜이 **WS** 혹은 **WSS**로 변경됩니다. 이때, 여러 frame이 모여서 구성되는 **Message**라는 단위로 데이터를 전송합니다. 이 Message 에는 텍스트(UTF-8) 데이터와 바이너리 데이터, 컨트롤 프레임(프로토콜 레벨의 신호)등을 담을 수 있습니다.

**frame**은 communication에서 가장 작은 단위의 데이터로 작은 헤더와 payload 로 구성됩니다. 앞서 설명했던 HTTP와 헤더 크기의 차이점을 이 부분에서 알 수 있습니다.

### 웹소켓과 HTTP 통신의 차이점

|  |  |  |
| --- | --- | --- |
|  | 웹소켓 | HTTP |
| 통신 방식 | - **양방햔 통신**을 지원하여 서버와 클라이언트가 서로 원할 때 데이터를 주고 받을 수 있음 - 연결 이후에는 독립적인 웹소켓 프로토콜을 사용하여 통신이 이루어짐 | - **단방향 통신** 방식으로, 클라이언트가 요청을 보내야 서버가 응답할 수 있음 |
| 연결 지속성 | - 연결이 한 번 맺어진 이후에는 **지속적인 연결 상태**를 유지 - 연결을 유지하면서 데이터를 주고받기 때문에 반복적인 연결 설정 과정이 필요하지 않음 | - 요청-응답마다 새로운 연결을 설정하며, 연결이 종료됩니다. - 지속적인 데이터 전송이 필요한 경우, 연결을 반복적으로 설정해야 함 |
| 오버헤드 | - 초기 연결(handshake)은 HTTP 프로토콜을 사용하지만, 연결 후에는 웹소켓 프로토콜을 사용하여 헤더 크기가 상당히 작아지고 데이터 전송이 효율적임 | - 요청과 응답에 포함된 헤더가 비교적 크며, 매번 새 연결마다 헤더가 포함됨 - 실시간 통신에서는 불필요한 오버헤드가 발생할 수 있음 |
| 성능 | - 지속적인 연결을 유지하고 헤더 크기가 작아 효율적인 데이터 전송이 가능 - 주식, 채팅, 게임, 비디오 스트리밍 등 **실시간 통신**에서 성능이 뛰어남 | - 요청-응답 구조로 인해 연결 및 데이터 전송에 소요되는 시간이 길어짐 - 실시간 통신을 위해서는 추가적인 기술(Polling, Long Polling 등)이 필요 |
| 통신 프로토콜 | - HTTP에서 연결 설정 후, **ws:// 또는 wss://**(SSL/TLS 지원)로 전환하여 별도의 웹소켓 프로토콜로 통신 | - **HTTP/HTTPS**를 사용하며, 기본적으로 요청-응답 모델을 따름 |

## STOMP 란?

**STOMP (Simple/Stream Text Oriented Message Protocol)** 란 웹소켓 상에서 동작하는 간단하고 가벼운 문자 기반 메시징 프로토콜입니다.

STOMP 를 통해 서버와 클라이언트는 전송할 메시지의 유형, 형식, 내용들을 정의할 수 있습니다. 이는 기본적으로 **pub/sub**(publish-subscibe) 구조로 되어있고, 클라이언트는 메시지를 주고받기 위해 특정 주제(Topic)를 구독(subscibe)하거나 발행(publish)할 수 있습니다.

> Publish-Subscribe 구조란 메시지를 공급하는 주체와 소비하는 주체를 분리해 제공하는 메시징 방법입니다.

### STOMP 메시지 프레임

```text
COMMAND
header1:value1
header2:value2

Body(optional)
```

- **COMMAND**: 프레임의 목적을 나타내는 명령어입니다. (ex: CONNECT, SEND, SUBSCRIBE, UNSUBSCRIBE 등)
- **헤더(Header)**: 키-값 쌍으로 메시지의 추가 정보를 포함합니다. (예: destination, content-type 등)
- **본문(Body)**: 메시지 내용(payload)에 해당하는 부분으로 텍스트나 JSON 형식 등 자유롭게 사용할 수 있습니다.

### STOMP 를 사용하는 이유

1. 메시지의 형식(frame)을 지정할 수 있어 클라이언트와 서버 간의 통신에서 일관성을 유지할 수 있습니다. (개발자는 메시징 프로토콜 혹은 메시지 형식을 개발할 필요가 없어집니다.)
2. 웹소켓은 연결과 데이터 전송을 위한 **기본적인 통신 채널**만 제공하지만, STOMP와 함께 사용하면 구조화된 메시징 방식을 사용하여 다양한 **메시지 브로커**(RabbitMQ, Kafka 등)와 쉽게 통합할 수 있습니다.
3. 서버는 특정 주제(Topic)를 구독하고 있는 클라이언트에게 메시지를 broadcast 할 수 있고, 이로 인해 편리한 메시지 전송이 가능하다.
4. STOMP는 메시지 전송 상태를 확인할 수 있는 ACK(acknowledge) 메커니즘을 지원하여, 메시지가 손실되지 않고 클라이언트가 수신했음을 확인할 수 있습니다.

## 마치며

이번 기회로 웹소켓과 STOMP 프로토콜의 기본적인 개념에 대해 알아보고, 왜 채팅 서비스에 웹소켓 통신을 사용하는지 이해할 수 있었습니다. 추가로 개념이 궁금하신 분이 있다면 아래 레퍼런스를 참고하시면 좋을 것 같습니다. 감사합니다 :)

> [!note] 레퍼런스
> 아래 레퍼런스를 참고하였습니다.
>
> - [웹소켓 - 위키백과](https://ko.wikipedia.org/wiki/%EC%9B%B9%EC%86%8C%EC%BC%93)
> - [Polling / Long Polling / Streaming](https://velog.io/@hahan/Polling-Long-Polling-Streaming)
> - [[10분 테코톡] ✨ 아론의 웹소켓&스프링](https://www.youtube.com/watch?v=rvss-_t6gzg&t=94s)
> - [[10분 테코톡] 코일의 Web Socket](https://youtu.be/MPQHvwPxDUw?si=-jH-mjq185hMoKW1)

[🔗 [Spring boot] WebSocket 을 사용하여 채팅 서비스 구현하기(2) - 채팅 데이터베이스 설계하기](/posts/spring-websocket-chat-2-data/)
