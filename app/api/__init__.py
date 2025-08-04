# Query/Discovery routers (read-only)
from .routes.query import query_routers

# Admin routers (CRUD operations)
from .routes.admin import admin_routers

# Public routers
from .routes.public import public_routers

__all__ = ["query_routers", "admin_routers", "public_routers"]
