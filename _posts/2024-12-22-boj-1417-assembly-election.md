---
title: "[BOJ/Silver5] 1417번 국회의원 선거 - JAVA[자바]"
date: 2024-12-22 01:19:30 +0900
categories: [PS, 백준]
tags: [구현, 그리디, 우선순위 큐]
---

**난이도** : 실버 5

**유형** : 그리디 / 구현 / 우선순위 큐

**링크** : <https://www.acmicpc.net/problem/1417>

![](/assets/img/boj-1417-assembly-election/01.png)

![](/assets/img/boj-1417-assembly-election/02.png)

## 문제 풀이

1. 1. 후보의 수가 1 이하일 경우 0 반환
   2. 1번(다솜이) 득표수 저장, 이외 다른 후보들의 득표수 저장
   3. 각 후보 득표수들의 최대 득표수 저장 및 후보 인덱스 저장
   4. 다솜이의 득표수가 최대 득표수보다 크다면 반복문 탈출
   5. 아니라면 최대 득표자의 득표수를 -1, 다솜이 득표수 +1

## 1차 시도- 통과

```java
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder sb = new StringBuilder();

        int N = Integer.parseInt(br.readLine());
        int target = Integer.parseInt(br.readLine());

        // 예외 케이스
        if (N <= 1) {
            System.out.println(0);
            return;
        }

        int[] arr = new int[N - 1];
        int answer = 0;

        // 1번을 제외한 각 후보의 득표수 저장
        for (int i = 0; i < N - 1; i++) {
            arr[i] = Integer.parseInt(br.readLine());
        }

        while (true) {
            // 각 후보들의 최대값과 해당 인덱스 저장
            int idx = -1;
            int max = Integer.MIN_VALUE;
            // 최대값 찾기
            for (int i = 0; i < N - 1; i++) {
                if (arr[i] > max) {
                    max = arr[i];
                    idx = i;
                }
            }
            // 1번(다솜이) 득표수가 최대값보다 크다면 탈출
            if (target > max) {
                break;
            }
            // 1번 득표수를 하나 올리고, 최대 득표자의 득표수를 하나 내림
            target++;
            arr[idx]--;
            answer++;
        }
        System.out.println(answer);
    }
}
```

## 2차 시도 - 우선순위 큐 사용

```java
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.Collections;
import java.util.PriorityQueue;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder sb = new StringBuilder();

        int N = Integer.parseInt(br.readLine());
        int target = Integer.parseInt(br.readLine());

        // 예외 케이스
        if (N <= 1) {
            System.out.println(0);
            return;
        }

        PriorityQueue<Integer> pq = new PriorityQueue<>(Collections.reverseOrder());
        int answer = 0;

        // 1번을 제외한 각 후보의 득표수를 우선순위 큐에 저장
        for (int i = 0; i < N - 1; i++) {
            pq.add(Integer.parseInt(br.readLine()));
        }

        while (!pq.isEmpty() && pq.peek() >= target) {
            target++;
            answer++;
            pq.add(pq.poll() - 1);
        }
        System.out.println(answer);
    }
}
```
