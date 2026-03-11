"""
연동 테스트: 오케스트레이터 → 하위 에이전트 → Sign-off Agent 전체 루프 검증

실행:
    python integration_test.py                # 전체 시나리오 (normal + retry)
    python integration_test.py normal         # 정상 경로만
    python integration_test.py retry          # 재시도 경로만
    python integration_test.py escalation     # 에스컬레이션 경로 (max_retries=1 강제)
    python integration_test.py all            # 전체 시나리오 + 에스컬레이션
"""

import asyncio
import json
import sys
import uuid

from orchestrator import run
from step3_domain_signoff import run_signoff, MOCK_DRAFTS

# ── 시나리오 정의 ─────────────────────────────────────────────
NORMAL_CASES = [
    ("admin",   "식품 가게를 창업하려고 하는데 영업신고는 어떻게 하나요?"),
    ("finance", "소규모 카페 창업 시 초기 6개월 재무 시뮬레이션을 보여주세요. 초기 투자금은 5,000만 원입니다."),
    ("legal",   "임대차 계약 만료 후 집주인이 보증금을 돌려주지 않으면 어떻게 하나요?"),
]

# 형식상 완전하지만 루브릭 누락을 유발하기 쉬운 질문 — 재시도 루프 작동 확인용
# · admin  : 절차 대신 '분위기'를 묻는 질문 → 법령 조문·서류명·처리기관·기간(A1-A5) 누락 유도
# · finance: 정성적 판단을 구하는 질문 → 수치·단위·가정·리스크 경고(F1-F5) 누락 유도
# · legal  : 직접 조언을 구하는 질문 → 면책 고지·법령 인용·전문가 권고(G1-G4) 누락 유도
RETRY_CASES = [
    ("admin",   "식품 창업을 준비 중인데, 전반적으로 어떤 마음가짐으로 행정 절차에 임하면 좋을까요?"),
    ("finance", "소규모 카페 창업이 현실적으로 수익을 낼 수 있는 사업인지 솔직한 의견을 들려주세요."),
    ("legal",   "임대차 계약 만료 시 세입자 입장에서 가장 유리하게 대처하는 방법을 알려주세요."),
]


def print_result(result: dict) -> None:
    status = result["status"]
    symbol = "APPROVED" if status == "approved" else "ESCALATED"
    print(f"  상태     : {symbol}")
    print(f"  재시도   : {result['retry_count']}회")
    print(f"  request_id: {result['request_id']}")

    if status == "escalated":
        print(f"  메시지   : {result.get('message', '')}")

    if result["rejection_history"]:
        print(f"  거부 이력 ({len(result['rejection_history'])}건):")
        for h in result["rejection_history"]:
            issues = [i["code"] for i in h["verdict"].get("issues", [])]
            print(f"    시도 {h['attempt']}: issues={issues}")

    print(f"\n  최종 draft:\n{result['draft']}")


async def run_suite(cases: list, label: str, max_retries: int = 3) -> None:
    print(f"\n{'#' * 64}")
    print(f"  {label}")
    print(f"{'#' * 64}")

    approved_count = 0
    escalated_count = 0

    for domain, question in cases:
        print(f"\n{'=' * 52}")
        print(f"  도메인  : {domain.upper()}")
        print(f"  질문    : {question}")
        print("=" * 52)

        result = await run(domain, question, max_retries=max_retries)
        print_result(result)

        if result["status"] == "approved":
            approved_count += 1
        else:
            escalated_count += 1

    print(f"\n{'─' * 52}")
    print(f"  결과: {approved_count}건 승인 / {escalated_count}건 에스컬레이션")


async def _run_signoff_loop(domain: str, draft: str, max_retries: int = 2) -> dict:
    """
    고정 draft를 Sign-off에 반복 투입하는 에스컬레이션 전용 루프.
    서브-에이전트 재생성 없이 동일 draft를 계속 평가하므로,
    초기 draft가 루브릭을 통과하지 못하면 반드시 에스컬레이션에 도달한다.
    """
    request_id = str(uuid.uuid4())[:8]
    rejection_history = []

    for attempt in range(1, max_retries + 2):
        verdict = await run_signoff(domain=domain, draft=draft)

        if verdict["approved"]:
            return {
                "status": "approved",
                "retry_count": attempt - 1,
                "request_id": request_id,
                "message": "",
                "rejection_history": rejection_history,
                "draft": draft,
            }

        rejection_history.append({"attempt": attempt, "verdict": verdict})

        if attempt > max_retries:
            break

    last_retry_prompt = rejection_history[-1]["verdict"].get("retry_prompt", "")
    return {
        "status": "escalated",
        "retry_count": max_retries,
        "request_id": request_id,
        "message": f"재시도 {max_retries}회 초과. 마지막 거부 이유: {last_retry_prompt}",
        "rejection_history": rejection_history,
        "draft": draft,
    }


def _check_escalation_result(result: dict) -> list[str]:
    """에스컬레이션 경로 검증 — 실패한 항목 목록 반환 (없으면 빈 리스트)."""
    failures = []
    if result["status"] != "escalated":
        failures.append(f"status='{result['status']}' (expected 'escalated')")
    if not result["rejection_history"]:
        failures.append("rejection_history가 비어 있음")
    if not result.get("message"):
        failures.append("message 필드가 비어 있음")
    last = result["rejection_history"][-1] if result["rejection_history"] else {}
    if not last.get("verdict", {}).get("retry_prompt"):
        failures.append("마지막 verdict에 retry_prompt가 없음")
    return failures


async def run_escalation_suite(max_retries: int = 2) -> None:
    """
    MOCK_DRAFTS(고정 실패 draft)를 Sign-off에 직접 반복 투입하여 에스컬레이션 경로를 검증한다.
    서브-에이전트를 거치지 않으므로 draft가 개선되지 않아 에스컬레이션이 확실히 발생한다.
    """
    label = f"[ 에스컬레이션 경로 — 고정 실패 draft, max_retries={max_retries} ]"
    print(f"\n{'#' * 64}")
    print(f"  {label}")
    print(f"  ※ 설계상 반드시 Sign-off를 통과하지 못하는 고정 draft를 사용합니다.")
    print(f"  ※ 서브-에이전트 재생성 없이 동일 draft를 반복 평가합니다.")
    print(f"{'#' * 64}")

    pass_count = 0
    fail_count = 0

    for domain, draft in MOCK_DRAFTS.items():
        print(f"\n{'=' * 52}")
        print(f"  도메인  : {domain.upper()}")
        print(f"  draft   : (step3_domain_signoff.MOCK_DRAFTS['{domain}'])")
        print("=" * 52)

        result = await _run_signoff_loop(domain=domain, draft=draft, max_retries=max_retries)
        print_result(result)

        failures = _check_escalation_result(result)
        if failures:
            print(f"  [검증 실패]")
            for f in failures:
                print(f"    - {f}")
            fail_count += 1
        else:
            print(f"  [검증 통과] 에스컬레이션 경로 정상 동작 확인")
            pass_count += 1

    print(f"\n{'─' * 52}")
    print(f"  결과: {pass_count}건 검증 통과 / {fail_count}건 검증 실패")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "normal":
        await run_suite(NORMAL_CASES, "[ 정상 경로 — 충분한 질문 ]")
    elif mode == "retry":
        await run_suite(RETRY_CASES, "[ 재시도 경로 — 루브릭 누락 유발 질문 ]")
    elif mode == "escalation":
        await run_escalation_suite()
    elif mode == "all":
        await run_suite(NORMAL_CASES, "[ 정상 경로 — 충분한 질문 ]")
        await run_suite(RETRY_CASES, "[ 재시도 경로 — 루브릭 누락 유발 질문 ]")
        await run_escalation_suite()
    else:
        await run_suite(NORMAL_CASES, "[ 정상 경로 — 충분한 질문 ]")
        await run_suite(RETRY_CASES, "[ 재시도 경로 — 루브릭 누락 유발 질문 ]")


if __name__ == "__main__":
    asyncio.run(main())
