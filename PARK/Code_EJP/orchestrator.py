"""
오케스트레이터: 하위 에이전트 → Sign-off Agent 전체 루프 관리
"""

import uuid
from typing import Literal

from kernel_setup import get_kernel
from agents.admin_agent import AdminAgent
from agents.finance_agent import FinanceAgent
from agents.legal_agent import LegalAgent
from step3_domain_signoff import run_signoff  # 기존 판정 엔진


AGENT_MAP = {
    "admin":   AdminAgent,
    "finance": FinanceAgent,
    "legal":   LegalAgent,
}


async def run(
    domain: Literal["admin", "finance", "legal"],
    question: str,
    max_retries: int = 3,
) -> dict:
    kernel = get_kernel()
    agent = AGENT_MAP[domain](kernel)

    request_id = str(uuid.uuid4())[:8]
    rejection_history = []
    retry_prompt = ""
    draft = ""

    for attempt in range(1, max_retries + 2):  # max_retries 초과 시 에스컬레이션
        # 1. 하위 에이전트 draft 생성
        draft = await agent.generate_draft(
            question=question,
            retry_prompt=retry_prompt,
        )

        # 2. Sign-off Agent 판정
        verdict = await run_signoff(domain=domain, draft=draft)

        # issues가 없는데 approved=false → 모델 논리 오류, 강제 통과 처리
        if not verdict.get("issues") and not verdict.get("approved"):
            verdict["approved"] = True

        if verdict["approved"]:
            return {
                "status": "approved",
                "retry_count": attempt - 1,
                "request_id": request_id,
                "message": "",
                "rejection_history": rejection_history,
                "draft": draft,
            }

        # 3. 거부 — 이력 기록 후 재시도 준비
        rejection_history.append({"attempt": attempt, "verdict": verdict})
        retry_prompt = verdict.get("retry_prompt", "")

        if attempt > max_retries:
            break

    # 한도 초과 — 에스컬레이션
    return {
        "status": "escalated",
        "retry_count": max_retries,
        "request_id": request_id,
        "message": f"재시도 {max_retries}회 초과. 마지막 거부 이유: {rejection_history[-1]['verdict'].get('retry_prompt', '')}",
        "rejection_history": rejection_history,
        "draft": draft,
    }