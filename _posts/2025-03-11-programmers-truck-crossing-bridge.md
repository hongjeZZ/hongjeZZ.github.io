---
title: "[프로그래머스/Level2] 다리를 지나는 트럭 - JAVA[자바]"
date: 2025-03-11 15:31:13 +0900
categories: [PS, 프로그래머스]
tags: [구현, 시뮬레이션, 큐]
---

**난이도** : Level 2

**유형**: 큐 / 구현 / 시뮬레이션

**구현 시간** : 30분

**링크**: <https://school.programmers.co.kr/learn/courses/30/lessons/42583>

[🔗 프로그래머스 SW개발자를 위한 평가, 교육, 채용까지 Total Solution을 제공하는 개발자 성장을 위한 베이스캠프 programmers.co.kr](https://school.programmers.co.kr/learn/courses/30/lessons/42583)

![](/assets/img/programmers-truck-crossing-bridge/01.png)

## 문제 풀이

우선 해당 문제는 문제에 대한 설명이 부족하다.

예제를 보면 추측이 가능한데 아래 2가지 조건을 추가해야 한다.

1. 트럭은 1초에 1씩 전진한다.
2. 트럭은 1초에 1대씩 다리에 올라갈 수 있다.

1. Queue 자료구조를 사용해서 다리 위 트럭 객체를 관리

2. currentWeight, idx, time 변수를 통해 현재 다리 위 무게, 시간, 대기 트럭의 인덱스를 관리

```java
while (idx < truck_weights.length || !bridge.isEmpty()) {
    time++; // 1초 경과
```

모든 트럭이 다리 위에 올라가고, 다리 위 모든 트럭이 건넜을 경우 반복문을 종료한다.

```java
if (!bridge.isEmpty() && bridge.peek()[1] == time) {
    currentWeight -= bridge.poll()[0]; // 다리를 지난 트럭 제거
}
```

트럭이 다리를 지나갔는지 시간을 통해 확인하고, 다리를 다 지나갔다면 즉시 무게를 차감해준다.

```java
if (idx < truck_weights.length) {
    if (currentWeight + truck_weights[idx] <= weight && bridge.size() < bridge_length) {
        bridge.add(new int[]{truck_weights[idx], time + bridge_length}); // 트럭 추가
        currentWeight += truck_weights[idx];
        idx++;
    }
}
```

무게 제한을 초과하지 않는 경우에만 다리에 트럭을 추가한다.

다리에 트럭을 추가할 때, 다리의 길이만큼 현재 시간을 더해준 이유는 **다리를 건너는 시간은 다리의 길이만큼 걸리기 때문**

또한 다리의 길이만큼 트럭을 올릴 수 있기 때문에 해당 조건도 추가한다.

## 문제 풀이 - 통과

```java
// 트럭은 1초에 1씩 전진한다.
// 트럭은 1초에 1대씩 다리에 올라갈 수 있다.
// 트럭은 순서대로 다리에 올라가야 한다.

import java.util.*;

class Solution {
    public int solution(int bridge_length, int weight, int[] truck_weights) {
        Queue<int[]> bridge = new LinkedList<>();
        int currentWeight = 0;
        int time = 0;
        int idx = 0;
        
         while (idx < truck_weights.length || !bridge.isEmpty()) {
            time++;

            // 다리에서 나갈 트럭 확인
            if (!bridge.isEmpty() && bridge.peek()[1] == time) {
                currentWeight -= bridge.poll()[0];
            }
            
            // 트럭 추가
            if (idx < truck_weights.length) {
                if (truck_weights[idx] + currentWeight <= weight && bridge.size() < bridge_length) {
                    bridge.add(new int[]{truck_weights[idx], time + bridge_length});
                    currentWeight += truck_weights[idx];
                    idx++;
                }
            }
        }
        
        return time;
    }
}
```
