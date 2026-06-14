---
title: application.properties 및 Profile 설정
date: 2024-08-14 14:30:18 +0900
categories: [Back-End, Spring]
tags: [Spring]
---

## 1. `application.properties` 파일 설정

### application.properties

>`application.properties`는 Spring Framework와 Spring Boot에서 애플리케이션 설정을 관리하기 위해 사용되는 주요 구성 파일이다. 이 파일을 통해 애플리케이션이 실행될 때 필요한 환경 설정 값들을 정의할 수 있다.

- 예를 들어, 데이터베이스 연결 정보, 서버 포트 설정, 로깅 레벨 등 다양한 설정을 지정할 수 있다.
- 기본적으로 key-value 형식으로 이루어져 있으며, 매우 간단하고 직관적으로 구성할 수 있는 장점이 있다.
- [참고 - 스프링 공식 문서](https://docs.spring.io/spring-boot/appendix/application-properties/index.html)

<br>

### 설정 파일 생성 (예시)

```properties
xxx.version = v.1.0.0
xxx.minimum-order-amount = 1
xxx.support-vendors = a, b, c, d
```

- `xxx.version`: 애플리케이션 버전을 지정
- `xxx.minimum-order-amount`: 최소 주문 금액을 설정
- `xxx.support-vendors`: 지원하는 공급 업체 목록을 지정

<br>

### `AppConfiguration` 생성

```java
@Configuration
@ComponentScan(basePackages = {"org.xxx.xxx.order", "org.xxx.xxx.voucher", "org.xxx.xxx.config"})
@PropertySource(value = "application.properties")
public class AppConfiguration {}
```

- `@PropertySource` 어노테이션을 사용해 `application.properties` 파일에서 설정된 속성들을 읽어온다.
- 이 파일에 정의된 설정 값들은 애플리케이션의 다양한 컴포넌트에서 사용할 수 있다.

<br>

### `OrderTester` 클래스

```java
public class OrderTester {
    public static void main(String[] args) {
        var applicationContext = new AnnotationConfigApplicationContext(AppConfiguration.class);
        var environment = applicationContext.getEnvironment();
        
        String version = environment.getProperty("xxx.version");
        Integer minimumOrderAmount = environment.getProperty("minimum-order-amount", Integer.class);
        List<String> supportVendors = environment.getProperty("support-vendors", List.class);
    }
}
```

- 기본 타입은 `String`이며, 타입 변환이 필요하면 매개변수에 타입 클래스를 명시한다.
- 만약 변환이 불가능할 경우 `NumberFormatException`이 발생한다.

출력 결과:

```java
version = v.1.0.0
minimumOrderAmount = 1
supportVendors = [a, b, c, d]
```

<br>

### `OrderProperties` 클래스

```java
@Component
public class OrderProperties implements InitializingBean {

    @Value("${xxx.version:v0.0.0}")
    private String version;

    @Value("${xxx.minimum-order-amount:2}")
    private Integer minimumOrderAmount;

    @Value("${xxx.support-vendors}")
    private List<String> supportVendors;

    @Override
    public void afterPropertiesSet() throws Exception {
        System.out.println("version = " + version);
        System.out.println("minimumOrderAmount = " + minimumOrderAmount);
        System.out.println("supportVendors = " + supportVendors);
    }
}
```

- `@Value` 어노테이션을 사용해 `application.properties` 파일에 정의된 값을 주입받는다.
- 설정 파일에 값이 없다면, `@Value`에 지정된 기본 값(콜론으로 지정)이 사용된다.

<br>

---

## 2. YAML 설정 파일로 작성

### `application.yaml` 생성

> `application.yaml`은 `application.properties`와 유사한 역할을 하지만, YAML 형식을 사용하여 더 구조화된 방식으로 설정을 관리할 수 있다. 
> 이러한 장점이 있기 때문에, 규모가 큰 프로젝트에서 YAML 으로 작성하고, 규모가 작은 프로젝트는 properties로 작성하는 경우가 많다.

```yaml
xxx:
  version: "v1.0.0"
  minimum-order-amount: 1
  support-vendors:
    - a
    - b
    - c
    - d
  description: |-
    line 1 hello world
    line 2 xxxx
    line 3
```

<br>

### `AppConfiguration` 수정

```java
@Configuration
@ComponentScan(basePackages = {"org.xxx.xxx.order", "org.xxx.xxx.voucher", "org.xxx.xxx.config"})
@PropertySource(value = "application.yaml", factory = YamlPropertiesFactory.class)
@EnableConfigurationProperties
public class AppConfiguration {}
```

- `@PropertySource`에서 `	value`를 변경하고 `factory`를 추가해 YAML 파일을 지원하도록 설정한다.
- 기본적으로 Spring Framework는 YAML을 지원하지 않으므로 `PropertySourceFactory`를 구현하여 사용해야 한다.
- 또한, `@EnableConfigurationProperties` 을 붙여 스프링 부트에 있는 내용인 것을 알려줌
- Spring-Boot 를 사용하면 구현하지 않고 읽어올 수 있다.

<br>

### `YamlPropertiesFactory` 클래스

```java
import org.springframework.beans.factory.config.YamlPropertiesFactoryBean;
import org.springframework.core.env.PropertiesPropertySource;
import org.springframework.core.env.PropertySource;
import org.springframework.core.io.support.EncodedResource;
import org.springframework.core.io.support.PropertySourceFactory;

import java.io.IOException;
import java.util.Properties;

public class YamlPropertiesFactory implements PropertySourceFactory {

    @Override
    public PropertySource<?> createPropertySource(String name, EncodedResource resource) throws IOException {
        YamlPropertiesFactoryBean yamlPropertiesFactoryBean = new YamlPropertiesFactoryBean();
        yamlPropertiesFactoryBean.setResources(resource.getResource());

        Properties properties = yamlPropertiesFactoryBean.getObject();
        return new PropertiesPropertySource(resource.getResource().getFilename(), properties);
    }
}
```

<br>

### `OrderProperties` 클래스 수정

```java
import lombok.Getter;
import lombok.Setter;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

import java.util.List;

@Configuration
@ConfigurationProperties(prefix = "xxx")
@Getter @Setter
public class OrderProperties implements InitializingBean {

    private String version;
    private Integer minimumOrderAmount;
    private List<String> supportVendors;
    private String description;

    @Override
    public void afterPropertiesSet() throws Exception {
        System.out.println("version = " + version);
        System.out.println("minimumOrderAmount = " + minimumOrderAmount);
        System.out.println("supportVendors = " + supportVendors);
        System.out.println("description = " + description);
    }
}
```

- `@ConfigurationProperties(prefix = "xxx")`를 사용하여 YAML 파일에 정의된 속성들을 주입받는다.
- 이때 `setter` 메서드가 필요하다.

<br>

---

## 3. Profile 설정

### `JdbcOrderRepository` (dev 프로파일)

```java
@Repository
@Profile("dev")
public class JdbcOrderRepository implements OrderRepository {
    private final Map<UUID, Order> storage = new ConcurrentHashMap<>();

    @Override
    public Order insert(Order order) {
        storage.put(order.getOrderId(), order);
        return order;
    }
}
```

- `@Profile` 어노테이션을 사용하여 특정 프로파일에서만 동작하도록 설정할 수 있다.
- 위 예제에서는 `dev` 프로파일에서만 `JdbcOrderRepository`가 동작하도록 설정되었다.

<br>

### `MemoryOrderRepository` (local 프로파일)

```java
@Repository
@Profile("local")
public class MemoryOrderRepository implements OrderRepository {
    private final Map<UUID, Order> storage = new ConcurrentHashMap<>();

    @Override
    public Order insert(Order order) {
        storage.put(order.getOrderId(), order);
        return order;
    }
}
```

- `local` 프로파일에서만 사용되도록 설정되었다.

<br>

### `OrderTester` 클래스

```java
public class OrderTester {
    public static void main(String[] args) {
        var applicationContext = new AnnotationConfigApplicationContext();
        applicationContext.register(AppConfiguration.class);
        var environment = applicationContext.getEnvironment();
        environment.setActiveProfiles("local");
        applicationContext.refresh();

        OrderRepository orderRepository = applicationContext.getBean(OrderRepository.class);
        System.out.println(MessageFormat.format("is Jdbc Repo -> {0}", orderRepository instanceof JdbcOrderRepository));
        System.out.println(MessageFormat.format("is Jdbc Repo -> {0}", orderRepository.getClass().getSimpleName()));
    }
}
```

- `environment.setActiveProfiles("local");`을 통해 프로파일을 설정한다.
- 이외에도 IDE 우측 상단 Launcher에 vm option을 편집하여 추가할 수 있다.
- `local` 프로파일이 활성화되었기 때문에 `MemoryOrderRepository`가 빈으로 주입된다. 출력 결과는 다음과 같다.

```java
is Jdbc Repo -> false
is Jdbc Repo -> MemoryOrderRepository
```

<br>

### YAML 파일을 프로파일로 그룹화 (1)

#### `application.yaml`
```yaml
#Default properties
servers:
  - dev.bar.com
  - foo.bar.com

# 하지만 SpringFrameWork 에서는 Profile 에 따른 properties 변경은 지원하지 않는다.
# Spring-boot 에서 지원하는 기능이다.
---
spring.config.activate.on-profile: local
xxx:
  version: "v1.0"
  minimum-order-amount: 1
  support-vendors:
    - local-a
    - local-b
    - local-c
    - local-d
  description: |-
    line 1 hello world
    line 2 xxxx
    line 3

---
spring.config.activate.on-profile: dev
xxx:
  version: "v1.0"
  minimum-order-amount: 1
  support-vendors:
    - dev-a
    - dev-b
    - dev-c
    - dev-d
  description: |-
    line 1 hello world
    line 2 xxxx
    line 3
---
```
<br>

#### `XxxApplication`
```java
@ComponentScan(basePackages = {"org.xxx.xxx.order", "org.xxx.xxx.voucher", "org.xxx.xxx.config"})
@SpringBootApplication
public class XxxApplication {

	public static void main(String[] args) {
		// 1. profile 활성화 혹은 2.우측 상단 Spring Launcher 에서 profiles 에 "local"을 추가
		SpringApplication springApplication = new SpringApplication(XxxApplication.class);
		springApplication.setAdditionalProfiles("dev");
		ConfigurableApplicationContext applicationContext = springApplication.run(args);

		OrderRepository orderRepository = applicationContext.getBean(OrderRepository.class);
		System.out.println(MessageFormat.format("is Jdbc Repo -> {0}", orderRepository instanceof JdbcOrderRepository));
		System.out.println(MessageFormat.format("is Jdbc Repo -> {0}", orderRepository.getClass().getSimpleName()));
	}
}
```
- SpringFrameWork 에서는 Profile 에 따른 properties 변경은 지원하지 않고, Spring-boot 에서 지원하는 기능이다.
- 따라서 `@SpringBootApplication` 에서 실행한다.

<br>

### YAML 파일을 프로파일로 그룹화 (2)
> 각 프로파일별로 다른 설정 값을 유지할 수 있다. 
`application-dev.yaml`은 `dev` 프로파일이 활성화될 때 사용되며, `application-local.yaml`은 `local` 프로파일이 활성화될 때 사용된다.

#### `application.yaml` (기본 설정)

```yaml
xxx:
  version: "v.1.0.0"
  minimum-order-amount: 1
  support-vendors:
    - a
    - b
    - c
    - d
  description: |-
    line 1 hello world
    line 2 xxxx
    line 3
```

#### `application-dev.yaml` (dev 프로파일 설정)

```yaml
xxx:
  version: "v1.0.0"
  minimum-order-amount: 1
  support-vendors:
    - dev-a
    - dev-b
    - dev-c
    - dev-d
  description: |-
    line 1 hello world
    line 2 xxxx
    line 3
```

#### `application-local.yaml` (local 프로파일 설정)

```yaml
xxx:
  version: "v.1.0.0"
  minimum-order-amount: 1
  support-vendors:
    - local-a
    - local-b
    - local-c
   

 - local-d
  description: |-
    line 1 hello world
    line 2 xxxx
    line 3
```
