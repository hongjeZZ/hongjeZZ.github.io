---
title: "[프로그래머스/Level3] 경주로 건설 - JAVA[자바]"
date: 2024-12-31 12:22:22 +0900
categories: [PS, 프로그래머스]
tags: [BFS, 카카오, 큐]
---

**난이도** : Level 3

**유형** : BFS / 큐

**구현 시간** : 1시간 (못품)

**링크** : <https://school.programmers.co.kr/learn/courses/30/lessons/67259>

[🔗 프로그래머스 - 경주로 건설](https://school.programmers.co.kr/learn/courses/30/lessons/67259)

![](/assets/img/programmers-race-track/01.png)

![](/assets/img/programmers-race-track/02.png)

![](/assets/img/programmers-race-track/03.png)

![](/assets/img/programmers-race-track/04.png)

## 문제풀이

위 문제는 2020 카카오 인턴십 코딩 테스트에 출제된 문제로 현재까지 풀어본 BFS 문제와는 다르게 생각이 많이 필요했다.

최단 경로를 구한다고 하더라도 그 경로가 가장 저렴한 비용이 들지 않기 때문에 최소 비용을 저장해서 문제를 구현했다.

1. x, y 좌표 및 방향 정보를 저장하는 cost 배열을 사용해서 시작점을 제외한 모든 데이터를 최대값으로 저장한다.
2. Queue 에는 x, y 좌표, 방향 정보, 비용을 담아 상하좌우 방향으로 순회하며 탐색을 하였고, 같은 방향과 좌표인 경우 비용이 더 많이 든다면 탐색을 종료했다.
3. 도착지를 향하는 모든 비용을 우선순위 큐에 담아서 제일 저렴한 비용을 반환했는데, 불필요한 자료구조를 사용한 것 같다.

## 1차 시도 - 통과 (다른 사람 코드 참조)

```java
import java.util.Arrays;
import java.util.LinkedList;
import java.util.PriorityQueue;
import java.util.Queue;

class Solution {
    int N;
    int[][][] cost;
    int[] dx = {0, 0, -1, 1};
    int[] dy = {1, -1, 0, 0};

    public int solution(int[][] board) {
        N = board.length;
        cost = new int[N][N][4];

        // 최대 금액 저장
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < N; j++) {
                Arrays.fill(cost[i][j], Integer.MAX_VALUE);
            }
        }

        // 시작점 초기화
        for (int i = 0; i < 4; i++) {
            cost[0][0][i] = 0; // 모든 방향에서 시작점 비용을 0으로 설정
        }

        return bfs(board);
    }

    public int bfs(int[][] board) {
        Queue<int[]> q = new LinkedList<>();
        PriorityQueue<Integer> pq = new PriorityQueue<>();

        // 행, 열, 방향, 비용
        q.offer(new int[]{0, 0, -1, 0});

        while (!q.isEmpty()) {
            int[] poll = q.poll();
            int x = poll[0];
            int y = poll[1];
            int d = poll[2];
            int nowCost = poll[3];

            if (x == N - 1 && y == N - 1) {
                pq.add(nowCost);
            }

            for (int i = 0; i < 4; i++) { // 동, 서, 북, 남 방향 탐색
                int nx = x + dx[i];
                int ny = y + dy[i];
                int newCost;

                // board 를 벗어나거나, 벽이 있다면 즉시 종료
                if (nx >= N || ny >= N || nx < 0 || ny < 0 || board[nx][ny] == 1) {
                    continue;
                }

                // 금액 계산
                // 방향이 같거나, 처음 시작하는 경우라면 100원 추가
                if (d == i || d == -1) {
                    newCost = nowCost + 100;
                }
                // 그게 아니라면, 100 + 500 = 600원 추가
                else {
                    newCost = nowCost + 600;
                }

                // cost[][] 의 값과 비교하여 더 금액이 같거나 낮게 든다면 실행
                if (cost[nx][ny][i] >= newCost) {
                    q.offer(new int[]{nx, ny, i, newCost});
                    cost[nx][ny][i] = newCost;
                }
            }
        }
        return pq.poll();
    }
}
```

```java
// Test Case 25
int[][] board = {
        {0, 0, 0, 0, 0},
        {0, 1, 1, 1, 0},
        {0, 0, 1, 0, 0},
        {1, 0, 0, 0, 1},
        {1, 1, 1, 0, 0}
};
```

마지막 테스트 케이스 25번을 계속 실패했었는데, 그 이유는 board[4][3] 지점에서 서로 다른 경로가 만나게 되는데 방향이 다름에도 금액만 비교하여 잘못된 최소값을 저장하는 문제였다.

이러한 문제는 방향 정보를 고려하지 않기 때문에 우측 경로가 board[4][3] 지점에서 더 저렴하여 선택되지만, 그 이후 코너를 건설하는 비용이 추가되어 좌측 경로가 정답이었다. 이를 해결하기 위해 **cost 배열에 방향 정보를 추가한 3차원 배열**을 사용했다. 하지만 이러한 배열은 성능이 좋지 않을 것으로 우려되어 2차 시도에 개선해서 다시 문제를 풀어보았다.

## 2차 시도 - 통과

```java
import java.util.Arrays;
import java.util.LinkedList;
import java.util.Queue;

class Solution {
    int N;
    int[][][] cost;
    int[] dx = {0, 0, -1, 1};
    int[] dy = {1, -1, 0, 0};

    public int solution(int[][] board) {
        N = board.length;
        cost = new int[N][N][4];

        // 최대 금액 저장
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < N; j++) {
                Arrays.fill(cost[i][j], Integer.MAX_VALUE);
            }
        }

        // 시작점 초기화
        for (int i = 0; i < 4; i++) {
            cost[0][0][i] = 0; // 모든 방향에서 시작점 비용을 0으로 설정
        }

		// BFS 실행
        bfs(board);

		// 최소 비용 계산
        int answer = Integer.MAX_VALUE;

        for (int i = 0; i < 4; i++) {
            answer = Math.min(answer, cost[N - 1][N - 1][i]);
        }

        return answer;
    }

    public void bfs(int[][] board) {
        Queue<int[]> q = new LinkedList<>();

        // 행, 열, 방향, 비용
        q.offer(new int[]{0, 0, -1, 0});

        while (!q.isEmpty()) {
            int[] poll = q.poll();
            int x = poll[0];
            int y = poll[1];
            int d = poll[2];
            int nowCost = poll[3];

            for (int i = 0; i < 4; i++) { // 동, 서, 북, 남 방향 탐색
                int nx = x + dx[i];
                int ny = y + dy[i];
                int newCost;

                // board 를 벗어나거나, 벽이 있다면 즉시 종료
                if (nx >= N || ny >= N || nx < 0 || ny < 0 || board[nx][ny] == 1) {
                    continue;
                }

                // 금액 계산
                // 방향이 같거나, 처음 시작하는 경우라면 100원 추가
                if (d == i || d == -1) {
                    newCost = nowCost + 100;
                }
                // 그게 아니라면, 100 + 500 = 600원 추가
                else {
                    newCost = nowCost + 600;
                }

                // cost[][] 의 값과 비교하여 더 금액이 낮게 든다면 실행
                if (cost[nx][ny][i] > newCost) {
                    q.offer(new int[]{nx, ny, i, newCost});
                    cost[nx][ny][i] = newCost;
                }
            }
        }
    }
}
```
