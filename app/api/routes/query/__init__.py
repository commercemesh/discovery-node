from .search import search_router
from .products import products_router
from .filter import filter_router
from .compare import compare_router
from .cache import cache_router
from .feed import feed_router

query_routers = [
    ("search", search_router),
    ("products", products_router),
    ("filter", filter_router),
    ("compare", compare_router),
    ("cache", cache_router),
    ("feed", feed_router),
]

__all__ = ["query_routers"]