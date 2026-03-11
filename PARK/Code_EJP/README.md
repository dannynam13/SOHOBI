# Code_EJP — Sign-off Agent 파이프라인

## 실행 방법

### 환경 설정

`.env.example`을 참고하여 `.env` 파일을 생성한 뒤 Azure OpenAI 키를 입력한다.

```bash
cp .env.example .env
# .env 파일을 편집하여 AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_DEPLOYMENT_NAME 값을 입력
```

의존성 설치:

```bash
pip install -r requirements.txt
```

---

### domain_router.py 단독 테스트

도메인 분류기를 독립 실행하여 키워드 분류와 LLM 분류 결과를 확인한다.

```bash
cd Code_EJP
python domain_router.py
```

---

### api_server.py 서버 실행

```bash
cd Code_EJP
python api_server.py
```

또는 uvicorn 직접 실행:

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

서버 기동 후 `http://localhost:8000/docs` 에서 Swagger UI로 엔드포인트를 확인할 수 있다.

---

### 엔드포인트 curl 예시

#### GET /health — 서버 상태 확인

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "version": "0.1.0", "domains": ["admin", "finance", "legal"]}
```

---

#### POST /api/v1/query — 질문 전송 (전체 파이프라인)

`domain` 필드를 생략하면 `domain_router`가 자동으로 분류한다.

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "식품 가게를 창업하려고 하는데 영업신고는 어떻게 하나요?",
    "max_retries": 3
  }'
```

```json
{
  "request_id": "a1b2c3d4",
  "status": "approved",
  "domain": "admin",
  "draft": "[사용자 질문]\n...\n[에이전트 응답]\n...",
  "retry_count": 0,
  "message": ""
}
```

---

#### POST /api/v1/signoff — draft 단독 Sign-off 검증

```bash
curl -X POST http://localhost:8000/api/v1/signoff \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "legal",
    "draft": "[사용자 질문]\n보증금을 못 받으면 어떻게 하나요?\n\n[에이전트 응답]\n본 응답은 법적 조언이 아닙니다..."
  }'
```

```json
{
  "approved": true,
  "passed": ["C1", "C2", "G1", "G2", "G3", "G4"],
  "issues": [],
  "retry_prompt": ""
}
```

---

### 통합 테스트 실행

```bash
# 정상 경로 + 재시도 경로
python integration_test.py

# 에스컬레이션 경로 (고정 실패 draft 사용)
python integration_test.py escalation

# 전체 경로
python integration_test.py all
```
