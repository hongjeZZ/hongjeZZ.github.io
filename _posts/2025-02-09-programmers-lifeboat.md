---
title: "[프로그래머스/Level2] 구명 보트 - JAVA[자바]"
date: 2025-02-09 17:47:33 +0900
categories: [PS, 프로그래머스]
tags: [그리디, 이진탐색, 투 포인터]
---

**난이도** : Level 2

**유형**: 그리디 / 투 포인터

**구현 시간** : 1시간 (못 품)

**링크**: <https://school.programmers.co.kr/learn/courses/30/lessons/42885>

[🔗 프로그래머스 SW개발자를 위한 평가, 교육, 채용까지 Total Solution을 제공하는 개발자 성장을 위한 베이스캠프 programmers.co.kr](https://school.programmers.co.kr/learn/courses/30/lessons/42885)

![](/assets/img/programmers-lifeboat/01.png)

## 문제풀이

이 문제는 **그리디 알고리즘** 유형으로, 최소한의 구명보트 개수로 모든 사람을 태우는 문제이다.

처음에는 A라는 사람의 무게가 주어지면 남은 사람들 중 구명보트의 무게 제한을 넘지 않는 최대값이 되는 B라는 사람을 찾아 최소한의 보트를 사용하려 했다. 만약 무게 제한을 넘지 않는 B가 없다면 A만 보트에 태우는 방식으로 접근했다.

이 접근 방식은 정확성 테스트는 통과했지만, 효율성 테스트에서 시간 초과가 발생했다. 리스트에서 최대값을 찾기 위해 한 번 더 전체 탐색을 수행해야 하므로 시간 복잡도가 **O(N²)**로 증가했기 때문이다. 이후 정렬과 이진 탐색을 활용하여 최적화하려 했지만, 효율성 테스트를 통과하지 못했다.

다른 풀이를 참고한 후, 투 포인터 기법을 활용하는 방법을 알게 되었다. 투 포인터 기법은 정렬된 배열에서 두 개의 포인터를 이용해 탐색하는 방식으로, **O(N)**의 시간 복잡도를 가지므로 매우 빠른 탐색이 가능하다.

이 방법을 적용하기 위해 먼저 people 배열을 오름차순으로 정렬한 후, 가장 가벼운 사람을 가리키는 left 포인터와 가장 무거운 사람을 가리키는 right 포인터를 선언했다. 이후 두 사람이 함께 탈 수 있다면 두 포인터를 동시에 이동시키고, 그렇지 않다면 무거운 사람만 태운 후 right 포인터를 이동시키는 방식으로 최소한의 보트 개수를 구할 수 있었다.

> 정답 코드가 궁금하신 분들은 3차 시도만 봐주시면 됩니다!

## 1차시도 - 실패

```java
import java.util.ArrayList;
import java.util.List;

class Solution {
    public int solution(int[] people, int limit) {
        List<Integer> list = new ArrayList<>();
        for (int person : people) {
            list.add(person);
        }

        int cnt = 0;
        
        while (!list.isEmpty()) {
            Integer get = list.get(0);
            list.remove(get);
            cnt++;
            
            int res = limit - get;
            if (res < 40) {
                continue;
            }

            Integer removeTarget = -1;
            for (Integer next : list) {
                if (res >= next) {
                    removeTarget = Math.max(removeTarget, next);
                }
            }
            
            if (removeTarget != -1) {
                list.remove(removeTarget);
            }
        }
        
        return cnt;
    }
}
```

## 2차 시도 - 실패 (이진탐색 사용)

```java
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

class Solution {
    public int solution(int[] people, int limit) {
        List<Integer> list = new ArrayList<>();
        for (int person : people) {
            list.add(person);
        }

        Collections.sort(list);

        int cnt = 0;

        while (!list.isEmpty()) {
            Integer get = list.get(0);
            list.remove(0);
            cnt++;

            int res = limit - get;
            if (res < 40) {
                continue;
            }

            int left = 0, right = list.size() - 1, bestFit = -1;
            while (left <= right) {
                int mid = (left + right) / 2;
                if (list.get(mid) <= res) {
                    bestFit = mid;
                    left = mid + 1;
                } else {
                    right = mid - 1;
                }
            }

            if (bestFit != -1) {
                list.remove(bestFit);
            }
        }

        return cnt;
    }
}
```

## 3차시도 - 성공 (투 포인터 사용)

```java
import java.util.Arrays;

class Solution {
    public int solution(int[] people, int limit) {
        Arrays.sort(people);

        int left = 0;
        int right = people.length - 1;
        int cnt = 0;

        while (left <= right) {
            if (limit >= people[left] + people[right]) {
                left++;
            }
            right--;
            cnt++;
        }
        return cnt;
    }
}
```
