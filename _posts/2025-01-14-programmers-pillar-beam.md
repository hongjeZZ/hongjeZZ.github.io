---
title: "[프로그래머스/Level3] 기둥과 보 설치 - JAVA[자바]"
date: 2025-01-14 21:48:26 +0900
categories: [PS, 프로그래머스]
tags: [구현, 시뮬레이션]
---

**난이도** : Level 3

**유형** :구현 / 시뮬레이션

**구현 시간** : 2시간 (못품)

**링크** : <https://school.programmers.co.kr/learn/courses/30/lessons/60061>

[🔗 프로그래머스 SW개발자를 위한 평가, 교육, 채용까지 Total Solution을 제공하는 개발자 성장을 위한 베이스캠프 programmers.co.kr](https://school.programmers.co.kr/learn/courses/30/lessons/60061)

![](/assets/img/programmers-pillar-beam/01.png)

![](/assets/img/programmers-pillar-beam/02.png)

![](/assets/img/programmers-pillar-beam/03.png)

![](/assets/img/programmers-pillar-beam/04.png)

## 문제풀이

위 문제는 많은 조건을 생각해야하는 빡구현 문제다. 주어진 좌표에 기둥과 보를 설치하는 구현은 정말 쉽지만, 기둥과 보를 삭제할 때 고려해야할 경우의 수는 매우 많다. 해당 경우의 수에 대해서 설명해보겠다. 나는 처음 구현할 때, 설치, 삭제 모두 전부 경우의 수를 고려해서 코드를 구현했는데 복잡한만큼 실수가 많아서 실패했다.

포기 후 다른 사람의 코드를 보니, 설치는 경우의 수를 생각하며 구현하지만 삭제의 경우 미리 삭제를 해본 후, 해당 건축물에 영향을 받을 보 혹은 기둥의 설치 조건을 다시 확인해보며 삭제 조건을 찾는 생각보다 간단한 방법으로 구현을 했다.

우선 설치 조건과 삭제 조건을 살펴보자

1. 기둥 설치 조건 (4가지)
   1. 좌표가 바닥인 경우
   2. 좌표 아래 기둥이 있는 경우
   3. 좌표 옆 보가 있는 경우
   4. 좌표에 보가 있는 경우
2. 보 설치 조건 (3가지)
   1. 좌표 아래 기둥이 있는 경우
   2. 좌표 우측 아래 기둥이 있는 경우
   3. 좌우에 보가 있는 경우
3. 기둥 삭제 불가 조건 (3가지)
   1. 좌표 위 기둥이 있는 경우
      1. 현재 기둥을 삭제해보고 좌표 위 기둥을 설치하려고 할 때, 설치가 안되는 경우
   2. 좌표 위 보가 있는 경우
      1. 현재 기둥을 삭제해보고 좌표 위 보를 설치하려고 할 때, 설치가 안되는 경우
   3. 좌표 좌측 위 보가 있는 경우
      1. 현재 기둥을 삭제해보고 좌표 좌측 위 보를 설치하려고 할 때, 설치가 안되는 경우
4. 보 삭제 불가 조건 (4가지)
   1. 좌표에 기둥이 있는 경우
      1. 보를 삭제해보고 기둥을 설치하려고 할 때, 설치가 안되는 경우
   2. 좌표 우측에 기둥이 있는 경우
      1. 보를 삭제해보고 좌표 우측 기둥을 설치하려고 할 때, 설치가 안되는 경우
   3. 좌표 우측에 보가 있는 경우
      1. 보를 삭제해보고 좌표 오측 보를 설치하려고 할 때, 설치가 안되는 경우
   4. 좌표 좌측에 보가 있는 경우
      1. 보를 삭제해보고 좌표 좌측 보를 설치하려고 할 때, 설치가 안되는 경우

이제 위 경우를 모두 구현하면 쉽게 정답을 찾을 수 있다. 출력 조건에 정렬이 있었기 때문에 Comparable 인터페이스를 구현한 객체를 생성해서 정답을 출력하였다.

## 정답 코드

```java
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

class Solution {

    int n;
    boolean[][] wall;
    boolean[][] floor;

    static class Block implements Comparable<Block> {
        int x;
        int y;
        int type;

        public Block(int x, int y, int type) {
            this.x = x;
            this.y = y;
            this.type = type;
        }

        @Override
        public int compareTo(Block o) {
            if (x != o.x) {
                return x - o.x;
            } else if (y != o.y) {
                return y - o.y;
            } else {
                return type - o.type;
            }
        }

        @Override
        public String toString() {
            return "[" + x + "," + y + "," + type + "]";
        }

    }

    public boolean canBuildWall(int bx, int by) {
        return  (by == 0)                               // 바닥에 설치
                || (by - 1 >= 0 && wall[bx][by - 1])    // 아래에 기둥이 있는 경우
                || (bx - 1 >= 0 && floor[bx - 1][by])   // 왼쪽에 보가 있는 경우
                || floor[bx][by];           // 오른쪽에 보가 있는 경우
    }

    public boolean canBuildFloor(int bx, int by) {
        return  (by - 1 >= 0 && wall[bx][by - 1])          // 아래에 기둥이 있는 경우
                || (bx + 1 <= n && by - 1 >= 0 && wall[bx + 1][by - 1]) // 우측 아래에 기둥이 있는 경우
                || (bx - 1 >= 0 && bx + 1 <= n && floor[bx - 1][by] && floor[bx + 1][by]); // 좌우에 보가 있는 경우
    }

    public int[][] solution(int n, int[][] build_frame) {
        this.n = n;
        wall = new boolean[n + 1][n + 1];
        floor = new boolean[n + 1][n + 1];
        List<Block> blocks = new ArrayList<>();

        for (int[] frame : build_frame) {
            int bx = frame[0];
            int by = frame[1];
            int type = frame[2];
            int command = frame[3];

            // 특정 좌표에 기둥을 건설하는 경우
            if (type == 0 && command == 1) {
                // 기둥 설치 조건
                if (canBuildWall(bx, by)) {
                    blocks.add(new Block(bx, by, type));
                    wall[bx][by] = true;
                }
            }

            // 특정 좌표에 보를 건설하는 경우
            if (type == 1 && command == 1) {
                // 조건 만족 시 보 설치
                if (canBuildFloor(bx, by)) {
                    blocks.add(new Block(bx, by, type));
                    floor[bx][by] = true;
                }
            }

            // 특정 좌표에 기둥을 삭제하는 경우
            if (type == 0 && command == 0) {
                wall[bx][by] = false;

                // 좌표 위 기둥이 있는 경우
                if (by + 1 <= n && wall[bx][by + 1]) {
                    if (!canBuildWall(bx, by + 1)) {
                        wall[bx][by] = true;
                        continue;
                    }
                }
                // 기둥 위 보가 있는 경우
                if (by + 1 <= n && floor[bx][by + 1]) {
                    if (!canBuildFloor(bx, by + 1)) {
                        wall[bx][by] = true;
                        continue;
                    }
                }
                // 기둥 좌측 위 보가 있는 경우
                if (by + 1 <= n && bx - 1 >= 0 && floor[bx - 1][by + 1]) {
                    if (!canBuildFloor(bx - 1, by + 1)) {
                        wall[bx][by] = true;
                        continue;
                    }
                }
                blocks.removeIf(block -> block.x == bx && block.y == by && block.type == 0);
            }

            // 특정 좌표에 보를 삭제하는 경우
            if (type == 1 && command == 0) {
                floor[bx][by] = false;

                // 좌표에 기둥이 있는 경우
                if (wall[bx][by]) {
                    if (!canBuildWall(bx, by)) {
                        floor[bx][by] = true;
                        continue;
                    }
                }

                // 좌표 우측에 기둥이 있는 경우
                if (bx + 1 <= n && wall[bx + 1][by]) {
                    if (!canBuildWall(bx + 1, by)) {
                        floor[bx][by] = true;
                        continue;
                    }
                }

                // 좌표 우측에 보가 있는 경우
                if (bx + 1 <= n && floor[bx + 1][by]) {
                    if (!canBuildFloor(bx + 1, by)) {
                        floor[bx][by] = true;
                        continue;
                    }
                }

                // 좌표 좌측에 보가 있는 경우
                if (bx - 1 >= 0 && floor[bx - 1][by]) {
                    if (!canBuildFloor(bx - 1, by)) {
                        floor[bx][by] = true;
                        continue;
                    }
                }
                blocks.removeIf(block -> block.x == bx && block.y == by && block.type == 1);
            }
        }
        Collections.sort(blocks);

        int[][] answer = new int[blocks.size()][3];
        for (int i = 0; i < blocks.size(); i++) {
            Block block = blocks.get(i);
            answer[i][0] = block.x;
            answer[i][1] = block.y;
            answer[i][2] = block.type;
        }
        return answer;
    }
}
```
