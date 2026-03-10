"""LLM service layer wrapping the Azure OpenAI API."""

from openai import AzureOpenAI, BadRequestError

from app.config import settings

_CONTENT_FILTER_RESPONSE = (
    "Your message was blocked by the content filter. Please try a different approach."
)


class LLMService:
    """Handles all interactions with the Azure OpenAI API."""

    def __init__(self) -> None:
        self.client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_api_key,
            api_version="2024-12-01-preview",
        )
        self.model = settings.llm_model

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
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=chat_messages,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except BadRequestError as e:
            if e.code == "content_filter":
                return _CONTENT_FILTER_RESPONSE
            raise

    def single_turn(self, system_prompt: str, user_message: str) -> str:
        """Convenience method for a single user->assistant exchange."""
        return self.chat(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    

if __name__ == "__main__":
    # Quick test to verify LLM service is working
    llm = LLMService()
    test_response = llm.single_turn(
        system_prompt="You are a helpful assistant.",
        user_message="What is 2 + 2?",
    )
    print("LLM Test Response:", test_response)
