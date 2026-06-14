---
title: "[프로그래머스/Level2] 미로탈출 - JAVA[자바]"
date: 2024-12-31 10:01:05 +0900
categories: [PS, 프로그래머스]
tags: [BFS, 큐]
---

**난이도** : Level 2

**유형** : BFS / 큐

**구현 시간** : 30분

**링크** : [프로그래머스 - 미로 탈출](https://school.programmers.co.kr/learn/courses/30/lessons/159993)

![](/assets/img/programmers-maze-escape/01.png)

![](/assets/img/programmers-maze-escape/02.png)

![](/assets/img/programmers-maze-escape/03.png)

![](/assets/img/programmers-maze-escape/04.png)

## 문제풀이

위 문제는 BFS 탐색 알고리즘을 사용하여 최단 경로를 찾는 문제이다. 앞서 백준을 통해 BFS / DFS 문제를 많이 연습해두었기에 알고리즘을 구현하는 것은 오래 걸리지 않았지만 BFS 를 총 2번 실행하는 과정에서 데이터 초기화에 문제를 겪었다.

1. 시작점, 레버, 도착지의 위치 정보 저장
2. 시작점 -> 레버까지 최단 경로를 BFS 를 통해 구함
   1. 만약 레버까지 도달할 수 없다면 -1 을 반환
3. 레버 -> 도착지까지 최단 경로를 BFS 를 통해 구함
   1. 만약 도착지까지 도달할 수 없다면 -1 을 반환
4. 두 최단 경로의 합을 반환

## 1차 시도 - 통과

```java
import java.util.LinkedList;
import java.util.Queue;

class Solution {

    int N;
    int M;
    int[] start;
    int[] lever;
    int[] exit;
    int[][] distance;
    int[] dx = {0, 0, -1, 1};
    int[] dy = {1, -1, 0, 0};

    public int solution(String[] maps) {
        int answer = 0;
        N = maps.length;
        M = maps[0].length();

        // 위치 정보 저장
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < M; j++) {
                if (maps[i].charAt(j) == 'S') {
                    start = new int[]{i, j};
                } else if (maps[i].charAt(j) == 'E') {
                    exit = new int[]{i, j};
                } else if (maps[i].charAt(j) == 'L') {
                    lever = new int[]{i, j};
                }
            }
        }

        // 레버를 당기러 가는 최단 경로 구하기
        int bfsLever = bfs(start, lever, maps);

        if (bfsLever == -1) {
            return -1;
        }
        answer += bfsLever;

        // 레버를 당긴 위치에서 출입구로 나가는 최단 경로 구하기
        int bfsExit = bfs(lever, exit, maps);

        if (bfsExit == -1) {
            return -1;
        }
        answer += bfsExit;
        return answer;
    }

    public int bfs(int[] idx, int[] destination, String[] maps) {
        // 변수 초기화
        Queue<int[]> q = new LinkedList<>();
        boolean[][] visited = new boolean[N][M];
        distance = new int[N][M];
        distance[idx[0]][idx[1]] = 0;

        // 방문 처리
        visited[idx[0]][idx[1]] = true;
        q.offer(idx);

        // 큐의 요소가 남지 않을 때까지 반복
        while (!q.isEmpty()) {
            int[] poll = q.poll();
            int x = poll[0];
            int y = poll[1];

            if (x == destination[0] && y == destination[1]) {
                return distance[x][y];
            }

            // 상하좌우 탐색
            for (int i = 0; i < 4; i++) {
                int nx = x + dx[i];
                int ny = y + dy[i];

                // 미로의 범위에서 벗어나면 종료
                if (nx < 0 || ny < 0 || nx > N - 1 || ny > M - 1) {
                    continue;
                }

                // 벽이 아니고, 방문하지 않았으면 방문 처리
                if (maps[nx].charAt(ny) != 'X' && !visited[nx][ny]) {
                    // 방문 처리
                    visited[nx][ny] = true;
                    q.offer(new int[]{nx, ny});
                    distance[nx][ny] += distance[x][y] + 1;
                }
            }
        }
        return -1;
    }
}
```

레버까지의 최단 경로를 구하고나서 Queue 를 초기화해 주어야 하는데 그 부분을 생각하지 못해서 디버깅 시간이 오래 걸렸다. Queue 를 초기화하지 않으면 출발지에서 레버까지 도달했을 때 Queue 에 남아있는 요소들이 있기 때문에 올바르게 최단 경로를 구할 수 없으니 조심해야 한다.
