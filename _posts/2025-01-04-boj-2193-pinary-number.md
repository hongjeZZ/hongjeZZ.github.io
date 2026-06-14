---
title: "[BOJ/Silver3] 2193번 이친수 - JAVA[자바]"
date: 2025-01-04 23:36:17 +0900
categories: [PS, 백준]
tags: [DP]
---

**난이도** : 실버 3

**유형 :** DP(동적 계획법)

**링크** : <https://www.acmicpc.net/problem/2193>

**구현 시간** : 30분

![](/assets/img/boj-2193-pinary-number/01.png)

## 문제풀이

위 문제는 전형적인 DP 문제 유형이다. 풀이는 반복문을 사용한 Bottom-Up 방식으로 해결하였다.

이 문제를 해결하기 위해서는 이친수의 규칙을 파악해야 한다.

이진수가 0으로 끝나는 수는 다음 자리 숫자일 때, 0과 1로 생성되고, 1로 끝나는 수는 0으로 생성된다.

예를 들면, 10010 이라는 이진수는 다음 6자리수에서 10010 + 0, 10010 + 1 로 생성된다.

또한, 10001 이라는 이진수는 다음 6자리수에서 10001 + 0 으로 생성된다.

따라서 N 번째 자리수에서 0으로 끝나는 이친수와, 1로 끝나는 이친수의 점화식은 다음과 같다.

> Zero(N) = Zero(N-1) + One(N-1)  
> One(N) = Zero(N-1)

따라서 위와 같은 점화식을 세울 수 있다. 위 점화식을 코드로 구현하면 아래와 같다.

## 1차 시도 - 통과 (Bottom-Up)

```java
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        int N = Integer.parseInt(br.readLine());
        
        long[][] dp = new long[N + 1][2];
        dp[1] = new long[]{0, 1};
        
        for (int i = 2; i < N + 1; i++) {
            dp[i][0] = dp[i - 1][0] + dp[i - 1][1];
            dp[i][1] = dp[i - 1][0];
        }
        
        System.out.println(dp[N][0] + dp[N][1]);
    }
}
```
