from app.api.v1.documents import router as documents_router
from app.api.v1.query import router as query_router
from app.api.v1.upload import router as upload_router

__all__ = ["documents_router", "query_router", "upload_router"]
