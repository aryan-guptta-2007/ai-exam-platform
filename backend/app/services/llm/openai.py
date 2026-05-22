from typing import AsyncGenerator, List, Optional, Union
from openai import AsyncOpenAI
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from loguru import logger

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str = settings.OPENAI_API_KEY, model_name: str = "gpt-4o-mini"):
        self.model_name = model_name
        self.api_key = api_key
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key)
        else:
            self.client = None
            logger.warning("OpenAI API Key is missing. OpenAI provider will fail if invoked.")

    def get_model_name(self) -> str:
        return self.model_name

    async def generate_text(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        **kwargs
    ) -> str:
        if not self.client:
            raise ValueError("OpenAI client is not configured.")

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=kwargs.get("temperature", 0.2),
                max_tokens=kwargs.get("max_tokens", 2048),
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI text generation error: {e}")
            raise e

    async def generate_stream(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        if not self.client:
            raise ValueError("OpenAI client is not configured.")

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=kwargs.get("temperature", 0.2),
                max_tokens=kwargs.get("max_tokens", 2048),
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise e

    async def generate_embeddings(
        self, 
        text: Union[str, List[str]], 
        **kwargs
    ) -> List[List[float]]:
        if not self.client:
            raise ValueError("OpenAI client is not configured.")

        embedding_model = kwargs.get("model", "text-embedding-3-small")
        
        try:
            response = await self.client.embeddings.create(
                model=embedding_model,
                input=text
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error(f"OpenAI embedding generation error: {e}")
            raise e
class GPT4Provider(OpenAIProvider):
    def __init__(self, api_key: str = settings.OPENAI_API_KEY):
        super().__init__(api_key=api_key, model_name="gpt-4o")
