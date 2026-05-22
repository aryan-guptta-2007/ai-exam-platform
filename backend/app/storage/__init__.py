from app.core.config import settings
from app.storage.base import BaseStorageProvider
from app.storage.local import LocalStorageProvider

def get_storage_provider() -> BaseStorageProvider:
    provider = settings.STORAGE_PROVIDER.lower()
    
    if provider == "local":
        return LocalStorageProvider()
    else:
        # Placeholder for S3/R2 cloud storage providers
        # Defaulting back to local to guarantee functional system out of the box
        return LocalStorageProvider()
