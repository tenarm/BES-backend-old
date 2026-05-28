"""Comments — Threaded comment service for any entity."""
from .models import EntityComment
from .service import CommentService

__all__ = ["EntityComment", "CommentService"]
