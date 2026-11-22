---
title: "TIL - chroot, namespace, cgroup"
date: 2026-11-22 13:22:00 +0900
categories: [Infra, Kubernetes]
tags: [TIL, Kubernetes, 운영체제, namespace, cgroup]
---

{% raw %}

> [!NOTE]
>
> ※ 본 게시물은 AI(인공지능)를 활용하여 작성된 콘텐츠입니다.<br>
> ※ This post was created with the help of AI.

컨테이너는 VM처럼 별도의 커널을 띄우지 않습니다. 호스트 Linux 커널 위에서 도는 일반 프로세스이고, 커널 기능 몇 가지로 다른 프로세스와 분리해 둔 것입니다.<br>
그 기능이 chroot, namespace, cgroup이며, 셋은 제한하는 대상이 서로 다릅니다.

| 기술 | 제한하는 대상 | 도입 시기 |
|---|---|---|
| chroot | 파일시스템의 루트(`/`) 위치 | 1979년 Version 7 Unix |
| namespace | 프로세스가 볼 수 있는 시스템 자원의 범위 | 2002년 Linux 2.4.19(mount)부터 종류별로 추가 |
| cgroup | 프로세스가 쓸 수 있는 CPU·메모리 등의 양 | 2008년 Linux 2.6.24 |

<br>

## chroot

chroot는 프로세스와 그 자식 프로세스의 루트 디렉터리를 바꾸는 system call(같은 이름의 명령도 있음)입니다.<br>
`chroot /srv/myroot /bin/sh`로 셸을 띄우면 그 셸에서 `/`는 호스트의 `/srv/myroot`를 가리키고, 그 바깥 경로는 보이지 않습니다.<br>
컨테이너 이미지가 `/bin`, `/etc`, `/usr`를 모두 갖춘 디렉터리 트리 형태인 것도 이 구조에서 비롯됐습니다.

chroot가 격리하는 것은 파일 경로뿐입니다. 프로세스 목록, 네트워크, 사용자 계정은 호스트와 그대로 공유합니다.<br>
게다가 chroot 안에서 root 권한을 가진 프로세스는 chroot를 한 번 더 호출하는 방법 등으로 바깥에 빠져나갈 수 있습니다. man page도 chroot를 보안 목적으로 쓰지 말라고 명시합니다.

그래서 runc 같은 컨테이너 런타임은 chroot 대신, 새로 만든 mount namespace 안에서 `pivot_root`를 호출합니다.<br>
`pivot_root`는 루트 마운트 자체를 이미지 디렉터리로 바꾸고 이전 루트를 마운트 해제하기 때문에, 원래 루트로 돌아갈 경로가 남지 않습니다.

<br>

## namespace

namespace는 커널 자원을 프로세스 그룹별로 나누어, 각 그룹이 자기 몫만 보게 합니다. 종류마다 나누는 자원이 다릅니다.

| namespace | 나누는 자원 |
|---|---|
| mount | 마운트 지점(파일시스템 트리) |
| PID | 프로세스 ID 번호 공간 |
| network | 네트워크 인터페이스, IP, 라우팅 테이블, 포트 |
| UTS | hostname |
| IPC | System V IPC, POSIX 메시지 큐 |
| user | UID/GID 매핑 (컨테이너 안의 root를 호스트의 일반 사용자에 대응) |
| cgroup | 프로세스가 보는 cgroup 계층의 루트 |
| time | 부팅 시각 기준 시계의 오프셋 (Linux 5.6) |

두 가지 예를 들어 보겠습니다.

- 새 PID namespace에서 시작한 프로세스는 자신을 PID 1로 보고, `ps`로는 같은 namespace 안의 프로세스만 보입니다.<br>
  같은 프로세스를 호스트에서 보면 12345 같은 평범한 PID를 가집니다.
- 새 network namespace는 loopback 인터페이스 하나만 가진 채 시작합니다.<br>
  그래서 런타임이나 CNI 플러그인이 veth 쌍을 만들어 호스트와 연결해 줘야 통신할 수 있습니다.

namespace는 보이는 범위만 나눕니다.<br>
어떤 컨테이너가 호스트 메모리를 전부 써 버리는 것은 막지 못하며, 그 역할은 cgroup이 맡습니다.

<br>

## cgroup

cgroup(control group)은 프로세스를 계층 구조의 그룹으로 묶고, 그룹 단위로 CPU, 메모리, 디스크 I/O, 프로세스 수 등의 사용량을 제한하고 측정합니다.<br>
인터페이스는 `/sys/fs/cgroup` 아래의 파일시스템입니다. 그룹 하나가 디렉터리 하나이고, 그 안의 `memory.max`나 `cpu.max` 같은 파일에 값을 쓰면 제한이 걸립니다.

한도를 넘었을 때의 동작은 자원마다 다릅니다.

- **메모리**: 회수하지 않으면 더 줄 수 없는 자원입니다. 한도를 넘으면 커널의 OOM killer가 그 cgroup 안의 프로세스를 종료합니다.
- **CPU**: 시간을 나눠 쓰는 자원입니다. 한도를 넘은 프로세스는 종료되지 않고, 다음 주기가 올 때까지 실행이 미뤄집니다(throttling).

현재 주로 쓰이는 버전은 Linux 4.5에서 들어온 cgroup v2입니다. 자원마다 계층이 따로 있던 v1과 달리 계층이 하나로 통합됐습니다.<br>
Fedora 31, Debian 11, Ubuntu 21.10, RHEL 9 이후 배포판은 기본값이 v2입니다.

<br>

## 쿠버네티스와의 관계

컨테이너 하나를 띄우는 요청은 kubelet → containerd → runc 순으로 전달됩니다.<br>
마지막 단계에서 runc가 namespace를 만들고, cgroup을 설정하고, `pivot_root`를 호출한 뒤 컨테이너 프로세스를 실행합니다.<br>
쿠버네티스 개념 중 일부는 이 기능에 그대로 대응합니다.

<br>

### Pod

- 한 Pod 안의 컨테이너들은 network namespace와 IPC namespace를 공유합니다. 그래서 같은 IP를 쓰고 `localhost`로 서로 접속할 수 있습니다.
- 공유되는 namespace는 pause 컨테이너(sandbox)가 먼저 만들어 유지하고, 앱 컨테이너는 거기에 합류합니다.
- mount namespace는 컨테이너마다 따로 있어서 파일시스템은 분리됩니다. 파일을 공유하려면 volume을 씁니다.

<br>

### resources

- `limits.memory`는 cgroup의 `memory.max` 값으로, `limits.cpu`는 `cpu.max` 값으로 설정됩니다.<br>
  메모리 한도를 넘은 컨테이너는 `OOMKilled`로 재시작되고, CPU 한도에 걸린 컨테이너는 죽지 않고 느려지기만 합니다.<br>
  앞에서 본 cgroup의 동작 차이가 그대로 나타나는 것입니다.
- `requests`는 주로 스케줄러가 노드를 고르는 기준입니다.<br>
  CPU requests는 `cpu.weight`로도 설정되어, CPU를 놓고 경합할 때 나눠 갖는 비율이 됩니다.

모든 컨테이너가 호스트 커널을 공유한다는 점이 VM과 가장 크게 다릅니다.<br>
같은 노드의 Pod는 모두 노드의 커널 하나 위에서 돌기 때문에, 커널 취약점이 있으면 그 노드의 모든 컨테이너가 영향을 받을 수 있습니다.

<br>

## 노드에서 직접 확인하기

kubeadm으로 구성한 노드에 root로 접속해 실행합니다.

```bash
lsns -t net                   # network namespace 목록. Pod마다 하나씩 있다
PID=$(pgrep -o coredns)       # CoreDNS 컨테이너 프로세스의 호스트 쪽 PID
ls -l /proc/$PID/ns           # CoreDNS가 속한 namespace
ls -l /proc/1/ns              # 호스트 systemd의 namespace. 번호가 다르면 다른 namespace다
cat /proc/$PID/cgroup         # CoreDNS가 속한 cgroup 경로
cat /sys/fs/cgroup$(cut -d: -f3 /proc/$PID/cgroup)/memory.max
```

kubeadm 기본 설정에서 CoreDNS의 `limits.memory`는 170Mi입니다. 그래서 마지막 명령은 170Mi를 바이트로 바꾼 `178257920`을 출력합니다.<br>
Pod spec에 적은 값이 cgroup 파일에 그대로 들어간 것을 확인할 수 있습니다.

<br>

## 참고 자료

- [chroot(2)](https://man7.org/linux/man-pages/man2/chroot.2.html)
- [pivot_root(2)](https://man7.org/linux/man-pages/man2/pivot_root.2.html)
- [namespaces(7)](https://man7.org/linux/man-pages/man7/namespaces.7.html)
- [cgroups(7)](https://man7.org/linux/man-pages/man7/cgroups.7.html)
- [Control Group v2 (Linux kernel 문서)](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [Kubernetes, About cgroup v2](https://kubernetes.io/docs/concepts/architecture/cgroups/)
- [Kubernetes, Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)

{% endraw %}
