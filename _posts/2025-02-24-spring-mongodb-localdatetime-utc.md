---
title: "[Spring Boot] MongoDB LocalDateTime 저장 시 UTC로 저장되는 문제"
date: 2025-02-24 16:37:26 +0900
categories: [Back-End, Spring]
tags: [MongoDB, Spring Boot, ZonedDateTime]
---

## **문제 상황**

![](/assets/img/spring-mongodb-localdatetime-utc/01.png)

Spring Boot 환경에서 MongoDB에 **LocalDateTime**을 저장할 때, **Date 컬럼이 자동으로 UTC로 변환되어 저장**되는 문제가 발생했습니다.  
  
예를 들어, 한국 시간(KST) 기준 18시 36분에 전송한 채팅 메시지가 국제 표준 시간(UTC) 기준 09시 36분으로 저장됩니다.  
그러나 데이터를 다시 Spring Boot 애플리케이션에서 조회하면, 시스템 기본 시간대(KST)로 변환되어 정상적으로 출력되는 것을 확인할 수 있습니다.  
  
해당 문제는 비즈니스 로직에 직접적인 영향을 미치지는 않지만, 팀 내에서 데이터 저장 시간과 변환 방식에 대한 혼동이 발생할 수 있습니다. 데이터베이스에 저장된 시간과 애플리케이션에서 조회된 시간이 다르게 보이기 때문에 개발자나 운영팀이 시간 데이터를 해석하는 데 어려움을 겪을 수 있습니다.

이에 따라, MongoDB에 저장되는 시간을 UTC가 아닌 KST 기준으로 저장하도록 변경하기로 결정했습니다.

## **원인**

해당 문제의 원인은 MongoDB는 Date 타입을 저장할 때, 항상 UTC로 변환하여 저장하기 때문입니다.

MongoDB는 시간대(Time Zone) 정보를 별도로 저장하지 않으며, 모든 Date 타입의 데이터를 **UTC로 변환하여 저장**합니다.

일반적으로 사용하는 MySQL, PostgreSQL은 서버 레벨에서 *'SET time_zone'* 등의 명령어로 Time Zone을 간단하게 변경할 수 있지만, MongoDB는 Time Zone 변경을 지원하지 않습니다.

즉, 애플리케이션에서 *LocalDateTime.now()*로 현재 시간을 저장하면, 시스템의 기본 시간대(KST)에서 UTC로 변환되어 저장됩니다.

## **해결 방법**

### **1. LocalDateTime -> ZonedDateTime으로 변경 (실패)**

해당 프로젝트는 한국(KST)에서만 운영될 예정이므로, 시간대 정보를 명시적으로 저장할 필요가 없다고 판단하여 **LocalDateTime**을 사용해 왔습니다.

LocalDateTime은 시간대 정보를 포함하지 않으며, 실제 사람이 사용하는 시간을 나타내는 데 적합합니다.

이러한 LocalDateTime은 동일한 값을 여러 시간대에서 다르게 해석할 위험이 있음으로, 시간대 정보를 포함하는 ZonedDateTime을 사용하여 문제를 해결하려고 했습니다.

```java
ZonedDateTime sentAt = ZonedDateTime.now(ZoneId.of("Asia/Seoul"));
```

그러나 MongoDB는 ZonedDateTime을 직접 저장할 수 없으며, 이를 지원하는 기본 컨버터(ZonedDateTimeConverter)가 제공되지 않습니다. 따라서 ZonedDateTime을 사용하려고 하면 다음과 같은 직렬화 오류가 발생했습니다.

```shell
org.bson.codecs.configuration.CodecConfigurationException:
	Can't find a codec for class java.time.ZonedDateTime
```

이 오류는 MongoDB가 ZonedDateTime과 같은 복잡한 시간대 정보를 포함한 타입을 기본적으로 지원하지 않기 때문이었습니다.

---

### **2. MongoConfig에 커스텀 컨버터 설정 (성공)**

첫 번째 방법으로 실패한 후, Spring Data MongoDB에서 제공하는 **Custom Conversions** 기능을 활용하여 문제를 해결했습니다.

[🔗 Custom Conversions :: Spring Data MongoDB Generally, we inspect the Converter implementations for the source and target types they convert from and to. Depending on whether one of those is a type the underlying data access API can handle natively, we register the converter instance as a reading or docs.spring.io](https://docs.spring.io/spring-data/mongodb/reference/mongodb/mapping/custom-conversions.html)

**Custom Conversions**는 데이터를 저장하거나 읽을 때 원하는 값으로 변환할 수 있도록 지원하는 기능입니다.

이를 위해 Converter<T, R> 인터페이스를 구현하고, @ReadingConverter와 @WritingConverter 어노테이션을 사용하여 Document를 조회 및 저장할 때 컨버터를 명시적으로 지정할 수 있습니다.

#### **LocalDateTimeToDateKstConverter.java (저장 시 KST로 변환하는 컨버터)**

```java
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.Date;
import org.springframework.core.convert.converter.Converter;
import org.springframework.data.convert.WritingConverter;
import org.springframework.stereotype.Component;

@Component
@WritingConverter
public class LocalDateTimeToDateKstConverter implements Converter<LocalDateTime, Date> {

    private static final int KST_OFFSET_HOURS = 9;

    @Override
    public Date convert(LocalDateTime source) {
        return convertToKst(source);
    }

    // KST 로 변환하기 위해 9시간을 더함
    private Date convertToKst(LocalDateTime localDateTime) {
        return Timestamp.valueOf(localDateTime.plusHours(KST_OFFSET_HOURS));
    }
}
```

이 컨버터는 LocalDateTime을 KST 기준으로 변환하여 MongoDB에 저장합니다.

데이터 저장 시 9시간을 더하여 UTC로 저장되는 것을 방지합니다.

#### **DateToLocalDateTimeKstConverter.java (조회 시 KST로 변환하는 컨버터)**

```java
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Date;
import org.springframework.core.convert.converter.Converter;
import org.springframework.data.convert.ReadingConverter;
import org.springframework.stereotype.Component;

@Component
@ReadingConverter
public class DateToLocalDateTimeKstConverter implements Converter<Date, LocalDateTime> {

    private static final int KST_OFFSET_HOURS = 9;

    @Override
    public LocalDateTime convert(Date source) {
        return convertToKst(source);
    }

    // KST 로 변환하기 위해 9시간을 빼줌
    private LocalDateTime convertToKst(Date date) {
        LocalDateTime localDateTime = date.toInstant().atZone(ZoneId.systemDefault()).toLocalDateTime();
        return localDateTime.minusHours(KST_OFFSET_HOURS);
    }
}
```

이 컨버터는 MongoDB에서 UTC로 저장된 Date 타입을 KST 기준으로 변환합니다.

저장 시 9시간을 더했으므로, 조회 시 9시간을 빼서 원래의 KST 시간을 복원합니다.

#### **MongoConfig.java**

```java
import com.example.mate.common.util.converter.DateToLocalDateTimeKstConverter;
import com.example.mate.common.util.converter.LocalDateTimeToDateKstConverter;
import java.util.List;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.mongodb.MongoDatabaseFactory;
import org.springframework.data.mongodb.core.convert.DbRefResolver;
import org.springframework.data.mongodb.core.convert.DefaultDbRefResolver;
import org.springframework.data.mongodb.core.convert.DefaultMongoTypeMapper;
import org.springframework.data.mongodb.core.convert.MappingMongoConverter;
import org.springframework.data.mongodb.core.convert.MongoCustomConversions;
import org.springframework.data.mongodb.core.mapping.MongoMappingContext;

@Configuration
public class MongoConfig {

    @Bean
    public MappingMongoConverter mappingMongoConverter(
            MongoDatabaseFactory mongoDatabaseFactory,
            MongoMappingContext mongoMappingContext,
            LocalDateTimeToDateKstConverter dateKstConverter,
            DateToLocalDateTimeKstConverter localDateTimeKstConverter
    ) {
        DbRefResolver dbRefResolver = new DefaultDbRefResolver(mongoDatabaseFactory);
        MappingMongoConverter converter = new MappingMongoConverter(dbRefResolver, mongoMappingContext);

        // "_class" 타입을 저장하지 않도록 설정
        converter.setTypeMapper(new DefaultMongoTypeMapper(null));

        // MongoDB KST 변환 컨버터 설정
        converter.setCustomConversions(new MongoCustomConversions(
                List.of(localDateTimeKstConverter, dateKstConverter)
        ));

        return converter;
    }
}
```

위에서 만든 컨버터를 **MappingMongoConverter**에 등록하여, 자동으로 변환이 적용되도록 설정합니다.

![컨버터를 설정한 후 데이터를 저장하면 정상적으로 실제 KST 시간이 반영되어 저장되는 것을 확인할 수 있습니다.](/assets/img/spring-mongodb-localdatetime-utc/02.png)

위 과정을 통해 MongoDB에 KST 기준으로 시간을 저장하고 조회할 수 있게 되었습니다.

그러나 이 방법은 근본적인 해결책이 아니라, 특정 시간대(KST)에 종속된 임시적인 해결책입니다.

만약 애플리케이션이 여러 시간대를 지원해야 한다면, 각 시간대별로 컨버터를 커스터마이징해야 하기 때문에 유지보수가 복잡해질 수 있기 때문에, 공통적으로 UTC로 시간대를 저장하는 게 더 바람직할 수 있습니다.

이번 트러블 슈팅을 통해 애플리케이션에서 사용하는 날짜 타입의 클래스들의 특징과 글로벌 서비스에서 ZonedDateTime을 사용하는 것이 가지는 이점을 알 수 있었습니다.
