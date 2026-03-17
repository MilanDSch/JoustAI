"""LLM service layer wrapping the OpenAI-compatible API."""

from openai import AzureOpenAI, BadRequestError, OpenAI

from app.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_CONTENT_FILTER_RESPONSE = (
    "Your message was blocked by the content filter. Please try a different approach."
)


class LLMService:
    """Handles all interactions with an OpenAI-compatible API."""

    def __init__(self) -> None:
        if settings.llm_provider == "local":
            self.client = OpenAI(
                base_url=settings.local_api_base,
                api_key="local-mode",
            )
            self.model = settings.local_model_name
        else:
            self.client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_api_key,
                api_version=settings.azure_api_version,
            )
            self.model = settings.openai_model_name

        logger.info("Using provider: %s, model: %s", settings.llm_provider, self.model)

    def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
    ) -> str:
        """Send a conversation to the model and return the assistant's text response.

        Args:
            system_prompt: The defender's system prompt.
            messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
            max_tokens: Max response length.

        Returns:
            The assistant's text response.
        """
        chat_messages = [{"role": "system", "content": system_prompt}] + messages
        logger.debug(
            "LLM request: model=%s, messages=%d, max_tokens=%d",
            self.model,
            len(chat_messages),
            max_tokens,
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=chat_messages,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except BadRequestError as e:
            if e.code == "content_filter":
                logger.error("Azure content filter blocked the request: %s", e)
                return _CONTENT_FILTER_RESPONSE
            logger.error("LLM BadRequestError: %s", e)
            raise
        except Exception as e:
            logger.error("LLM request failed (%s): %s", type(e).__name__, e)
            raise

    def single_turn(self, system_prompt: str, user_message: str) -> str:
        """Convenience method for a single user->assistant exchange."""
        return self.chat(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    
