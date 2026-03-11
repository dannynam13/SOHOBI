"""
도메인 라우터: 사용자 질문 → admin | finance | legal 분류
1차: 키워드 기반 (빠름), 2차: LLM 기반 (Azure OpenAI gpt-4o-mini)
"""

import json

from semantic_kernel.contents import ChatHistory
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings

from kernel_setup import get_kernel

# ── 1차 분류 키워드 ──────────────────────────────────────────
KEYWORDS: dict[str, list[str]] = {
    "admin":   ["신고", "허가", "인허가", "서류", "관청", "위생", "영업신고", "등록", "행정"],
    "finance": ["재무", "대출", "금리", "수익", "비용", "투자", "시뮬레이션", "매출", "자본"],
    "legal":   ["법", "계약", "소송", "보증금", "임대차", "조항", "권리", "의무", "판례"],
}

# ── 2차 분류 시스템 프롬프트 ─────────────────────────────────
_SYSTEM_PROMPT = """You are a query classifier for a Korean small business assistant.
Classify the user query into exactly one of: admin, finance, legal.
- admin: 행정 절차, 영업 신고, 허가, 서류, 관청 관련
- finance: 재무, 대출, 수익, 비용, 투자 시뮬레이션 관련
- legal: 법률, 계약, 권리 의무, 소송, 임대차 관련
Respond ONLY in JSON: {"domain": "...", "confidence": 0.0~1.0, "reasoning": "..."}"""

_FALLBACK = {"domain": "admin", "confidence": 0.3, "reasoning": "LLM 파싱 실패 — 기본값 적용"}


def _keyword_classify(question: str) -> dict | None:
    """키워드 2개 이상 매칭 시 해당 도메인 반환, 실패 시 None."""
    counts = {domain: sum(kw in question for kw in kws) for domain, kws in KEYWORDS.items()}
    best_domain = max(counts, key=counts.get)
    best_count = counts[best_domain]

    if best_count < 2:
        return None

    # 동점 확인
    top_domains = [d for d, c in counts.items() if c == best_count]
    if len(top_domains) > 1:
        return None

    matched = [kw for kw in KEYWORDS[best_domain] if kw in question]
    return {
        "domain": best_domain,
        "confidence": 0.85,
        "reasoning": f"키워드 {best_count}개 매칭: {', '.join(matched)}",
    }


async def _llm_classify(question: str) -> dict:
    """Azure OpenAI(gpt-4o-mini)에 분류 위임."""
    kernel = get_kernel()
    chat_service = kernel.get_service("sign_off")
    settings = AzureChatPromptExecutionSettings(
        response_format={"type": "json_object"}
    )

    history = ChatHistory()
    history.add_system_message(_SYSTEM_PROMPT)
    history.add_user_message(question)

    try:
        result = await chat_service.get_chat_message_content(
            chat_history=history,
            settings=settings,
        )
        parsed = json.loads(str(result))
        if parsed.get("domain") not in ("admin", "finance", "legal"):
            return _FALLBACK
        return parsed
    except Exception:
        return _FALLBACK


async def classify(question: str) -> dict:
    """
    사용자 질문을 도메인으로 분류한다.

    Returns:
        {
            "domain": "admin" | "finance" | "legal",
            "confidence": 0.0~1.0,
            "reasoning": "분류 근거 한 줄"
        }
    """
    # 1차: 키워드
    result = _keyword_classify(question)
    if result:
        return result

    # 2차: LLM
    return await _llm_classify(question)


if __name__ == "__main__":
    import asyncio

    tests = [
        "식품 영업신고는 어떻게 하나요?",
        "초기 투자금 5000만 원으로 카페를 창업하면 수익성이 있나요?",
        "임대차 계약 만료 후 보증금을 못 받으면 어떻게 하나요?",
    ]

    async def main():
        for q in tests:
            result = await classify(q)
            print(f"Q: {q[:30]}...")
            print(f"  → {result}\n")

    asyncio.run(main())
