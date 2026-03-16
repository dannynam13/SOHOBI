# Railway 로그 로컬 내려받기 가이드

**작성일**: 2026-03-16
**대상 폴더**: `integrated_PARK/`
**관련 파일**:
- `scripts/pull_logs.py`
- `api_server.py` — `GET /api/v1/logs/export`
- `logger.py` — `errors.jsonl` 포함 3종 로그 파일
- `log_formatter.py` — 로컬 분석용

---

## 개요

백엔드는 Railway 서비스에서 실행되며, 모든 요청 기록은 Railway 볼륨의 다음 세 파일에 누적됩니다.

| 파일 | 내용 |
|------|------|
| `logs/queries.jsonl` | 전체 요청 이력 |
| `logs/rejections.jsonl` | Sign-off에서 한 번 이상 반려된 요청 |
| `logs/errors.jsonl` | 응답 생성 자체가 실패한 요청 |

`scripts/pull_logs.py`를 실행하면 이 세 파일을 로컬로 내려받아 분석할 수 있습니다.

---

## 사전 준비

### 1. EXPORT_SECRET 확인

로그 내려받기에는 인증 키가 필요합니다. 키는 팀 내부 채널을 통해 공유되며, 프로젝트 관리자에게 문의하십시오.

키를 받은 뒤 `integrated_PARK/.env` 파일에 추가합니다.

```
EXPORT_SECRET=<받은 키 값>
```

> `.env` 파일이 없으면 `.env.example`을 복사하여 생성하십시오.
> `.env`는 `.gitignore`에 포함되어 있으므로 커밋되지 않습니다.

### 2. RAILWAY_HOST 확인

Railway 서비스의 공개 URL을 `.env`에 추가합니다.

```
RAILWAY_HOST=https://<서비스명>.up.railway.app
```

URL은 Railway 대시보드 → 서비스 → Settings → Domains에서 확인할 수 있습니다.

### 3. 의존성 확인

`pull_logs.py`는 `requests`와 `python-dotenv`를 사용합니다. 이미 `requirements.txt`에 포함되어 있으므로 별도 설치 없이 사용 가능합니다.

```bash
pip install -r requirements.txt
```

---

## 사용법

`integrated_PARK/` 디렉터리에서 실행합니다.

### 기본 실행 (세 파일 모두 내려받기)

```bash
python scripts/pull_logs.py
```

`.env`의 `RAILWAY_HOST`와 `EXPORT_SECRET`을 자동으로 읽습니다.
결과는 `logs/remote/` 디렉터리에 저장됩니다.

```
대상: https://xxx.up.railway.app  →  logs/remote/
  [queries]     완료 → logs/remote/queries.jsonl (24.3 KB)
  [rejections]  완료 → logs/remote/rejections.jsonl (8.1 KB)
  [errors]      완료 → logs/remote/errors.jsonl (1.2 KB)
```

### 특정 타입만 내려받기

```bash
python scripts/pull_logs.py --type queries
python scripts/pull_logs.py --type rejections
python scripts/pull_logs.py --type errors
```

### 저장 경로 지정

```bash
python scripts/pull_logs.py --out logs/2026-03-16/
```

### 명령줄에서 직접 값 지정

`.env` 설정 없이 실행할 경우:

```bash
python scripts/pull_logs.py \
  --host https://xxx.up.railway.app \
  --secret <EXPORT_SECRET 값>
```

---

## 로컬 분석

내려받은 파일은 `log_formatter.py`로 분석합니다.
`LOGS_DIR` 환경변수로 다운로드 경로를 지정합니다.

```bash
# 전체 요청 요약 출력
LOGS_DIR=logs/remote python log_formatter.py --type queries

# 거부 이력만, 최근 20건
LOGS_DIR=logs/remote python log_formatter.py --type rejections --limit 20

# 마크다운 리포트 파일로 저장
LOGS_DIR=logs/remote python log_formatter.py --type queries --output logs/report.md
```

출력 예시:

```
============================================================
SOHOBI 에이전트 로그 요약
생성 시각: 2026-03-16 14:32:00
============================================================
전체 요청: 47건
  ✅ approved:  41건 (87.2%)
  ❌ escalated:  6건 (12.8%)
평균 응답 시간: 4823ms
평균 재시도: 0.38회

도메인별 요청 수:
  법무(legal): 18건
  재무(finance): 16건
  행정(admin): 13건
```

---

## 오류 대처

| 증상 | 원인 | 해결 |
|------|------|------|
| `실패 — EXPORT_SECRET 불일치` | `.env`의 키가 Railway 환경변수와 다름 | 팀 관리자에게 현재 키 확인 |
| `실패 — 서버에 연결할 수 없습니다` | `RAILWAY_HOST` URL 오기입 또는 서비스 중단 | URL 재확인 또는 Railway 대시보드에서 서비스 상태 확인 |
| `건너뜀 (파일 없음)` | 해당 타입의 로그가 아직 없음 | 정상 상태. 해당 이벤트가 발생하면 생성됨 |
| `오류: RAILWAY_HOST 를 지정하십시오` | `.env`에 `RAILWAY_HOST` 누락 | `.env`에 추가하거나 `--host` 옵션 사용 |

---

## 주의사항

- 로그 파일에는 사용자 질문 내용이 포함됩니다. **내려받은 파일을 외부에 공유하지 마십시오.**
- `logs/remote/` 디렉터리는 `.gitignore`에 추가되어 있어 커밋되지 않습니다.
- 실행할 때마다 파일을 **덮어씁니다**. 특정 시점의 스냅샷을 보존하려면 `--out` 옵션으로 날짜별 경로를 지정하십시오.

```bash
python scripts/pull_logs.py --out logs/$(date +%Y-%m-%d)/
```
