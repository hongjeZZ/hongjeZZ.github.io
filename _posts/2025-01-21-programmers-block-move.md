---
title: "[프로그래머스/Level3] 블록 이동하기 - JAVA[자바]"
date: 2025-01-21 21:51:20 +0900
categories: [PS, 프로그래머스]
tags: [BFS, 구현]
---

**난이도** : Level 3

**유형**: BFS / 구현

**구현 시간** : 1시간

**링크**: <https://school.programmers.co.kr/learn/courses/30/lessons/60063>

[🔗 프로그래머스 - 블록 이동하기](https://school.programmers.co.kr/learn/courses/30/lessons/60063)

## 문제 설명

로봇개발자 **"무지"**는 한 달 앞으로 다가온 "카카오배 로봇경진대회"에 출품할 **로봇**을 준비하고 있습니다. 준비 중인 로봇은 **2 x 1** 크기의 로봇으로 "무지"는 **"0"**과 **"1"**로 이루어진 **N x N** 크기의 지도에서 **2 x 1** 크기인 로봇을 움직여 **(N, N)** 위치까지 이동 할 수 있도록 프로그래밍을 하려고 합니다. 로봇이 이동하는 지도는 가장 왼쪽, 상단의 좌표를 **(1, 1)**로 하며 지도 내에 표시된 숫자 **"0"**은 빈칸을 **"1"**은 벽을 나타냅니다. 로봇은 벽이 있는 칸 또는 지도 밖으로는 이동할 수 없습니다. 로봇은 처음에 아래 그림과 같이 좌표 **(1, 1)** 위치에서 가로방향으로 놓여있는 상태로 시작하며, 앞뒤 구분없이 움직일 수 있습니다.

로봇이 움직일 때는 현재 놓여있는 상태를 유지하면서 이동합니다. 예를 들어, 위 그림에서 오른쪽으로 한 칸 이동한다면 **(1, 2), (1, 3)** 두 칸을 차지하게 되며, 아래로 이동한다면 **(2, 1), (2, 2)** 두 칸을 차지하게 됩니다. 로봇이 차지하는 두 칸 중 어느 한 칸이라도 **(N, N)** 위치에 도착하면 됩니다.

![](/assets/img/programmers-block-move/01.png)

![](/assets/img/programmers-block-move/02.png)

위 그림과 같이 로봇은 90도씩 회전할 수 있습니다. 단, 로봇이 차지하는 두 칸 중, 어느 칸이든 축이 될 수 있지만, 회전하는 방향(축이 되는 칸으로부터 대각선 방향에 있는 칸)에는 벽이 없어야 합니다. 로봇이 한 칸 이동하거나 90도 회전하는 데는 걸리는 시간은 정확히 1초 입니다.

**"0"**과 **"1"**로 이루어진 지도인 board가 주어질 때, 로봇이 **(N, N)** 위치까지 이동하는데 필요한 최소 시간을 return 하도록 solution 함수를 완성해주세요.

### 제한 사항

- board의 한 변의 길이는 **5 이상 100 이하**입니다.
- board의 원소는 **0 또는 1**입니다.
- 로봇이 처음에 놓여 있는 칸 **(1, 1), (1, 2)는 항상 0**으로 주어집니다.
- 로봇이 항상 목적지에 **도착할 수 있는 경우만** 입력으로 주어집니다.

### 입출력 예

**board** : [[0, 0, 0, 1, 1],[0, 0, 0, 1, 0],[0, 1, 0, 1, 1],[1, 1, 0, 0, 1],[0, 0, 0, 0, 0]]

**result** : 7

## 문제풀이

위 문제는 BFS 를 베이스로 하여 최단거리를 탐색하는 알고리즘을 요구한다. 하지만 *로봇이 연속 2칸을 차지하는 것*과 일반적인 상하좌우 이동뿐만 아니라 *축을 중심으로 8가지 회전 이동*을 구현해야함으로 이제껏 풀어봤던 BFS 중 생각이 제일 필요했던 문제였다.

나는 Node 클래스로 x,y 좌표를 저장하였고, Machine 클래스에 2개의 Node, 현재 비용, 로봇의 방향(가로, 세로)를 저장했다. BFS 탐색 시 탐색이 가능하다면 Machine 객체를 Queue 자료구조에 저장하고, 다음 탐색을 이어가는 흐름이다.

상하좌우 4가지 이동은 평범한 BFS 문제와 다를 것 없이 *다음 위치를 방문했는 지* 여부와 *해당 좌표가 범위를 벗어났는 지*, *해당 좌표에 벽이 있는 지* 여부를 확인하면 된다. (여기서 방문 여부를 저장은 로봇의 방향을 포함하여 3차원 배열을 사용했다.)

문제는 8가지 회전 이동이다. 이 부분에서 고민이 많았는데, 질문하기 탭에서 힌트를 얻을 수 있었다.

만약 로봇이 가로 방향으로 놓여져 있고 위로 90도 회전을 하는 경우에는, 로봇의 한칸 위 좌표(가로)에 벽이 없으면 가능하다. 이 규칙을 알게되면 세로 방향일때도 회전하는 쪽의 좌표에 벽이 있는 지 확인한다면 쉽게 구현할 수 있다.

## 1차 시도 - 통과

```java
import java.util.LinkedList;
import java.util.Queue;

class Solution {

    static class Node {
        int x;
        int y;

        public Node(int x, int y) {
            this.x = x;
            this.y = y;
        }
    }

    static class Machine {
        Node first;
        Node second;
        int direction; // 가로 0, 세로 1
        int distance;

        public Machine(Node first, Node second, int direction, int distance) {
            this.first = first;
            this.second = second;
            this.direction = direction;
            this.distance = distance;
        }
    }

    static int N;
    static boolean[][][] visited;
    static int[][] arr;
    Queue<Machine> q;

    static int[] dx = {-1, 1, 0, 0};
    static int[] dy = {0, 0, -1, 1};

    public int solution(int[][] board) {
        N = board.length;
        arr = board;
        visited = new boolean[N][N][2];

        q = new LinkedList<>();
        q.offer(new Machine(new Node(0, 0), new Node(0, 1), 0, 0));

        while (!q.isEmpty()) {
            Machine poll = q.poll();
            Node first = poll.first;
            Node second = poll.second;

            int firstX = first.x;
            int firstY = first.y;
            int secondX = second.x;
            int secondY = second.y;
            int direction = poll.direction;
            int distance = poll.distance;

            // 이미 방문했다면 종료
            if (visited[firstX][firstY][direction] && visited[secondX][secondY][direction]) {
                continue;
            }
            // 방문 처리
            visited[firstX][firstY][direction] = true;
            visited[secondX][secondY][direction] = true;

            // 도착한 경우 최단거리 반환
            if (isArrived(first) || isArrived(second)) {
                return distance;
            }

            // 이동 탐색
            for (int i = 0; i < 4; i++) {
                int firstNx = firstX + dx[i];
                int firstNy = firstY + dy[i];
                int secondNx = secondX + dx[i];
                int secondNy = secondY + dy[i];

                // 이동이 불가능하면 종료
                if (isOutOfRange(firstNx, firstNy) || isOutOfRange(secondNx, secondNy)) {
                    continue;
                }

                // 두 Node 중 하나만 방문하지 않았어도 방문처리
                q.offer(new Machine(new Node(firstNx, firstNy), new Node(secondNx, secondNy), direction, distance + 1));
            }

            // 회전 탐색 시작
            // 방향이 가로일 때
            if (direction == 0) {
                // 위로 회전이 가능하다면
                if (!(isOutOfRange(firstX - 1, firstY) || isOutOfRange(secondX - 1, secondY))) {
                    // first 축으로 위로 회전
                    q.offer(new Machine(new Node(firstX, firstY), new Node(firstX - 1, firstY), 1, distance + 1));
                    // second 축으로 위로 회전
                    q.offer(new Machine(new Node(secondX, secondY), new Node(secondX - 1, secondY), 1, distance + 1));
                }
                // 아래로 회전이 가능하다면
                if (!(isOutOfRange(firstX + 1, firstY) || isOutOfRange(secondX + 1, secondY))) {
                    // first 축으로 아래로 회전
                    q.offer(new Machine(new Node(firstX, firstY), new Node(firstX + 1, firstY), 1, distance + 1));
                    // second 축으로 아래로 회전
                    q.offer(new Machine(new Node(secondX, secondY), new Node(secondX + 1, secondY), 1, distance + 1));
                }
            }
            // 방향이 세로일 때
            else {
                // 왼쪽으로 회전이 가능하다면
                if (!(isOutOfRange(firstX, firstY - 1) || isOutOfRange(secondX, secondY - 1))) {
                    // first 축으로 왼쪽 회전
                    q.offer(new Machine(new Node(firstX, firstY), new Node(firstX, firstY - 1), 0, distance + 1));
                    // second 축으로 왼쪽 회전
                    q.offer(new Machine(new Node(secondX, secondY), new Node(secondX, secondY - 1), 0, distance + 1));
                }

                // 오른쪽으로 회전이 가능하다면
                if (!(isOutOfRange(firstX, firstY + 1) || isOutOfRange(secondX, secondY + 1))) {
                    // first 축으로 오른쪽 회전
                    q.offer(new Machine(new Node(firstX, firstY), new Node(firstX, firstY + 1), 0, distance + 1));
                    // second 축으로 오른쪽 회전
                    q.offer(new Machine(new Node(secondX, secondY), new Node(secondX, secondY + 1), 0, distance + 1));
                }
            }
        }
        return -1;
    }

    public boolean isArrived(Node node) {
        int x = node.x;
        int y = node.y;

        return x == N - 1 && y == N - 1;
    }

    public boolean isOutOfRange(int x, int y) {
        return x < 0 || y < 0 || x > N - 1 || y > N - 1 || arr[x][y] == 1;
    }
}
```
