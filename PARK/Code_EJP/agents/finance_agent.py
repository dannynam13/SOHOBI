from semantic_kernel.functions import kernel_function
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory

SYSTEM_PROMPT = """당신은 한국 소규모 외식업 창업자를 위한 재무 분석 전문 에이전트입니다.
사용자의 질문에 대해 아래 기준을 충족하는 응답을 작성하십시오.

- 수치 계산 근거와 가정(자기자본/대출 비율, 금리 고정/변동 여부 등)을 명시한다
- 금액 단위를 원(KRW)으로 일관되게 표기한다
- 핵심 가정을 최소 하나 이상 명시한다 (예: 고정금리 3.5% 가정)
- 낙관·기본·비관 시나리오와 신뢰 구간 또는 불확실성 범위를 포함한다
- 리스크 경고를 명시한다 (예: 실제 결과와 다를 수 있음, 원금 손실 가능성)
- 투자 권유가 아닌 정보 제공임을 명시한다

응답 형식:
[사용자 질문]
{question}

[에이전트 응답]
(위 기준을 충족하는 응답 내용)
"""

RETRY_PREFIX = """이전 응답에서 다음 문제가 지적되었습니다. 반드시 반영하여 전체 응답을 다시 작성하십시오.

[지적 사항]
{retry_prompt}

"""

class FinanceAgent:
    def __init__(self, kernel):
        self._kernel = kernel

    @kernel_function(name="generate_draft", description="재무 시뮬레이션 관련 draft 생성")
    async def generate_draft(self, question: str, retry_prompt: str = "") -> str:
        service: AzureChatCompletion = self._kernel.get_service("sign_off")
        system = (RETRY_PREFIX.format(retry_prompt=retry_prompt) if retry_prompt else "") + SYSTEM_PROMPT

        history = ChatHistory()
        history.add_system_message(system)
        history.add_user_message(question)

        from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
        settings = OpenAIChatPromptExecutionSettings(temperature=0.3)

        response = await service.get_chat_message_content(history, settings=settings)
        return str(response)