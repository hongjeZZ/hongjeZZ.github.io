---
title: "[BOJ/Gold1] 1700번 멀티탭 스케줄링 - JAVA[자바]"
date: 2025-02-09 17:23:48 +0900
categories: [PS, 백준]
tags: [구현, 그리디]
---

**난이도** : 골드 1

**유형 :** 그리디 / 구현

**링크** : <https://www.acmicpc.net/problem/1700>

**구현 시간** : 1시간

![](/assets/img/boj-1700-multitap-scheduling/01.png)

## 문제 풀이

이 문제는 **그리디 알고리즘** 유형으로, 멀티탭에 꽂힌 전기용품 중 어떤 것을 제거해야 하는지 결정하는 문제입니다.

멀티탭의 상태를 관리하기 위해 삭제 및 삽입이 용이한 **List 자료구조**를 사용하여 구현하였습니다.

- 현재 멀티탭이 비어있거나 빈 구멍이 있는 경우
  - 새로운 전기용품을 그대로 꽂습니다.
- 새로운 전기용품이 이미 멀티탭에 꽂혀 있는 경우  
  - 추가적인 작업 없이 그대로 넘어갑니다.
- 멀티탭이 꽉 찬 상태에서 새로운 전기용품이 등장할 경우 **( 핵심)**  
  - 1. 이후 사용되지 않는 전기용품이 있다면
    - 해당 전기용품을 제거합니다.
  - 2. 모든 전기용품이 이후에도 사용된다면
    - 가장 마지막에 사용될 전기용품을 제거하면, 이후의 변경 횟수를 최소화할 수 있습니다.

## 1차 시도 - 통과

```java
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.*;

public class Main {

    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringTokenizer st = new StringTokenizer(br.readLine());

        int N = Integer.parseInt(st.nextToken()); // 멀티탭 구멍 개수
        int K = Integer.parseInt(st.nextToken()); // 전기용품 사용 횟수
        int[] arr = new int[K]; // 전기용품 사용 순서

        st = new StringTokenizer(br.readLine());
        for (int i = 0; i < K; i++) {
            arr[i] = Integer.parseInt(st.nextToken());
        }

        List<Integer> plugged = new ArrayList<>(); // 현재 꽂혀 있는 전기용품
        int cnt = 0;

        for (int i = 0; i < K; i++) {
            int current = arr[i];

            // 이미 꽂혀 있는 경우
            if (plugged.contains(current)) {
                continue;
            }

            // 멀티탭에 빈 공간이 있는 경우
            if (plugged.size() < N) {
                plugged.add(current);
                continue;
            }

            // 전기용품을 교체해야 하는 경우
            int lastUseItem = -1;
            Integer removeTarget = -1;

            for (Integer item : plugged) {
                int nextUse = Integer.MAX_VALUE; // 사용 예정이 없을 경우 방지
                for (int j = i; j < K; j++) {
                    if (arr[j] == item) {
                        nextUse = j;
                        break;
                    }
                }

                if (nextUse > lastUseItem) {
                    lastUseItem = nextUse;
                    removeTarget = item;
                }
            }

            plugged.remove(removeTarget);
            plugged.add(current);
            cnt++;
        }

        System.out.println(cnt);
    }
}
```
