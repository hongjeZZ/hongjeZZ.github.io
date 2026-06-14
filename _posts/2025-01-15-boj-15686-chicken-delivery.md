---
title: "[BOJ/Gold5] 15686번 치킨 배달 - JAVA[자바]"
date: 2025-01-15 18:57:37 +0900
categories: [PS, 백준]
tags: [구현, 백트래킹, 조합]
---

**난이도** : 골드 5

**유형 :** 조합 / 구현 / 백트래킹

**링크** : <https://www.acmicpc.net/problem/15686>

**구현 시간** : 30분

![](/assets/img/boj-15686-chicken-delivery/01.png)

![](/assets/img/boj-15686-chicken-delivery/02.png)

## 문제풀이

위 문제의 핵심은 M개의 치킨집의 조합에 따라 최소 치킨 거리는 달라진다. 이 말이 무슨 뜻이냐면 항상 작은 치킨 거리의 합을 가지는 경우를 선택하면 안되므로 그리디 알고리즘은 사용할 수 없다. 예를 들어 6개의 치킨집 중 하나의 치킨집을 폐업시킬 때는 6개의 치킨집을 순회하며 하나씩 치킨집을 삭제해보고 최소값을 찾으면 되지만, 이 후 5개의 치킨집 중 하나의 치킨집을 다시 폐업시킬 때는 이전의 선택에 영향을 받을 수 있다는 의미이다.

따라서 현 상황에서 가장 좋은 선택을 하는 그리디 알고리즘은 사용하지 못하고, N개의 치킨집중 M개의 치킨집을 만드는 조합을 전부 구현하여 최소값을 찾아야 한다.

문제의 핵심만 잘 이해할 수 있다면 백트래킹을 통해 조합을 구현하는 건 크게 어렵지 않으니 쉽게 풀 수 있다.

나는 2차원 배열을 사용하지 않고, 좌표 정보를 저장하는 Pos 클래스를 선언하여 ArrayList로 치킨 가게의 정보, 집의 정보를 저장하였다.

## 1차 시도 - 성공

```arduino
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.List;
import java.util.StringTokenizer;

public class Main {

    static int N;
    static int M;
    static int minValue = Integer.MAX_VALUE;

    static ArrayList<Pos> chickens = new ArrayList<>();
    static ArrayList<Pos> houses = new ArrayList<>();

    static class Pos {
        int x;
        int y;

        public Pos(int x, int y) {
            this.x = x;
            this.y = y;
        }
    }

    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringTokenizer st = new StringTokenizer(br.readLine());

        N = Integer.parseInt(st.nextToken());
        M = Integer.parseInt(st.nextToken());

        // 지도 저장
        for (int i = 0; i < N; i++) {
            st = new StringTokenizer(br.readLine());
            for (int j = 0; j < N; j++) {
                int input = Integer.parseInt(st.nextToken());
                if (input == 1) {
                    houses.add(new Pos(i, j));
                } else if (input == 2) {
                    chickens.add(new Pos(i, j));
                }
            }
        }
        combination(new ArrayList<>(), 0, 0);
        System.out.println(minValue);
    }

    public static void combination(List<Pos> selected, int start, int depth) {
        // 조합을 완성했다면, 최소 치킨 거리 저장
        if (depth == M) {
            minValue = Math.min(minValue, getChickenWay(selected));
            return;
        }

        // Back-Tracking 으로 조합을 구현한다.
        for (int i = start; i < chickens.size(); i++) {
            selected.add(chickens.get(i));
            combination(selected, i + 1, depth + 1);
            selected.remove(selected.size() - 1);
        }
    }

    // 집을 순회하며 치킨 거리의 최소합을 찾는다.
    public static int getChickenWay(List<Pos> selected) {
        int answer = 0;

        for (Pos house : houses) {
            int min = Integer.MAX_VALUE;

            for (Pos pos : selected) {
                min = Math.min(min, Math.abs(pos.x - house.x) + Math.abs(pos.y - house.y));
            }
            answer += min;
        }
        return answer;
    }
}
```
