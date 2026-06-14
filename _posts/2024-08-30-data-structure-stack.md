---
title: 스택(Stack) 정리
date: 2024-08-30 14:26:02 +0900
categories: [CS, 자료구조]
tags: [스택, 자료구조, 코딩테스트]
---

### 스택(Stack) 이란?

스택(Stack)은 자료를 순서대로 쌓아 올릴 수 있는 자료구조로, Stack 이라는 단어의 어원은 "쌓다"라는 의미에서 유래했다. 이 자료구조의 핵심은 **선입후출(FILO: First In, Last Out)**이라는 규칙에 있다. 즉, 먼저 들어간 데이터가 마지막에 나오는 구조다.

<br>

### 스택의 동작 원리

스택은 일종의 리스트와 비슷한데, 데이터를 추가하거나 제거하는 방식이 제한적이다. 오직 한쪽 끝(보통 'top'이라고 불린다)에서만 데이터를 추가(push)하거나 제거(pop)할 수 있다. 

스택을 쉽게 이해하려면 책 더미를 떠올리면 된다. 책을 쌓을 때 맨 위에 올린 책이 맨 먼저 제거된다. 이와 같은 원리로 스택이 동작한다.

![Stack ADT](/assets/img/data-structure-stack/01.png)


<br>

### 스택의 주요 연산

스택에서 제공하는 주요 연산은 다음과 같다:

1. **`push(ItemType item)`**: 데이터를 스택에 추가한다.
2. **`pop()`**: 스택에서 가장 최근에 추가된 데이터를 제거하고 반환한다.
3. **`isFull()`**: 스택이 가득 찼는지 확인한다. 자바의 `Stack` 클래스에는 이 메서드가 없지만, 특정 구현에서는 유용하다.
4. **`isEmpty()`**: 스택이 비어 있는지 확인한다.
5. **`top`**: 현재 스택에서 가장 최근에 추가된 데이터의 위치를 나타낸다.
6. **`data[maxsize]`**: 스택의 데이터를 관리하는 배열로, 최대 `maxsize` 개의 데이터를 관리한다.

#### `push(ItemType item)` 동작 원리

스택에 데이터를 추가할 때는 다음과 같은 절차를 따른다:

1. 먼저 `isFull()` 연산을 수행하여 스택이 가득 찼는지 확인한다.
2. 가득 차지 않았다면, `top`의 값을 1 증가시킨다.
3. `top`이 가리키는 위치에 새로운 데이터를 추가한다.

#### `pop()` 동작 원리

스택에서 데이터를 제거할 때는 다음과 같은 절차를 따른다:

1. 먼저 `isEmpty()` 연산을 호출하여 스택이 비어 있는지 확인한다.
2. 데이터가 있다면 `top`의 값을 1 감소시킨다.
3. `top`이 가리키는 위치에 있는 데이터를 반환한다.

<br>

### 자바에서 스택 클래스 사용하기


```java
Stack<Integer> stack = new Stack<>();   // 스택 객체 생성 (java.util.Stack)

stack.push(1);                          // 스택에 데이터 {1} 푸시
stack.push(2);                          // 스택에 데이터 {2} 푸시

System.out.println(stack.isEmpty());    // 스택이 비어 있는지 확인 => false

Integer pop = stack.pop();              // pop => 2
pop = stack.pop();                      // pop => 1
```
자바에서는 `java.util.Stack` 클래스를 사용해 쉽게 스택을 구현할 수 있다. 자바의 스택 클래스는 크기를 동적으로 관리하므로 `maxsize`나 `isFull()` 메서드가 필요 없다. 대신, `size()` 메서드를 통해 현재 스택에 들어 있는 데이터 수를 확인할 수 있으며, `peek()` 메서드를 통해 가장 최근에 추가된 데이터를 제거하지 않고도 확인할 수 있다.

<br>


```java
Stack<Integer> stack = new Stack<>();
stack.push(5);
stack.push(6);

Integer peek = stack.peek();        // 최근에 푸시한 값(peek) => 6
Integer pop = stack.pop();          // pop => 6

int size = stack.size();            // size => 1
```
추가적으로, `peek()` 메서드를 사용하면 데이터가 제거되지 않은 상태에서 최상위 데이터를 확인할 수 있다.

<br>


이처럼 스택은 간단하지만, 강력한 자료구조로, 재귀적 알고리즘, 수식의 괄호 검사, 깊이 우선 탐색(DFS) 등 다양한 곳에서 사용된다.

스택의 개념을 이해하고 이를 활용하는 법을 익히면, 여러 가지 문제를 보다 효율적으로 해결할 수 있다.

---
### reference
[Stack Operations in Data Structures](https://www.scaler.com/topics/stack-operations-in-data-structures/)
