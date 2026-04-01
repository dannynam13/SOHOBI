import os
import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import openai
from dotenv import load_dotenv

load_dotenv()

_TOKEN_PROVIDER = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",
)


def get_kernel() -> sk.Kernel:
    kernel = sk.Kernel()
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_ver = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")

    # 기본 서비스 (gpt-4o-mini) — chat, location 등
    kernel.add_service(
        AzureChatCompletion(
            service_id="sign_off",
            deployment_name=os.getenv("AZURE_DEPLOYMENT_NAME"),
            endpoint=endpoint,
            api_key=api_key if api_key else None,
            ad_token_provider=None if api_key else _TOKEN_PROVIDER,
            api_version=api_ver,
        )
    )

    # 고급 서비스 (gpt-4o) — admin, legal, finance 등 판단력 필요한 에이전트용
    admin_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", os.getenv("AZURE_DEPLOYMENT_NAME"))
    if admin_deployment and admin_deployment != os.getenv("AZURE_DEPLOYMENT_NAME"):
        kernel.add_service(
            AzureChatCompletion(
                service_id="admin_llm",
                deployment_name=admin_deployment,
                endpoint=endpoint,
                api_key=api_key if api_key else None,
                ad_token_provider=None if api_key else _TOKEN_PROVIDER,
                api_version=api_ver,
            )
        )

    return kernel


def get_signoff_client() -> openai.AsyncAzureOpenAI:
    return openai.AsyncAzureOpenAI(
        azure_endpoint=os.getenv("AZURE_SIGNOFF_ENDPOINT", os.getenv("AZURE_OPENAI_ENDPOINT")),
        azure_ad_token_provider=_TOKEN_PROVIDER,
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
        timeout=220.0,
    )