---
title: "[BOJ/Silver2] 18353번 병사 배치하기 - JAVA[자바]"
date: 2025-01-27 21:56:37 +0900
categories: [PS, 백준]
tags: [DP, Lis]
---

**난이도** : 실버 2

**유형 :** 동적 계획법 / LIS

**링크** : <https://www.acmicpc.net/problem/18353>

**구현 시간** : 30분

![](/assets/img/boj-18353-soldier-placement/01.png)

## 문제 풀이

이 문제는 ‘가장 긴 감소하는 부분 수열’을 찾는 문제로, **LIS(가장 긴 증가하는 부분 수열)** 알고리즘을 변형해서 해결할 수 있습니다.

DP 테이블은 각 위치에서 끝나는 가장 긴 감소하는 부분 수열의 길이를 저장합니다. 예를 들어, dp[i]는 i번째 숫자를 마지막으로 포함하는 가장 긴 감소하는 부분 수열의 길이를 의미합니다.

- 각 숫자를 기준으로 그 이전 숫자들과 비교합니다.
- 만약 현재 숫자(arr[i])가 이전 숫자(arr[j])보다 작다면, 이전 숫자를 포함하는 감소하는 수열에 현재 숫자를 추가할 수 있습니다.
  - 이 경우, dp[i]를 dp[j] + 1로 업데이트합니다. (즉, j번째 숫자까지의 수열에 현재 숫자 하나를 더한 것이 됩니다.)

## 1차 시도 - 통과

```arduino
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.StringTokenizer;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        int N = Integer.parseInt(br.readLine());

        // 수열 정보 저장
        int[] arr = new int[N + 1];
        int[] dp = new int[N + 1];
        StringTokenizer st = new StringTokenizer(br.readLine());
        for (int i = 1; i < N + 1; i++) {
            arr[i] = Integer.parseInt(st.nextToken());
            dp[i] = 1;
        }

        int max = 0;

        for (int i = 1; i < N + 1; i++) {
            for (int j = 1; j < i; j++) {
                if (arr[i] < arr[j]) {
                    int res = Math.max(dp[i], dp[j] + 1);
                    dp[i] = res;
                }
            }

            if (dp[i] > max) {
                max = dp[i];
            }
        }

        System.out.println(N - max);
    }
}
```
