import asyncio
import json
import random
from typing import AsyncGenerator, List, Optional, Union
from app.services.llm.base import BaseLLMProvider

class MockLLMProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "mock-model"):
        self.model_name = model_name

    def get_model_name(self) -> str:
        return self.model_name

    async def generate_text(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        **kwargs
    ) -> str:
        # Check if the prompt is for metadata extraction
        if "JSON" in (system_instruction or "") or "json" in prompt.lower():
            if "key_concepts" in (system_instruction or "") or "key_concepts" in prompt:
                return json.dumps({
                    "summary": "This is a mock summary of the uploaded study document.",
                    "key_concepts": ["Mock Concept A", "Mock Concept B", "Mock Concept C"],
                    "suggested_title": "Mock Study Material",
                    "topics": ["Mock Topic 1", "Mock Topic 2"]
                })
            
            # If it's for exam/question generation
            if "question" in prompt.lower() or "exam" in prompt.lower():
                return json.dumps([
                    {
                        "text": "What is the primary benefit of the Mock Ingestion Flow?",
                        "expected_answer": "It allows end-to-end integration testing without active API credentials.",
                        "rubric": "Mentions integration testing, mock data, or no API keys."
                    },
                    {
                        "text": "Explain why vector databases are used in RAG systems.",
                        "expected_answer": "They enable efficient semantic search by comparing high-dimensional embedding vectors.",
                        "rubric": "Mentions semantic search, embeddings, or similarity matching."
                    }
                ])

        return "This is a mock response from the Mock LLM Provider, simulating a professional output."

    async def generate_stream(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        text = await self.generate_text(prompt, system_instruction, **kwargs)
        words = text.split(" ")
        for word in words:
            yield word + " "
            await asyncio.sleep(0.02)

    async def generate_embeddings(
        self, 
        text: Union[str, List[str]], 
        **kwargs
    ) -> List[List[float]]:
        if isinstance(text, str):
            return [[random.uniform(-0.1, 0.1) for _ in range(1536)]]
        else:
            return [[random.uniform(-0.1, 0.1) for _ in range(1536)] for _ in text]
