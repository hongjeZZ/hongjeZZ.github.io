---
title: "[BOJ/Silver3] 1966번 프린터 큐 - JAVA[자바]"
date: 2024-12-23 15:23:51 +0900
categories: [PS, 백준]
tags: [구현, 시뮬레이션]
---

**난이도** : 실버 3

**유형** : 구현 / 시뮬레이션

**링크** : [백준 1966번 - 프린터 큐](https://www.acmicpc.net/problem/1966)

![](/assets/img/boj-1966-printer-queue/01.png)

![](/assets/img/boj-1966-printer-queue/02.png)

## 문제풀이

1. 문서 출력 인덱스, 우선순위를 저장할 PrintJob 클래스 구현
2. 우선순위 비교 (현재 PrintJob 보다 높은 우선순위가 있는지 확인)
3. 2번에서 현재 PrintJob 보다 높은 우선순위가 있다면
   1. 현재 문서를 다시 큐의 맨 뒤로 삽입
4. 현재 PrintJob 의 우선순위가 제일 높다면
   1. 출력 순서 +1
   2. 출력된 문서의 idx 가 M이라면 반복문 탈출 후 출력

## 1차 시도 - 통과

```java
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.LinkedList;
import java.util.Queue;

public class Main {
    static class PrintJob {
        int idx;
        int priority;

        PrintJob(int idx, int priority) {
            this.idx = idx;
            this.priority = priority;
        }
    }

    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));

        int T = Integer.parseInt(br.readLine());

        for (int i = 0; i < T; i++) {
            String[] inputs = br.readLine().split(" ");
            int N = Integer.parseInt(inputs[0]);
            int M = Integer.parseInt(inputs[1]);

            Queue<PrintJob> queue = new LinkedList<>();

            String[] values = br.readLine().split(" ");
            for (int j = 0; j < N; j++) {
                queue.add(new PrintJob(j, Integer.parseInt(values[j])));
            }

            int printOrder = 0;

            while (!queue.isEmpty()) {
                PrintJob currentJob = queue.poll();
                boolean hasHigherPriority = true;

                for (PrintJob job : queue) {
                    if (job.priority > currentJob.priority) {
                        hasHigherPriority = false;
                        break;
                    }
                }

                if (hasHigherPriority) {
                    printOrder++;
                    if (currentJob.idx == M) {
                        break;
                    }
                } else {
                    queue.add(currentJob);
                }
            }
            System.out.println(printOrder);
        }
    }
}
```
