from fastapi import Query


class PaginationParams:
    """
    Reusable FastAPI dependency for pagination.
    
    Usage in routes:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            stmt = select(Item).offset(pagination.offset).limit(pagination.limit)
    """
    MAX_PAGE_SIZE = 200

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(50, ge=1, le=200, description="Items per page (max 200)")
    ):
        self.page = page
        self.page_size = min(page_size, self.MAX_PAGE_SIZE)
        self.offset = (page - 1) * self.page_size
        self.limit = self.page_size
