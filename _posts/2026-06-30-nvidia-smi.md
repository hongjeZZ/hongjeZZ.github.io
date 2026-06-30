---
title: "nvidia-smi의 GPU-Util은 'GPU 점유율'이 아니다"
date: 2026-06-30 16:16:14 +0900
categories: [Infra, GPU]
tags: [TIL, nvidia-smi, GPU, NVIDIA, 모니터링, NVML]
source_wiki: nvidia-smi
provenance: cite-only
---

GPU가 잘 돌고 있나 확인할 때 습관처럼 `nvidia-smi`를 치고 **GPU-Util** 숫자를 봅니다. 저는 이 값을 "GPU 연산을 몇 % 쓰고 있나"로 읽고 있었는데, [NVIDIA 문서](https://docs.nvidia.com/deploy/nvidia-smi/)와 관련 분석을 보니 그게 아니었습니다. GPU-Util은 *점유율*이 아니라 *시간* 지표였습니다. 오해를 풀고 GPU 사용률을 제대로 읽는 법을 짧게 정리한 TIL입니다.

## nvidia-smi가 보여주는 것

`nvidia-smi`(NVIDIA System Management Interface)는 NVIDIA GPU를 모니터링·관리하는 CLI입니다. NVML(NVIDIA Management Library)이라는 C API를 감싼 얇은 래퍼라, 화면에 찍히는 값은 전부 NVML이 노출하는 상태입니다. 드라이버에 같이 깔리므로 따로 설치할 게 없습니다.

기본 출력에서 자주 헷갈리는 필드 하나만 먼저 짚으면, 헤더의 **CUDA Version**은 *드라이버가 지원하는 최대 CUDA 버전*이지 설치된 CUDA toolkit 버전이 아닙니다. "CUDA Version: 12.4"는 12.4 이하 앱을 돌릴 수 있다는 뜻일 뿐, toolkit 12.4가 깔렸다는 의미가 아닙니다.

## GPU-Util은 "시간"이지 "공간"이 아니다

NVML이 정의하는 GPU-Util은 이렇습니다.

> 지난 샘플 주기 동안 **하나 이상의 커널이 실행되고 있던 시간**의 비율. (샘플 주기는 제품에 따라 약 1초~1/6초)

핵심은 *하나 이상의 커널이 실행 중*이기만 하면 카운트된다는 점입니다. GPU를 얼마나 채웠는지가 아니라, 뭐라도 돌고 있었는지를 시간으로 잰 값입니다. 그래서 직관과 어긋나는 일이 생깁니다.

- **스레드 하나짜리 커널**(`kernel<<<1,1>>>`)이 쉬지 않고 돌아도 GPU-Util은 **100%**가 됩니다. 한 분석에서는 단일 스레드 커널이 GPU-Util 100%를 찍는 동안 실제 **SM 점유율은 20% 미만**이었습니다. GPU의 연산 유닛(SM)이 대부분 놀고 있어도 "커널이 돌고 있으니" 100%입니다.
- **메모리를 기다리며 멈춰 있는 커널**도 "실행 중"으로 세므로, 연산 유닛은 노는 메모리 대역폭 바운드 작업도 100%를 보일 수 있습니다.

결국 **사용률(Utilization)과 포화(Saturation)는 다른 질문**입니다. Utilization은 "GPU가 시간의 몇 %를 바빴나", Saturation은 "GPU의 실제 용량(SM 처리량·메모리 대역폭·tensor core)을 얼마나 소비했나"인데, GPU-Util은 앞쪽만 답합니다.

> [!WARNING] `utilization.memory`도 같은 함정
> `--query-gpu=utilization.memory`는 VRAM 사용률이 아닙니다. "메모리를 읽거나 쓴 *시간*의 비율"입니다. 실제 VRAM 점유는 `memory.used` / `memory.total`로 봐야 합니다. 두 지표 다 "시간 기반 busy" 척도라는 게 혼동의 뿌리입니다.

## 제대로 읽는 법 — 한 지표로 단정하지 않기

GPU-Util 하나로 "GPU 바운드"라고 결론짓지 않고 여러 지표를 교차합니다.

- **`nvidia-smi dmon`의 `sm` 열** — "적어도 하나의 SM이 바빴던 시간 %". 여전히 시간 기반이지만 기본 GPU-Util보다 세밀합니다.
- **[DCGM](https://docs.nvidia.com/datacenter/dcgm/latest/gpu-telemetry/dcgm-exporter.html) 프로파일링 지표** — 진짜 포화를 봅니다.
  - `DCGM_FI_PROF_SM_ACTIVE` — warp가 상주한 SM 비율
  - `DCGM_FI_PROF_SM_OCCUPANCY` — warp 슬롯 점유율
  - `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE` — tensor core 가동
  - `DCGM_FI_PROF_DRAM_ACTIVE` — 메모리 대역폭 포화

스크립트로 값을 뽑을 땐 사람이 보는 기본 출력 대신 쿼리 모드를 씁니다(NVIDIA도 기본 출력 파싱은 권장하지 않습니다). `--format=csv`에 `noheader,nounits`를 붙이면 숫자만 깔끔하게 나옵니다.

```bash
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total \
  --format=csv,noheader,nounits
# 0, NVIDIA A100-SXM4-40GB, 78, 19478, 40960
```

## 정리

오늘 배운 건 이겁니다. `nvidia-smi`의 GPU-Util 100%는 "GPU를 꽉 쓰고 있다"가 아니라 "지난 주기에 커널이 계속 돌고 있었다"입니다. GPU가 실제로 포화됐는지는 GPU-Util + Memory-Usage + dmon `sm` + DCGM SM_ACTIVE/occupancy를 함께 봐야 알 수 있습니다. 다음부터 GPU-Util만 보고 "잘 돌아간다"고 안심하지 않으려 합니다.

## 참고 자료

- NVIDIA, [nvidia-smi Documentation](https://docs.nvidia.com/deploy/nvidia-smi/)
- NVIDIA, [DCGM Exporter — GPU Telemetry](https://docs.nvidia.com/datacenter/dcgm/latest/gpu-telemetry/dcgm-exporter.html)
- Arthur Chiao, [Understanding GPU Performance: Utilization vs. Saturation](https://arthurchiao.art/blog/understanding-gpu-performance/)
