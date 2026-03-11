"""
API 서버: FastAPI 기반 외부 인터페이스
- GET  /health            — 헬스 체크
- POST /api/v1/query      — 질문 → 도메인 라우팅 → 오케스트레이터 전체 루프
- POST /api/v1/signoff    — 기존 draft → Sign-off 단독 검증
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import domain_router
import orchestrator
from step3_domain_signoff import run_signoff

app = FastAPI(title="SOHOBI Sign-off API", version="0.1.0")


# ── 스키마 ────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    domain: str | None = Field(default=None, description="없으면 domain_router로 자동 분류")
    max_retries: int = Field(default=3, ge=0, le=10)


class SignoffRequest(BaseModel):
    domain: str = Field(description="admin | finance | legal")
    draft: str


# ── 엔드포인트 ────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "domains": ["admin", "finance", "legal"],
    }


@app.post("/api/v1/query")
async def query(req: QueryRequest):
    try:
        # 도메인 결정
        if req.domain and req.domain in ("admin", "finance", "legal"):
            domain = req.domain
        else:
            classification = await domain_router.classify(req.question)
            domain = classification["domain"]

        # 오케스트레이터 실행 (수정 없이 import)
        result = await orchestrator.run(
            domain=domain,
            question=req.question,
            max_retries=req.max_retries,
        )

        return {
            "request_id":  result["request_id"],
            "status":      result["status"],
            "domain":      domain,
            "draft":       result["draft"],
            "retry_count": result["retry_count"],
            "message":     result["message"],
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/v1/signoff")
async def signoff(req: SignoffRequest):
    try:
        if req.domain not in ("admin", "finance", "legal"):
            return JSONResponse(
                status_code=400,
                content={"error": f"지원하지 않는 도메인: {req.domain}"},
            )
        verdict = await run_signoff(domain=req.domain, draft=req.draft)
        return verdict
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── 실행 블록 ─────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
