---
title: REST(ful) API 정리
date: 2024-09-01 12:25:53 +0900
categories: [CS, 네트워크]
tags: [CS, REST API]
---

### REST 란?
- **REST(Representational State Transfer)** 는 월드 와이드 웹과 같은 분산 하이퍼미디어 시스템을 위한 소프트웨어 아키텍처의 한 형식이다. 
- 로이 필딩(Roy Fielding)의 2000년 박사학위 논문에서 소개되었고, 필딩은 HTTP의 주요 저자 중 한 사람
- 엄격한 의미로 REST는 네트워크 아키텍처 원리의 모음
- ‘네트워크 아키텍처 원리’란 자원을 정의하고 자원에 대한 주소를 지정하는 방법을 의미한다.
- 간단한 의미로는, 웹 상의 자료를 HTTP 위에서 SOAP이나 쿠키를 통한 세션 트랙킹 같은 별도의 전송 계층 없이 전송하기 위한 아주 간단한 인터페이스를 말다.

### API 란?
- 컴퓨터 프로그래밍에서, 애플리케이션 프로그래밍 인터페이스(API)는 서브루틴 정의, 프로토콜 및 도구의 집합으로, 애플리케이션 소프트웨어를 구축하기 위한 것을 의미한다. 
- 일반적으로 이는 다양한 소프트웨어 컴포넌트 간의 명확하게 정의된 통신 방법의 집합을 의미하고, 좋은 API는 모든 빌딩 블록을 제공하여 프로그래머가 쉽게 컴퓨터 프로그램을 개발할 수 있게 해준다. 
- API는 웹 기반 시스템, 운영 체제, 데이터베이스 시스템, 컴퓨터 하드웨어 또는 소프트웨어 라이브러리용일 수 있다.

> 💡REST API란  ->  REST 아키텍쳐 스타일을 따르는 API

<br>


### REST 아키텍처 스타일과 주요 원칙

- **클라이언트-서버 (Client-Server)**
  - 클라이언트와 서버는 서로 독립적으로 동작한다. 클라이언트는 사용자 인터페이스와 관련된 작업을 수행하고, 서버는 데이터 저장 및 비즈니스 로직을 처리한다. 이를 통해 클라이언트의 이식성(다양한 플랫폼에서 동작 가능)과 서버의 확장성을 높인다.

- **스테이트리스 (Stateless)**
  - 서버는 클라이언트의 상태를 저장하지 않는다. 각 요청은 독립적이며, 필요한 모든 정보를 포함해야 한다. 이로 인해 시스템의 확장성과 신뢰성이 높아진다. 클라이언트는 매 요청마다 필요한 모든 데이터를 포함해야 하며, 서버는 이를 처리하여 응답을 반환한다.

- **캐시 (Cache)**
  - 응답 데이터는 캐시가 가능해야 한다. 클라이언트는 서버로부터 받은 데이터를 캐시하여, 동일한 요청에 대해 서버와 재통신하지 않고도 데이터를 재사용할 수 있다. HTTP의 Last-Modified나 E-Tag 헤더를 사용해 캐싱을 구현할 수 있다.

- **균일한 인터페이스 (Uniform Interface)**
  - 모든 리소스에 대해 동일한 URI 구조와 메소드(GET, POST, PUT, DELETE 등)를 사용한다. 이렇게 하면 클라이언트와 서버 간의 상호작용이 단순해지고, 시스템의 일관성을 유지할 수 있다.

- **계층화된 시스템 (Layered System)**
  - 서버는 다중 계층으로 구성될 수 있으며, 보안, 로드 밸런싱, 암호화 등 다양한 기능을 추가할 수 있다. 클라이언트는 중간 계층의 존재를 알 필요가 없으며, 이를 통해 구조상의 유연성이 향상된다.

<br> 


### API 설계 원칙

API를 설계할 때는 몇 가지 중요한 원칙을 따라야 한다. 이러한 원칙을 준수하면 클라이언트와 서버 간의 통신이 명확하고 효율적으로 이루어질 수 있다.

1. **URI는 자원을 명확히 표현해야 한다.**
   - URI(Uniform Resource Identifier)는 자원을 식별하는 데 사용되며, 명사로 자원을 표현하는 것이 좋다. 예를 들어, `/members/1`은 특정 회원을 나타낸다.
   - 예시:
     - ❌ `GET /members/delete/1` (잘못된 방식, URI에 동사를 사용함)
     - ✅ `DELETE /members/1` (올바른 방식, 자원을 명확히 표현하고 HTTP 메소드를 활용)

2. **행위는 HTTP 메소드로 표현한다.**
   - 자원에 대한 CRUD(Create, Read, Update, Delete) 작업은 HTTP 메소드로 표현한다. 예를 들어, `GET` 메소드는 데이터를 조회하고, `POST` 메소드는 데이터를 생성하며, `DELETE` 메소드는 데이터를 삭제한다.
   - 예시:
     - ❌ `GET /members/show/1` (잘못된 방식, 행위를 URI에 포함)
     - ✅ `GET /members/1` (올바른 방식, HTTP 메소드를 사용)

3. **슬래시(/) 구분자는 계층 관계를 나타낸다.**
   - URI에서 슬래시 구분자는 계층 구조를 나타내는 데 사용한다. 예를 들어, `/members/1/orders`는 특정 회원의 주문을 의미한다.

4. **URI 마지막에 슬래시(/)를 포함하지 않는다.**
   - URI의 마지막에 슬래시를 포함하는 것은 혼란을 초래할 수 있으므로, 마지막에 슬래시를 생략하는 것이 좋다.

5. **하이픈(-)은 URI 가독성을 높인다.**
   - URI에서 하이픈은 단어를 구분하는 데 사용하여 가독성을 높인다. 예를 들어, `/user-profiles`는 `/userprofiles`보다 읽기 쉽다.
   
<br>


### Richardson Maturity Model
![](/assets/img/restful-api/01.png)

RESTful API의 성숙도를 측정하는 모델로, 쉽게 말해 API가 얼마나 RESTful한지 평가하는 데 사용된다.

- **Level 0: HTTP 사용**  
  - HTTP 프로토콜만 사용하며, URI나 HTTP 메소드를 고려하지 않고 모든 작업을 하나의 엔드포인트에서 수행한다.

- **Level 1: 리소스 사용**  
  - 리소스 URI를 사용하여 데이터를 구분하지만, HTTP 메소드는 사용하지 않는다.

- **Level 2: HTTP 메소드 사용**  
  - CRUD 작업에 HTTP 메소드를 사용하여 리소스 조작을 수행한다.

- **Level 3: HATEOAS 사용**  
  - Hypermedia as the Engine of Application State(HATEOAS)를 도입하여, 클라이언트가 리소스와 상호작용할 수 있도록 리소스 간의 링크를 포함한다. HATEOAS는 리소스 상태를 표현하는 JSON 문서에서 링크를 제공하여, 클라이언트가 어떤 작업을 할 수 있는지 안내한다.
  
<br>

#### HATEOAS 예시 (TODO data)

```json
{ 
  "id": "1", 
  "contents": "공부합시다.", 
  "createAt": "2020-01-01 12:00:00", 
  "likes": 2, 
  "likesOfMe": false, 
  "comments": [], 
  "writer": { 
    "id": "2", 
    "email": "harry@gmail.com", 
    "name": "harry" 
  }, 
  "links": [ 
    {"rel": "self", "action": "GET", "href": "/api/v1/posts/1"}, 
    {"rel": "deletePost", "action": "DELETE", "href": "/api/v1/posts/1"}, 
    {"rel": "getWriter", "action": "GET", "href": "/api/v1/users/2"}, 
    {"rel": "addComment", "action": "POST", "href": "/api/v1/posts/1/comments"} 
  ] 
}
```

위의 JSON 예시에서, 각 리소스는 어떤 상태에 있으며, 어떤 액션을 취할 수 있는지에 대한 정보를 포함하고 있다. 
`links` 배열 안의 요소들은 리소스 간의 관계를 설명하며, 클라이언트가 후속 작업을 어떻게 수행할지 안내해준다.

---
### reference
[Richardson Maturity Model](https://martinfowler.com/articles/richardsonMaturityModel.html)
[위키피디아](https://wikipedia.org/wiki/API)
