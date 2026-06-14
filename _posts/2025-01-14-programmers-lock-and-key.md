---
title: "[프로그래머스/Level3] 자물쇠와 열쇠 - JAVA[자바]"
date: 2025-01-14 21:20:21 +0900
categories: [PS, 프로그래머스]
tags: [구현, 시뮬레이션]
---

**난이도** : Level 3

**유형 :** 구현 / 시뮬레이션

**구현 시간** : 1시간

**링크: <https://school.programmers.co.kr/learn/courses/30/lessons/60059>**

[🔗 프로그래머스 SW개발자를 위한 평가, 교육, 채용까지 Total Solution을 제공하는 개발자 성장을 위한 베이스캠프 programmers.co.kr](https://school.programmers.co.kr/learn/courses/30/lessons/60059)

![](/assets/img/programmers-lock-and-key/01.png)

![](/assets/img/programmers-lock-and-key/02.png)

## 문제풀이

위 문제는 2차원 배열에 대한 높은 이해도가 필요하다. 제한사항을 자세히 보면, Key와 Lock의 크기가 3에서 최대 20으로 작은 것을 보니 완전탐색을 이용해서 풀 수 있다. 나는 (Lock 배열 길이 + Key 배열의 길이 * 2)의 크기의 2차원 배열을 새로 선언하여, 정사각형의 중앙에 Lock 배열을 삽입하고, 모든 경우를 전부 탐색하도록 구현했다.

1. Lock 배열 길이 + Key 배열의 길이 * 2 크기의 새로운 2차원 배열 arr 생성한다.
2. arr 의 중앙에 lock 배열을 삽입한다.
3. key 배열을 90도로 회전하여 4번 탐색한다.
   1. key 배열을 처음부터 끝까지 모든 경우 arr 배열에 삽입해보며 자물쇠가 열리는 지 확인한다.
   2. 자물쇠가 열린다면 그 즉시 true 를 반환하고 종료한다.
   3. key를 더했을 때 자물쇠가 열리지 않는다면 다시 arr 배열에서 key의 값을 빼고 3-1번으로 돌아간다.

## 1차 시도 - 통과

```java
class Solution {

    int M;
    int N;
    int length;

    public boolean solution(int[][] key, int[][] lock) {
        M = key.length;
        N = lock.length;
        length = N + (M - 1) * 2;

        int[][] arr = new int[length][length];
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < N; j++) {
                arr[i + M - 1][j + M - 1] = lock[i][j];
            }
        }

        if (check(arr)) {
            return true;
        }

        // Key 4방향 탐색
        for (int i = 0; i < 4; i++) {
            // 모든 경우의 수 확인
            for (int j = 0; j <= length - M; j++) {
                for (int k = 0; k <= length - M; k++) {
                    // key 의 요소 더하기
                    for (int l = 0; l < M; l++) {
                        for (int m = 0; m < M; m++) {
                            arr[l + j][m + k] += key[l][m];
                        }
                    }
                    // key 를 더한 후, 해당 칸의 0이 남아있는지 확인
                    if (check(arr)) {
                        return true;
                    }
                    // 다시 key 를 빼기
                    for (int l = 0; l < M; l++) {
                        for (int m = 0; m < M; m++) {
                            arr[l + j][m + k] -= key[l][m];
                        }
                    }
                }
            }
            // 시계 방향 90도 회전
            key = rotate(key);
        }

        return false;
    }

    int[][] rotate(int[][] arr) {
        int n = arr.length;
        int m = arr[0].length;
        int[][] rotate = new int[m][n];

        for (int i = 0; i < rotate.length; i++) {
            for (int j = 0; j < rotate[i].length; j++) {
                rotate[i][j] = arr[n - 1 - j][i];
            }
        }
        return rotate;
    }

    boolean check(int[][] arr) {
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < N; j++) {
                if (arr[i + M - 1][j + M - 1] != 1) {
                    return false;
                }
            }
        }
        return true;
    }
}
```

## 마치며

**개인적으로 이 문제보다 "문자열 압축"이 훨씬 어렵게 다가왔던 것 같다. 그만큼 문자열 문제에 대한 이해도가 부족한 것이니 문자열 관련 문제를 더 열심히 풀어보고 정리해야겠다...**
