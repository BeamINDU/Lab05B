from .products import router as products_routes
from .packages import router as packages_routes
from .orders import router as orders_routes
from .simulation import router as simulate_routes
from .reports import router as reports_routes
from .tasks import router as tasks_routes

__all__ = [
    "products_routes",
    "packages_routes",
    "orders_routes",
    "simulate_routes",
    "reports_routes",
    "tasks_routes",
]
