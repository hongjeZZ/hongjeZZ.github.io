---
title: "[BOJ/Gold5] 14503번 로봇 청소기 - JAVA[자바]"
date: 2024-12-23 16:56:01 +0900
categories: [PS, 백준]
tags: [구현, 시뮬레이션]
---

**난이도** : 골드 5

**유형** : 구현 / 시뮬레이션

**링크** : <https://www.acmicpc.net/problem/14503>

![](/assets/img/boj-14503-robot-vacuum/01.png)

![](/assets/img/boj-14503-robot-vacuum/02.png)

## 문제풀이

로봇 청소기의 규칙대로 알고리즘을 차례대로 구현했다.

구현에 대한 고민은 크게 어렵지 않았다. 로봇 청소기의 방향은 Map 자료구조를 사용해서 저장했다.

## 1차 시도 - 통과

```java
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.HashMap;
import java.util.Map;

public class Main {

    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));

        String[] NM = br.readLine().split(" ");
        int N = Integer.parseInt(NM[0]);
        int M = Integer.parseInt(NM[1]);

        String[] RCD = br.readLine().split(" ");
        int R = Integer.parseInt(RCD[0]);
        int C = Integer.parseInt(RCD[1]);
        int D = Integer.parseInt(RCD[2]); // 0 -> 북, 1 -> 동, 2 -> 남, 3 -> 서

        Map<Integer, int[]> direction = new HashMap<>();
        direction.put(0, new int[]{-1, 0});  // 북
        direction.put(1, new int[]{0, 1});  // 동
        direction.put(2, new int[]{1, 0}); // 남
        direction.put(3, new int[]{0, -1}); // 서

        int[][] room = new int[N][M];

        for (int i = 0; i < N; i++) {
            String[] roomStatus = br.readLine().split(" ");
            for (int j = 0; j < M; j++) {
                room[i][j] = Integer.parseInt(roomStatus[j]);
            }
        }

        // 청소 횟수
        int cnt = 0;

        while (true) {
            // 현재 칸이 아직 청소되지 않은 경우, 현재 칸을 청소한다.
            if (room[R][C] == 0) {
                room[R][C] = 2;
                cnt++;
            }

            // 현재 칸의 주변 4칸 중 청소되지 않은 빈 칸이 없는 경우
            if (room[R - 1][C] != 0 && room[R + 1][C] != 0 && room[R][C + 1] != 0 && room[R][C - 1] != 0) {
                // 바라보는 방향을 유지한 채로 한 칸 후진할 수 있다면 한 칸 후진하고 1번으로 돌아간다.
                int[] directions = direction.get(D);
                R -= directions[0];
                C -= directions[1];

                // 바라보는 방향의 뒤쪽 칸이 벽이라 후진할 수 없다면 작동을 멈춘다.
                if (room[R][C] == 1) {
                    break;
                }
                // 현재 칸의 주변 4칸 중 청소되지 않은 빈 칸이 있는 경우
            } else {
                // 반시계 방향으로 90도 회전한다.
                D = D != 0 ? D - 1 : 3;
                // 바라보는 방향을 기준으로 앞쪽 칸이 청소되지 않은 빈 칸인 경우 한 칸 전진한다.
                int[] directions = direction.get(D);
                if (room[R + directions[0]][C + directions[1]] == 0) {
                    R += directions[0];
                    C += directions[1];
                }
            }
        }
        System.out.println(cnt);
    }
}
```
