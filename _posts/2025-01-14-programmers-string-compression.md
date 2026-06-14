---
title: "[프로그래머스/Level2] 문자열 압축 - JAVA[자바]"
date: 2025-01-14 20:55:39 +0900
categories: [PS, 프로그래머스]
tags: [구현, 문자열]
---

**난이도** : Level 2

**유형** : 문자열 / 구현

**구현 시간** : 1시간

**링크** : [프로그래머스 - 문자열 압축](https://school.programmers.co.kr/learn/courses/30/lessons/60057)

![](/assets/img/programmers-string-compression/01.png)

![](/assets/img/programmers-string-compression/02.png)

## 문제풀이

1. 주어진 문자열을 1 ~ 문자열의 절반 길이까지 잘라가며 압축된 문자열의 길이를 비교한다.
2. 문자열을 자를 땐, 잘라진 앞부분(target) 을 설정하고 그 뒤로 남은 문자열을 자르며 비교한다.
3. 만약 target 과 다음으로 자른 문자열(compare)이 같다면 cnt 를 1 증가시키고, 다음 문자열로 넘어간다.
4. target 과 compare 이 같지 않은 경우에는 새로운 압축 문자열을 선언하고 cnt, target 을 차례대로 붙여준다.
5. 이렇게 3 ~ 4번을 반복하면 압축된 문자열이 생성되는데, 그 문자열의 길이를 현재까지 최소 길이와 비교해서 대입해준다.

## 1차 시도 - 통과

```java
class Solution {
    public int solution(String s) {
    	// 문자열의 최대길이는 압축되지 않은 문자열의 길이
        int answer = s.length();

		// 1 ~ 문자열의 길이의 반까지 잘라가며 반복
        for (int i = 1; i < s.length() / 2 + 1; i++) {
            int cnt = 1;
            String compressed = "";
            String target = s.substring(0, i);

			// target 과 남은 문자열 비교하기
            for (int j = i; j <= s.length(); j = j + i) {
                int end = Math.min(s.length(), i + j);
                String compare = s.substring(j, end);
                
                if (compare.equals(target)) {
                    cnt++;
                } else {
                	// cnt가 0일 땐 cnt를 포함시키지 않는다.
                    if (cnt > 1) {
                        compressed += cnt;
                        cnt = 1;
                    }
                    compressed += target;
                    target = compare;
                }
            }
            // 문자열이 i 로 나누어 떨어지지 않을 수 있으니 마지막 문자열을 더해준다.
            compressed += target;
            answer = Math.min(answer, compressed.length());
        }
        return answer;
    }
}
```
