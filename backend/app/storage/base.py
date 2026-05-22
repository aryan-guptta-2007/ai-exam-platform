from abc import ABC, abstractmethod

class BaseStorageProvider(ABC):
    @abstractmethod
    async def save_file(self, file_bytes: bytes, filename: str) -> str:
        """
        Saves the file to the target storage and returns its storage URI/path.
        """
        pass

    @abstractmethod
    async def read_file(self, file_path: str) -> bytes:
        """
        Reads and returns the contents of the file from the storage path.
        """
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> None:
        """
        Deletes the file from storage path.
        """
        pass
