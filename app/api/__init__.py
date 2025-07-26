from .routes.search import search_router
from .routes.products import products_router
from .routes.cache import cache_router
from .routes.filter import filter_router
from .routes.compare import compare_router

__all__ = ["search_router", "products_router", "cache_router", "filter_router", "compare_router"]
