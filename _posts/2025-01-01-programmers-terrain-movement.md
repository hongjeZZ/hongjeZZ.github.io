---
title: "[프로그래머스/Level4] 지형 이동 - JAVA[자바]"
date: 2025-01-01 23:52:01 +0900
categories: [PS, 프로그래머스]
tags: [BFS, MST, 우선순위 큐]
---

**난이도** : Level 4

**유형 :**BFS / 우선순위 큐

**구현 시간** : 1시간 20분 (못품)

**링크: <https://school.programmers.co.kr/learn/courses/30/lessons/62050>**

[🔗 프로그래머스 SW개발자를 위한 평가, 교육, 채용까지 Total Solution을 제공하는 개발자 성장을 위한 베이스캠프 programmers.co.kr](https://school.programmers.co.kr/learn/courses/30/lessons/62050)

![](/assets/img/programmers-terrain-movement/01.png)

![](/assets/img/programmers-terrain-movement/02.png)

![](/assets/img/programmers-terrain-movement/03.png)

## 문제풀이

위 문제는 Summer/Winter Coding(2019) 기출 문제로 처음으로 풀어보는 레벨 4의 문제였다. 확실히 비슷한 BFS 문제인 [경주로 건설](/posts/programmers-race-track/)보다는 어렵게 느껴졌다. 1시간동안 고민하며 구현한 결과 Node에 좌표 정보와 비용을 저장하고 우선순위 큐를 사용하여 BFS를 구현하는 것에는 성공했지만, 우선순위 큐에 추가할 Node의 비용을 계산할 때 실수가 있어서 테스트 케이스를 통과하지 못하고 실패하였다...

1. BFS 시작 위치는 어느 위치든 비용이 들지 않기 때문에, (0,0) 좌표로 시작하고 비용은 0이다. 위 노드를 큐에 삽입한다.
2. 큐의 요소를 뽑고, 해당 노드의 비용을 총 비용에 더하고 방문 처리를 한다.
3. 노드의 상하좌우 좌표를 탐색한다.
   1. 이미 방문을 했거나, 좌표의 위치가 범위를 벗어낫다면 종료한다.
   2. 해당 좌표의 높이와 노드의 높이의 차가 height 넘는다면 비용을 계산하고, 아니라면 비용은 0이다.
   3. 새로운 좌표, 비용을 노드를 큐에 삽입한다.
4. 큐의 요소가 빌때까지 2 ~ 3번 과정을 반복한다.

## 1차 시도 - 통과 (다른 사람 코드 참조)

```arduino
import java.util.Comparator;
import java.util.PriorityQueue;

class Solution {

    static int total;
    static int[] dx = {-1, 1, 0, 0};
    static int[] dy = {0, 0, -1, 1};

    static class Node {
        int x;
        int y;
        int cost;

        public Node(int x, int y, int cost) {
            this.x = x;
            this.y = y;
            this.cost = cost;
        }
    }

    public int solution(int[][] land, int height) {
        int N = land.length;
        boolean[][] visited = new boolean[N][N];

        PriorityQueue<Node> queue = new PriorityQueue<>(Comparator.comparingInt(o -> o.cost));
        total = 0;

        // 시작점은 어디여도 상관없고, 비용은 0이다.
        queue.offer(new Node(0, 0, 0));

        while (!queue.isEmpty()) {
            Node node = queue.poll();

            // 이미 방문했다면 종료
            if (visited[node.x][node.y]) {
                continue;
            }

            // 방문 처리
            visited[node.x][node.y] = true;
            total += node.cost;

            // 상하좌우 탐색
            for (int i = 0; i < 4; i++) {
                int nx = node.x + dx[i];
                int ny = node.y + dy[i];

                // 이미 방문을 했거나, 범위를 벗어났다면
                if (nx < 0 || ny < 0 || nx >= N || ny >= N || visited[nx][ny]) {
                    continue;
                }

                // 비용 계산
                int cost = Math.abs(land[nx][ny] - land[node.x][node.y]);

                if (cost > height) {
                    queue.offer(new Node(nx, ny, cost));
                } else {
                    queue.offer(new Node(nx, ny, 0));
                }
            }
        }
        return total;
    }
}
```
