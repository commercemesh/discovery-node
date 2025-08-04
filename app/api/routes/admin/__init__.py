from .products import products_admin_router
from .organizations import organizations_admin_router
from .analytics import analytics_router

admin_routers = [
    ("products", products_admin_router),
    ("organizations", organizations_admin_router),
    ("analytics", analytics_router),
]

__all__ = ["admin_routers"]