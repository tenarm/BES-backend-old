from abc import ABC, abstractmethod
from typing import BinaryIO

class AbstractFileStorage(ABC):
    """
    System-wide abstract file storage service to ensure Day 2 readiness
    for S3/GCS while allowing local storage for Day 1.
    """
    
    @abstractmethod
    async def upload(self, file_name: str, file_stream: BinaryIO, content_type: str) -> str:
        """Uploads a file and returns the system URI."""
        pass

    @abstractmethod
    async def download(self, file_uri: str) -> BinaryIO:
        """Downloads a file by system URI."""
        pass
