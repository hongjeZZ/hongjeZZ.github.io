---
title: 자주 사용하는 명령어 모음
date: 2024-08-22 23:20:52 +0900
categories: [기타]
tags: [TIL, cli, git]
---

### 깃 초기 설정

```shell
% git init // 깃 시작하기
% git config --global user.name {이름}       // 전역 이름 설정 
% git config --global user.email {깃이메일}   // 전역 이메일 설정

% git remote add {원격저장소별명} {깃주소}		// 깃 원격 저장소 연결
% git pull {원격저장소별명} {브랜치이름}			// 업데이트
% git push {원격저장소별명} {브랜치이름}			// 업로드

// 맥-윈도우 간 개행문자가 다름으로 인해 텍스트파일 깨지는거 잡아주는 명령어
% git config --global core.autocrlf true
```


### 깃 저장소 폴더로 내려받는 방법

```shell
% git clone {깃 주소}
```

### 업데이트

```shell
% git pull {원격저장소별명} {브랜치명}
```

### 업로드

```shell
% git add {파일명}   						// 경로에서 .을 입력하면 변경된 모든 파일
% git add -u            				// 수정되거나 삭제된 파일 반영
% git commit -m“커밋 메세지”
% git commit -a-m”커밋 메세지”             // 수정되거나 삭제된 파일만
% git push {원격저장소별명} {브랜치명}		// 원격 저장소에 업로드
% git push origin 브랜치명 -f				// 경고 무시하고 강제로 push하기
```

### 대용량 업로드

```shell
% brew install git-lfs         			// git-lfs 설치
% git las install                  		// 해당 디렉토리로 이동후
% git rm -r --cached        			// git add기록이 있다면 unstaging
% git las track “파일명”   				// 업로드하려는 파일 선택
% git add .gitattributes
```


### 언로드

```shell
% git reset HEAD [파일명]  				// git add 취소하기 
% git reset HEAD^               		// git commit 취소하기
% git commit --amend       				// git commit 메세지 변경
```

---
>수시로 추가할 예정
