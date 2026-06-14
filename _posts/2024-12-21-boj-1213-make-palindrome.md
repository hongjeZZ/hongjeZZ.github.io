---
title: "[BOJ/Silver3] 1213번 팰린드롬 만들기 - JAVA[자바]"
date: 2024-12-21 21:38:37 +0900
categories: [PS, 백준]
tags: [구현, 그리디, 문자열]
---

**난이도** : 실버 4

**유형** : 문자열 / 그리디 / 구현

**링크**: <https://www.acmicpc.net/problem/1213>

![](/assets/img/boj-1213-make-palindrome/01.png)

![](/assets/img/boj-1213-make-palindrome/02.png)

## 문제 풀이

1. 문자열의 길이가 홀수인 경우
   1. 팰린드롬을 만들기 위해서는 개수가 **홀수인 알파벳이 정확히 하나**여야 함
   2. 개수가 홀수인 알파벳이 하나가 아닌 경우 *디폴트 메시지(“I’m Sorry Hansoo”)*를 출력
   3. 팰린드롬 구현
      1. 홀수인 알파벳을 제외하고 문자열을 사전순 정렬
      2. 문자열의 절반(인덱스 0부터 짝수 간격으로 선택한 문자)을 추출하여 **반쪽 문자열**을 생성.
      3. 2번에서 만든 문자열 + 홀수인 알파벳 + 2번에서 만든 문자열을 reverse한 문자열을 결합하여 팰린드롬 반환
2. 문자열의 길이가 짝수인 경우
   1. 팰린드롬을 만들기 위해서는 개수가 **홀수인 알파벳이 없어야 함**
   2. 개수가 홀수인 알파벳이 존재할 경우 *디폴트 메시지(“I’m Sorry Hansoo”)*를 출력
   3. 팰린드롬 구현
      1. 문자열을 사전순 정렬 후 문자열의 절반(인덱스 0부터 짝수 간격으로 선택한 문자)을 추출하여 **반쪽 문자열**을 생성
      2. 1번에서 만든 문자열 + 1번에서 만든 문자열을 reverse한 문자열을 결합하여 팰린드롬 반환

## 1차 시도 (통과)

```java
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder sb = new StringBuilder();

        String input = br.readLine();
        char[] charArray = input.toCharArray();

        // 사전순으로 정렬
        Arrays.sort(charArray);
        List<Character> list = new ArrayList<>();

        if (charArray.length % 2 == 0) {
            // 이름이 짝수일 때
            for (Character c : charArray) {
                // 리스트가 비어있거나, 원소가 포함되지 않았다면 add
                if (list.isEmpty() || !list.contains(c)) {
                    list.add(c);
                } else {
                    // 아니라면 이전 원소 remove
                    list.remove(c);
                }
            }
            // 리스트가 비어있지 않다면(팰린드롬을 만들지 못한다면), 디폴트 메시지 출력
            if (!list.isEmpty()) {
                System.out.println("I'm Sorry Hansoo");
            } else {
                // 반쪽짜리 문자열 생성
                for (int i = 0; i < charArray.length; i = i + 2) {
                    sb.append(charArray[i]);
                }
                System.out.println(sb.toString() + sb.reverse());
            }
        } else {
            // 이름이 홀수일 때
            for (Character c : charArray) {
                // 리스트가 비어있거나, 원소가 포함되어 있지 않다면 push
                if (list.isEmpty() || !list.contains(c)) {
                    list.add(c);
                } else {
                    // 아니라면 해당 원소를 remove
                    list.remove(c);
                }
            }

            // 리스트의 크기가 1이 아니라면(팰린드롬을 만들지 못한다면), 디폴트 메시지 출력
            if (list.size() != 1) {
                System.out.println("I'm Sorry Hansoo");
            } else {
                // 고아문자 삭제
                List<Character> charList = new String(charArray)
                        .chars()
                        .mapToObj(c -> (char) c).collect(Collectors.toList());
                charList.remove(list.get(0));

                for (int i = 0; i < charList.size(); i = i + 2) {
                    sb.append(charList.get(i));
                }
                System.out.println(sb.toString() + list.get(0) + sb.reverse());
            }
        }
    }
}
```

문제를 해결하기 위해 컬렉션을 사용했지만, 다른 사람들의 풀이를 보고나니 사실 문자의 개수만 추적하면 되는 문제였다. 배열을 활용했다면 메모리 사용과 성능 면에서 더 좋은 풀이였을 것 같다.

문자열이 짝수인지 홀수인지에 따라 분기를 나누는 방식도 가독성을 떨어뜨리고 복잡성을 증가시키는 문제가 있다.

길이와 상관없이 “홀수 개의 문자가 1개 이하”라는 조건만 만족하면 되므로, 하나의 공통 로직으로 처리하는 방식이 더욱 적합한 것 같다.

## 2차 시도 (통과)

```java
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder sb = new StringBuilder();
        String input = br.readLine();

        // 알파벳 배열 생성 & 개수 카운트
        int[] charCount = new int[26];
        for (char c : input.toCharArray()) {
            charCount[c - 'A']++;
        }

        char middleChar = 0;
        boolean hasOddMiddle = false;

        for (int i = 0; i < 26; i++) {
            if (charCount[i] % 2 != 0) {
                if (hasOddMiddle) {
                    // 홀수 문자가 두 개 이상이면 팰린드롬 불가능
                    System.out.println("I'm Sorry Hansoo");
                    return;
                }
                hasOddMiddle = true;
                middleChar = (char) (i + 'A');
            }

            // 반쪽짜리 문자열 생성
            for (int j = 0; j < charCount[i] / 2; j++) {
                sb.append((char) (i + 'A'));
            }
        }
        
        String palindrome = hasOddMiddle ? sb.toString() + middleChar + sb.reverse() : sb.toString() + sb.reverse();
        System.out.println(palindrome);
    }
}
```
