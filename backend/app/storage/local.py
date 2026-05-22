import asyncio
import os
from app.core.config import settings
from app.storage.base import BaseStorageProvider
from loguru import logger

class LocalStorageProvider(BaseStorageProvider):
    def __init__(self, base_path: str = settings.STORAGE_LOCAL_PATH):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)
        logger.info(f"LocalStorageProvider initialized at path: {self.base_path}")

    async def save_file(self, file_bytes: bytes, filename: str) -> str:
        # Create unique directory path or save directly
        file_path = os.path.join(self.base_path, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        loop = asyncio.get_event_loop()
        # Save file in thread pool to prevent blocking the async loop
        await loop.run_in_executor(None, self._write, file_path, file_bytes)
        logger.info(f"File successfully saved to local storage: {file_path}")
        return file_path

    async def read_file(self, file_path: str) -> bytes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._read, file_path)

    async def delete_file(self, file_path: str) -> None:
        if os.path.exists(file_path):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, os.remove, file_path)
            logger.info(f"File deleted from local storage: {file_path}")
        else:
            logger.warning(f"File delete requested but path does not exist: {file_path}")

    def _write(self, path: str, content: bytes) -> None:
        with open(path, "wb") as f:
            f.write(content)

    def _read(self, path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()
