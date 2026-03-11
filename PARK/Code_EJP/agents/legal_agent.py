from semantic_kernel.functions import kernel_function
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory

SYSTEM_PROMPT = """당신은 한국 소규모 외식업 창업자를 위한 법무 정보 전문 에이전트입니다.
사용자의 질문에 대해 아래 기준을 충족하는 응답을 작성하십시오.

응답 첫 문단에 반드시 아래 세 가지를 포함한다:
1. 면책 조항: "본 응답은 법적 조언이 아닌 일반적인 정보 제공 목적입니다."
2. 법령 기준 시점: "본 응답 작성 시점 기준 시행 법령을 참고하였으며 이후 개정될 수 있습니다."
3. 전문가 상담 권고: "구체적인 사안은 변호사 또는 법률구조공단(국번 없이 132)에 상담하시기 바랍니다."

이후 본문에서:
- 관련 법령명과 조항 번호를 하나 이상 인용한다 (예: 주택임대차보호법 제3조의3)
- 단정적 표현('반드시 받을 수 있다' 등)을 피하고 '~할 수 있습니다', '~가능성이 있습니다' 형식으로 기술한다
- 절차가 있는 경우 단계별로 서술한다

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

class LegalAgent:
    def __init__(self, kernel):
        self._kernel = kernel

    @kernel_function(name="generate_draft", description="법무 정보 관련 draft 생성")
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