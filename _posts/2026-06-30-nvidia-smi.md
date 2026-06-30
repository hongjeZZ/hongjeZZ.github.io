---
title: "nvidia-smi GPU-Util 지표의 의미와 한계"
date: 2026-06-30 16:16:14 +0900
categories: [Infra, GPU]
tags: [TIL, nvidia-smi, GPU, NVIDIA, 모니터링, NVML]
source_wiki: nvidia-smi
provenance: cite-only
---

이 글은 `nvidia-smi`의 `GPU-Util` 지표가 무엇을 의미하는지와 그 한계, 그리고 GPU 사용률을 정확히 판단하는 방법을 정리한 것입니다. 출처는 [NVIDIA 공식 문서](https://docs.nvidia.com/deploy/nvidia-smi/)입니다.

## nvidia-smi

`nvidia-smi`(NVIDIA System Management Interface)는 NVIDIA GPU를 모니터링·관리하는 CLI입니다. NVML(NVIDIA Management Library)이라는 C API를 감싼 얇은 래퍼로, 화면에 출력되는 값은 모두 NVML이 노출하는 상태입니다. 드라이버와 함께 설치되므로 별도 설치가 필요 없습니다.

기본 출력에서 헤더의 **CUDA Version**은 *드라이버가 지원하는 최대 CUDA 버전*이며, 설치된 CUDA toolkit 버전이 아닙니다. "CUDA Version: 12.4"는 12.4 이하 애플리케이션을 실행할 수 있다는 의미이지, toolkit 12.4가 설치돼 있다는 의미가 아닙니다.

## GPU-Util의 정의

NVML이 정의하는 GPU-Util은 다음과 같습니다.

> 지난 샘플 주기 동안 하나 이상의 커널이 실행되고 있던 시간의 비율. (샘플 주기는 제품에 따라 약 1초~1/6초)

GPU-Util은 하나 이상의 커널이 실행 중이면 카운트되는 **시간 기반 지표**입니다. GPU의 연산 자원을 얼마나 채웠는지가 아니라, 커널이 실행되고 있었는지를 시간으로 측정합니다. 그 결과 다음과 같은 경우가 발생합니다.

- 스레드 하나짜리 커널(`kernel<<<1,1>>>`)이 계속 실행되면 GPU-Util은 **100%**가 됩니다. 문서화된 한 실험에서는 단일 스레드 커널이 GPU-Util 100%를 보이는 동안 SM 점유율은 20% 미만이었습니다. GPU의 연산 유닛(SM) 대부분이 유휴 상태여도 커널이 실행 중이면 100%로 보고됩니다.
- 메모리를 기다리며 정지한 커널도 "실행 중"으로 집계됩니다. 연산 유닛이 유휴 상태인 메모리 대역폭 바운드 작업도 GPU-Util 100%를 보일 수 있습니다.

사용률(Utilization)과 포화(Saturation)는 다른 개념입니다. Utilization은 GPU가 시간의 몇 %를 사용 중이었는지를, Saturation은 GPU의 실제 용량(SM 처리량·메모리 대역폭·tensor core)을 얼마나 소비했는지를 나타냅니다. GPU-Util은 Utilization만 측정합니다.

> [!WARNING] `utilization.memory`도 시간 기반 지표
> `--query-gpu=utilization.memory`는 VRAM 사용률이 아니라 "메모리를 읽거나 쓴 시간의 비율"입니다. 실제 VRAM 점유는 `memory.used` / `memory.total`로 확인합니다.

## 포화 여부를 판단하는 지표

GPU 포화 여부는 GPU-Util 단독으로 판단하지 않고 여러 지표를 함께 확인합니다.

- **`nvidia-smi dmon`의 `sm` 열** — "적어도 하나의 SM이 사용 중이었던 시간 %"입니다. 시간 기반 지표지만 기본 GPU-Util보다 세분화돼 있습니다.
- **[DCGM](https://docs.nvidia.com/datacenter/dcgm/latest/gpu-telemetry/dcgm-exporter.html) 프로파일링 지표** — 실제 포화를 측정합니다.
  - `DCGM_FI_PROF_SM_ACTIVE` — warp가 상주한 SM의 비율
  - `DCGM_FI_PROF_SM_OCCUPANCY` — warp 슬롯 점유율
  - `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE` — tensor core 가동
  - `DCGM_FI_PROF_DRAM_ACTIVE` — 메모리 대역폭 포화

스크립트로 값을 수집할 때는 기본 출력 대신 쿼리 모드를 사용합니다. NVIDIA는 기본 출력 파싱을 권장하지 않습니다. `--format=csv`에 `noheader,nounits`를 지정하면 숫자만 출력됩니다.

```bash
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total \
  --format=csv,noheader,nounits
# 0, NVIDIA A100-SXM4-40GB, 78, 19478, 40960
```

## 정리

`nvidia-smi`의 GPU-Util 100%는 "GPU 연산 자원을 모두 사용 중"이라는 의미가 아니라 "지난 샘플 주기 동안 커널이 실행되고 있었다"는 의미입니다. GPU의 실제 포화 여부는 GPU-Util, Memory-Usage, `dmon`의 `sm` 열, DCGM의 SM_ACTIVE·occupancy 지표를 함께 확인해야 판단할 수 있습니다.

## 참고 자료

- NVIDIA, [nvidia-smi Documentation](https://docs.nvidia.com/deploy/nvidia-smi/)
- NVIDIA, [DCGM Exporter — GPU Telemetry](https://docs.nvidia.com/datacenter/dcgm/latest/gpu-telemetry/dcgm-exporter.html)
- Arthur Chiao, [Understanding GPU Performance: Utilization vs. Saturation](https://arthurchiao.art/blog/understanding-gpu-performance/)
