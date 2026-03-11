"""
Sign-off 에이전트 판정 결정성 검증

동일한 draft를 N회 반복 평가하여 approved / issues 코드 집합이 매번 일치하는지 확인한다.
temperature=0.0 설정에도 불구하고 결과가 달라진다면 루브릭 문구의 해석 여지가 과도하다는 신호다.

실행:
    python determinism_test.py                  # 전 도메인, 5회 반복 (기본값)
    python determinism_test.py admin 10         # admin 도메인, 10회 반복
    python determinism_test.py finance 3        # finance 도메인, 3회 반복
    python determinism_test.py legal            # legal 도메인, 5회 반복
    python determinism_test.py all 7            # 전 도메인, 7회 반복
"""

import asyncio
import json
import sys
from collections import Counter

from step3_domain_signoff import run_signoff, MOCK_DRAFTS, REQUIRED_CODES

# 결정성 판단 기준: 전체 시도 중 동일 결과 비율이 이 값 미만이면 UNSTABLE
STABILITY_THRESHOLD = 1.0  # 100% 일치 시에만 STABLE


def _result_signature(verdict: dict) -> str:
    """verdict에서 비교 가능한 서명 문자열 생성 (approved + 정렬된 issues 코드)."""
    approved = verdict.get("approved", False)
    issues_codes = tuple(sorted(i["code"] for i in verdict.get("issues", [])))
    passed_codes = tuple(sorted(verdict.get("passed", [])))
    return json.dumps({"approved": approved, "issues": issues_codes, "passed": passed_codes})


async def test_domain(domain: str, n: int) -> dict:
    """domain의 MOCK_DRAFT를 n회 평가하고 결정성 결과를 반환한다."""
    draft = MOCK_DRAFTS[domain]
    signatures = []
    verdicts = []

    print(f"\n  {'─' * 48}")
    print(f"  도메인: {domain.upper()}  ({n}회 반복)")
    print(f"  {'─' * 48}")

    for i in range(1, n + 1):
        verdict = await run_signoff(domain, draft)
        sig = _result_signature(verdict)
        signatures.append(sig)
        verdicts.append(verdict)

        approved_mark = "O" if verdict.get("approved") else "X"
        issues_codes = sorted(i["code"] for i in verdict.get("issues", []))
        print(f"  [{i:2d}] approved={approved_mark}  issues={issues_codes}")

    # ── 결정성 분석 ──────────────────────────────────────────
    counter = Counter(signatures)
    most_common_sig, most_common_count = counter.most_common(1)[0]
    stability_ratio = most_common_count / n
    is_stable = len(counter) == 1

    print(f"\n  [분석]")
    if is_stable:
        print(f"  STABLE   — {n}회 전부 동일한 결과")
    else:
        print(f"  UNSTABLE — {len(counter)}가지 서로 다른 결과 발생")
        print(f"  최빈 결과: {most_common_count}/{n}회 ({stability_ratio:.0%})")
        print(f"  편차 케이스:")
        for sig, count in counter.items():
            parsed = json.loads(sig)
            if sig != most_common_sig:
                print(f"    {count}회: approved={parsed['approved']}  issues={list(parsed['issues'])}")

    return {
        "domain": domain,
        "stable": is_stable,
        "unique_results": len(counter),
        "stability_ratio": stability_ratio,
        "most_common_count": most_common_count,
        "total": n,
    }


async def main():
    args = sys.argv[1:]
    domain_arg = args[0] if args else "all"
    n = int(args[1]) if len(args) >= 2 else 5

    if domain_arg not in (*REQUIRED_CODES.keys(), "all"):
        print(f"알 수 없는 도메인: '{domain_arg}'")
        print(f"사용 가능한 도메인: {list(REQUIRED_CODES.keys())} 또는 all")
        sys.exit(1)

    domains = list(REQUIRED_CODES.keys()) if domain_arg == "all" else [domain_arg]

    print(f"\n{'=' * 52}")
    print(f"  Sign-off 결정성 검증  |  반복 횟수: {n}회")
    print(f"  temperature=0.0 고정 상태에서 판정이 일관되는지 확인")
    print(f"{'=' * 52}")

    results = []
    for domain in domains:
        result = await test_domain(domain, n)
        results.append(result)

    # ── 최종 요약 ─────────────────────────────────────────────
    print(f"\n{'=' * 52}")
    print(f"  최종 요약")
    print(f"{'=' * 52}")

    all_stable = True
    for r in results:
        status = "STABLE  " if r["stable"] else "UNSTABLE"
        ratio = f"{r['most_common_count']}/{r['total']} ({r['stability_ratio']:.0%})"
        print(f"  {r['domain'].upper():8s} {status}  일치율: {ratio}")
        if not r["stable"]:
            all_stable = False

    print(f"\n  {'[전체 STABLE]' if all_stable else '[주의] 일부 도메인에서 판정 불일치 발생 — 루브릭 재검토 권고'}")


if __name__ == "__main__":
    asyncio.run(main())
