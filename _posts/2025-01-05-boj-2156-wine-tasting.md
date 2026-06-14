---
title: "[BOJ/Silver1] 2156번 포도주 시식 - JAVA[자바]"
date: 2025-01-05 00:14:09 +0900
categories: [PS, 백준]
tags: [DP]
---

**난이도** : 실버 1

**유형** : DP(동적 계획법)

**링크** : [백준 2156번 - 포도주 시식](https://www.acmicpc.net/problem/2156)

**구현 시간** : 1시간

![](/assets/img/boj-2156-wine-tasting/01.png)

![](/assets/img/boj-2156-wine-tasting/02.png)

## 문제풀이

이 문제를 풀기 위해 DP의 Bottom-Up 방식을 사용하며, [9465번 스티커 문제](/posts/boj-9465-sticker/)와 같이 이전 선택에 따라 다음 선택이 제한된다.

연속 세 잔의 포도주를 마실 수 없기 때문에 마지막 잔의 앞 잔, 앞앞 잔의 값이 크다면 마지막 잔을 마시지 않을 수도 있다는 점도 고려해야 한다.

따라서 N 번째 잔의 최대값을 구하려면 아래와 같은 경우를 고려해야 한다.

1. N 번째 잔을 마시지 않는다.
2. N 번째 잔을 마신다.
   1. N - 3 -> N - 1 -> N 번째 잔을 마신다.
   2. N - 2 -> N 번째 잔을 마신다.

위 경우를 고려해서 표현한 점화식은 아래와 같다.

> DP[i] = max(DP[i-1], max(DP[i-2], DP[i-3] + graph[i-1]) + grape[i])

나의 경우는 N 번째 잔을 마시지 않는 경우는 생각하지 못해서 이 부분을 생각하는 것에 오랜 시간이 걸렸다.

위 점화식을 코드로 표현하면 아래와 같다.

## 1차 시도 - 성공

```java
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        int N = Integer.parseInt(br.readLine());
        
        int[] grape = new int[N + 1];
        
        for (int i = 1; i < N + 1; i++) {
            grape[i] = Integer.parseInt(br.readLine());
        }
        
        int[] dp = new int[N + 1];
        
        if (N == 1) {
            System.out.println(grape[1]);
            return;
        } else if (N == 2) {
            System.out.println(grape[1] + grape[2]);
            return;
        }
        
        dp[1] = grape[1];
        dp[2] = grape[1] + grape[2];
        
        for (int i = 3; i < N + 1; i++) {
            dp[i] = Math.max(dp[i - 1], Math.max(dp[i - 2], dp[i - 3] + grape[i - 1]) + grape[i]);
        }
        
        System.out.println(dp[N]);
    }
}
```
