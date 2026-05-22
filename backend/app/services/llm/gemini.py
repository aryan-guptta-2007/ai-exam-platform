import asyncio
from typing import AsyncGenerator, List, Optional, Union
import google.generativeai as genai
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from loguru import logger

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str = settings.GEMINI_API_KEY, model_name: str = "gemini-1.5-flash"):
        self.model_name = model_name
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)
        else:
            logger.warning("Gemini API Key is missing. Gemini provider will fail if invoked.")

    def get_model_name(self) -> str:
        return self.model_name

    async def generate_text(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        **kwargs
    ) -> str:
        if not self.api_key:
            raise ValueError("Gemini API key is not configured.")
        
        # Configure model parameters
        config = genai.types.GenerationConfig(
            temperature=kwargs.get("temperature", 0.2),
            max_output_tokens=kwargs.get("max_tokens", 2048),
        )

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction
        )

        try:
            # Run generator in separate thread if sync, or use native async if available
            response = await model.generate_content_async(
                prompt,
                generation_config=config
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise e

    async def generate_stream(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            raise ValueError("Gemini API key is not configured.")

        config = genai.types.GenerationConfig(
            temperature=kwargs.get("temperature", 0.2),
            max_output_tokens=kwargs.get("max_tokens", 2048),
        )

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction
        )

        try:
            response = await model.generate_content_async(
                prompt,
                generation_config=config,
                stream=True
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini streaming generation error: {e}")
            raise e

    async def generate_embeddings(
        self, 
        text: Union[str, List[str]], 
        **kwargs
    ) -> List[List[float]]:
        if not self.api_key:
            raise ValueError("Gemini API key is not configured.")

        # Default model for embeddings in Gemini is text-embedding-004
        embedding_model = kwargs.get("model", "models/text-embedding-004")
        
        try:
            # embed_content is sync, run in executor to keep it async
            loop = asyncio.get_event_loop()
            
            if isinstance(text, str):
                result = await loop.run_in_executor(
                    None,
                    lambda: genai.embed_content(
                        model=embedding_model,
                        content=text,
                        task_type="retrieval_document"
                    )
                )
                # Returns dict with 'embedding': {'values': [...]}
                return [result["embedding"]]
            else:
                result = await loop.run_in_executor(
                    None,
                    lambda: genai.embed_content(
                        model=embedding_model,
                        content=text,
                        task_type="retrieval_document"
                    )
                )
                # Returns dict with 'embedding': [{'values': [...]}, ...]
                return [item["values"] for item in result["embedding"]]
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            raise e
class GeminiProProvider(GeminiProvider):
    def __init__(self, api_key: str = settings.GEMINI_API_KEY):
        super().__init__(api_key=api_key, model_name="gemini-1.5-pro")
