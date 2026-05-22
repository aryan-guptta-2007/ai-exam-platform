from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Optional, Union

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_text(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        **kwargs
    ) -> str:
        """
        Generates and returns complete text.
        """
        pass

    @abstractmethod
    async def generate_stream(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Streams generated text token by token.
        """
        yield

    @abstractmethod
    async def generate_embeddings(
        self, 
        text: Union[str, List[str]], 
        **kwargs
    ) -> List[List[float]]:
        """
        Generates embedding vector(s) for the input text(s).
        Returns a list of vectors, where each vector is a list of floats.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Returns the identifier of the model being used.
        """
        pass
