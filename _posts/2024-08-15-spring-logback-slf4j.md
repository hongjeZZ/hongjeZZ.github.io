---
title: "[Spring] Loggig 과 Logback 설정, 그리고 SLF4J"
date: 2024-08-15 15:27:31 +0900
categories: [Back-End, Spring]
tags: [Spring, logback]
---

## 1. Logging

### Logging이란?

로깅이란 시스템이 작동할 때 발생하는 다양한 정보를 기록하는 과정을 말한다. 이 기록은 시스템의 작동 상태를 모니터링하거나, 사용자의 행동 패턴을 분석하는 데 유용하다. 시스템의 동작을 분석하고, 문제를 진단하는 데도 로깅은 필수적이다. 간단히 말해, 시스템에서 발생하는 모든 주요 이벤트를 기록으로 남기는 것을 로깅이라고 한다.  
> [출처: 네이버 지식백과](https://terms.naver.com/entry.naver?docId=796754&cid=42347&categoryId=42347)

<br>

### 로그 사용의 장점

- 쓰레드 정보, 클래스 이름 같은 추가적인 정보를 확인할 수 있고, 로그의 출력 형식을 자유롭게 조정할 수 있다.
- 로그 레벨을 설정하여 개발 환경에서는 모든 로그를 출력하고, 운영 환경에서는 중요한 로그만 출력하도록 설정할 수 있다.
- 로그는 단순히 콘솔 출력에 그치지 않고, 파일이나 네트워크와 같은 외부 저장소에 기록될 수 있다. 
  - 특히 파일로 로그를 남길 때는 일별, 또는 특정 용량에 따라 로그 파일을 분할 관리할 수 있다.
- 일반적인 `System.out` 출력보다 성능이 뛰어나다. 내부 버퍼링과 멀티 쓰레드를 활용해 로깅 성능을 최적화하기 때문이다. 따라서 실제 운영 환경에서는 `System.out.println()` 대신 로그 프레임워크를 사용하는 것이 필수적이다.

<br>

### 운영 환경에서 `System.out`을 사용하지 않는 이유
- `System.out.println()`은 내부적으로 `synchronized` 키워드를 사용해 오버헤드가 발생할 수 있다. 이는 심각한 성능 저하로 이어질 수 있다.
- 운영 환경에서는 이러한 성능 저하를 피하기 위해 `System.out.println()`을 사용하지 않는다.

<br>

### 자바가 지원하는 Logging Framework

- **java.util.logging**
- **Apache Commons Logging**
- **Log4J**
- **Logback**: 현재 가장 많이 사용되는 프레임워크
- **SLF4J (Simple Logging Facade for Java)**
  - 로깅 프레임워크를 추상화한 것으로, Facade 패턴을 이용한 프레임워크이다.
  - **Facade 패턴**은 복잡한 내부 구조를 단순화하여 편리한 인터페이스를 제공하는 디자인 패턴이다.
  - [참고 - 퍼사드 패턴](https://refactoring.guru/design-patterns/facade)

<br>

### 로그 레벨

- **TRACE**
  - 가장 상세한 로그 레벨로, 애플리케이션의 실행 흐름과 디버깅 정보를 기록한다. 주로 디버깅 시 사용된다.
  
- **DEBUG**
  - 디버깅 목적으로 사용되며, 개발 단계에서 상세한 정보를 기록한다. 애플리케이션의 내부 동작을 이해하고 문제를 분석하는 데 도움을 준다.
- **INFO**
  - 정보성 메시지를 기록하며, 애플리케이션의 주요 이벤트나 실행 상태에 대한 정보를 전달한다.
- **WARN**
  - 경고성 메시지를 기록하며, 예상치 못한 문제나 잠재적인 오류 상황을 알리는 메시지이다. 애플리케이션이 정상적으로 동작하지만 주의가 필요한 상황을 알려준다.
- **ERROR**
  - 오류 메시지를 기록하며, 심각한 문제 또는 예외 상황을 나타내어 애플리케이션의 정상적인 동작에 영향을 미칠 수 있는 문제를 알린다.
- **FATAL**
  - 아주 심각한 에러가 발생한 상태를 나타내며, 시스템적으로 심각한 문제가 발생해서 어플리케이션이 작동 불가능할 경우
  - 일반적으로 어플리케이션에서는 사용할 경우가 없음

<br>

### 로그 사용 예시

```java
private static final Logger logger = LoggerFactory.getLogger("org.xxx.xxx.OrderProperties");
//    private static final Logger logger = LoggerFactory.getLogger(OrderProperties.class);
```

- Logger는 클래스 이름으로 생성하며, 패키지를 포함하여 지정한다.
- 로그는 패키지의 `.`을 기준으로 제어가 가능하다.
  - ex) `org.xxx.xxx // WARN`, `org.xxx.xxx.voucher // INFO`
- Logger는 `static`으로 생성하여 클래스당 하나만 존재하도록 하며, `private final`로 생성해 불변성을 보장한다.

```java
@Override
public void afterPropertiesSet() {
    logger.debug("version = {}", version);
    logger.debug("minimumOrderAmount = {}", minimumOrderAmount);
    logger.debug("supportVendors = {}", supportVendors);
    logger.debug("description = {}", description);
}
```

- 디버그 레벨로 로그를 기록한다.

<br>

## 2. Logback 설정하기

### logback 설정 파일의 검색 순서
1. `logback-test.xml`
2. `logback.groovy`
3. `logback.xml`
4. 기본 설정 전략 (`BasicConfigurator`)

<br>

### logback.xml 구성

- **`<logger>`**: `name` 속성을 통해 클래스별로 지역 설정이 가능하며, `additivity` 속성을 통해 로그 레벨의 상속 여부를 설정할 수 있다.
- **`<root>`**: 전역 설정을 담당하며, `name` 속성이 없고, `level` 속성을 통해 로그 레벨만 지정한다.
- **`<appender>`**: 로그 메시지의 출력 대상을 결정한다. `ConsoleAppender`, `FileAppender`, `RollingFileAppender` 등이 있다.

<br>

### ConsoleAppender

```xml
<configuration>
  <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
    <encoder>
      <pattern>%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} -%kvp- %msg%n</pattern>
    </encoder>
  </appender>

  <logger name="org.xxx.xxx" level="info">
      <appender-ref ref="STDOUT"/>
  </logger>

  <root level="debug">
    <appender-ref ref="STDOUT" />
  </root>
</configuration>
```
- [logback 공식문서](https://logback.qos.ch/manual/configuration.html)를 참고하여 `BasicConfigurator` 설정 가져오기

<br>

### FileAppender

```xml
<timestamp key="bySecond" datePattern="yyyyMMdd'T'HHmmss"/>
<property name="FILE_LOG_PATTERN" value ="%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} -%kvp- %msg%n"/>

<appender name="FILE" class="ch.qos.logback.core.FileAppender">
    <file>logs/xxx_${bySecond}.log</file>
    <encoder>
        <pattern>${FILE_LOG_PATTERN}</pattern>
    </encoder>
</appender>

<logger name="org.xxx.xxx" level="info">
    <appender-ref ref="FILE"/>
</logger>
```

- **`<timestamp>`**: `key` 속성으로 이름을 지정
  - `datePattern` 속성으로 날짜 패턴을 지정한다. [(참고 자료)](https://docs.oracle.com/javase/8/docs/api/java/text/SimpleDateFormat.html)
- **`<property>`**: `name`과 `value` 속성을 통해 로그 출력 패턴을 정의한다.
- **로그 출력 예시**: `logs/xxx_20240815T140842.log`

<br>

### RollingFileAppender

```xml
<configuration>
    <conversionRule conversionWord="clr" converterClass="org.springframework.boot.logging.logback.ColorConverter"/>
    <property name="CONSOLE_LOG_PATTERN" value ="%clr(%d{HH:mm:ss.SSS}){yellow} [%thread] %clr(%-5level) %logger{36} -%kvp- %msg%n"/>
    <property name="FILE_LOG_PATTERN" value ="%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} -%kvp- %msg%n"/>

    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>${CONSOLE_LOG_PATTERN}</pattern>
        </encoder>
    </appender>

    <appender name="ROLLING_FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>logs/access.log</file>
        <rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">
            <fileNamePattern>logs/access-%d{yyyy-MM-dd}.log</fileNamePattern>
        </rollingPolicy>
        <encoder>
            <pattern>${FILE_LOG_PATTERN}</pattern>
        </encoder>
    </appender>

    <logger name="org.xxx.xxx" level="info">
        <appender-ref ref="ROLLING_FILE"/>
    </logger>

    <root level="warn">
        <appender-ref ref="STDOUT" />
    </root>
</configuration>
```

- `conversionRule`
  - conversionWord 속성을 통해 이름을 지정
  - converterClass 속성을 통해 Converter 클래스 지정
- `<file>logs/access.log</file>`
    - 현재 날짜의 로그 파일은 access.log 로 생성
- `<rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">`
    - `<fileNamePattern>logs/access-%d{yyyy-MM-dd}.log</fileNamePattern>`
    - 다음 날짜로 바뀔 때, access.log 파일은 access-`%d{yyyy-MM-dd}`.log 로 바뀌고, 다음 날짜가 access.log 파일로 생성됨
<br>

## 3. Lombok의 @Slf4j

`@Slf4j` 어노테이션을 사용하면 간단하게 로그 객체를 생성할 수 있다.

### 이전 코드

```java
@Configuration
@ConfigurationProperties(prefix = "xxx")
@Getter @Setter
public class OrderProperties implements InitializingBean {

    private static final Logger logger = LoggerFactory.getLogger(OrderProperties.class);

    private String version;
    private Integer minimumOrderAmount;
    private List<String> supportVendors;
    private String description;

    @Override
    public void afterPropertiesSet() {
        logger.debug("version = {}", version);
        logger.debug("minimumOrderAmount = {}", minimumOrderAmount);
        logger.debug("supportVendors = {}", supportVendors);
        logger.debug("description = {}", description);
    }
}
```

### @Slf4j 적용 후 코드

```java
@Configuration
@ConfigurationProperties(prefix = "xxx")
@Getter @Setter @Slf4j
public class OrderProperties implements InitializingBean {

    private String version;
    private Integer minimumOrderAmount;
    private List<String> supportVendors;
    private String description;

    @Override
    public void afterPropertiesSet() {
        log.debug("version = {}", version);
        log.debug("minimumOrderAmount = {}", minimumOrderAmount);
        log.debug("supportVendors = {}", supportVendors);
        log.debug("description = {}", description);
    }
}
```

- `@Slf4j` 어노테이션을 사용하면 `Logger` 객체를 명시적으로 생성할 필요 없이, `log`라는 이름으로 바로 접근할 수 있다.
- 이를 통해 코드가 더욱 간결해지고, 불필요한 보일러플레이트 코드가 줄어든다.

---
#### 📖 참고 자료
  - [(Spring Boot)Logging과 Profile 전략](https://meetup.toast.com/posts/149)

#### 🎥 참고영상

- [스프링 부트 2.0 Day 11. 스프링 프로파일과 스프링 부트 기본 로깅](https://www.youtube.com/watch?v=h_VoxXhhNH0)

- [스프링 부트 2.0 Day 12. 커스텀 로그 설정 제공하기와 logback에서 스프링 프로파일 사용하기](https://www.youtube.com/watch?v=uVR2iBEb474)

- [스프링캠프 2015[A-3]: 스프링부트와 로깅](https://www.youtube.com/watch?v=o2-JaRD9qQE)-
