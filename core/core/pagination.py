import os
from fastapi import Query


class PaginationParams:
    """
    Reusable FastAPI dependency for pagination.

    MAX_PAGE_SIZE is read from the MAX_PAGE_SIZE env var (default: 200),
    allowing instance-level overrides without code changes.

    Usage in routes:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            stmt = select(Item).offset(pagination.offset).limit(pagination.limit)
    """
    MAX_PAGE_SIZE: int = int(os.getenv("MAX_PAGE_SIZE", "200"))

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(50, ge=1, le=200, description="Items per page (max set by MAX_PAGE_SIZE env)")
    ):
        self.page = page
        self.page_size = min(page_size, self.MAX_PAGE_SIZE)
        self.offset = (page - 1) * self.page_size
        self.limit = self.page_size
