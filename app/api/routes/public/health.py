"""Health check endpoints for monitoring service status"""
from fastapi import APIRouter, status
from app.services.cache_service import get_cache_service
from app.db.base import get_db_session
from sqlalchemy import text
import redis
from app.core.config import settings
from datetime import datetime, timezone

health_router = APIRouter(
    prefix="/v1",
    tags=["health"],
)


@health_router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description="Check if the API is responsive"
)
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "discovery-api"
    }


@health_router.get(
    "/health/detailed",
    status_code=status.HTTP_200_OK,
    summary="Detailed health check",
    description="Check all service dependencies including database and Redis"
)
async def detailed_health_check():
    """Detailed health check including all dependencies"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "discovery-api",
        "dependencies": {}
    }
    
    # Check database
    try:
        db = next(get_db_session())
        db.execute(text("SELECT 1"))
        db.close()
        health_status["dependencies"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
    
    # Check Redis (Celery broker)
    try:
        # Handle SSL connections
        conn_params = {}
        if settings.celery_broker_url.startswith("rediss://"):
            conn_params["ssl_cert_reqs"] = "none"
        
        broker_client = redis.from_url(settings.celery_broker_url, **conn_params)
        broker_client.ping()
        health_status["dependencies"]["celery_broker"] = {
            "status": "healthy",
            "message": "Celery broker (Redis) connection successful"
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["celery_broker"] = {
            "status": "unhealthy",
            "message": f"Celery broker connection failed: {str(e)}"
        }
    
    # Check Redis (Cache - db 2)
    try:
        cache_service = get_cache_service()
        if cache_service.redis_client:
            cache_service.redis_client.ping()
            # Try to write and read a test value
            test_key = "health:check"
            test_value = {"timestamp": datetime.now(timezone.utc).isoformat()}
            cache_service.cache_response(test_key, test_value)
            retrieved = cache_service.get_cached_response(test_key)
            cache_service.delete_cached_response(test_key)
            
            if retrieved:
                health_status["dependencies"]["cache"] = {
                    "status": "healthy",
                    "message": "Cache (Redis db 2) connection successful",
                    "redis_url": cache_service.redis_url,
                    "write_read_test": "passed"
                }
            else:
                health_status["status"] = "unhealthy"
                health_status["dependencies"]["cache"] = {
                    "status": "unhealthy",
                    "message": "Cache write/read test failed",
                    "redis_url": cache_service.redis_url
                }
        else:
            health_status["status"] = "unhealthy"
            health_status["dependencies"]["cache"] = {
                "status": "unhealthy",
                "message": "Cache Redis client not initialized"
            }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["cache"] = {
            "status": "unhealthy",
            "message": f"Cache connection failed: {str(e)}"
        }
    
    # Check Pinecone (if configured)
    try:
        if hasattr(settings, 'PINECONE_API_KEY') and settings.PINECONE_API_KEY:
            health_status["dependencies"]["pinecone"] = {
                "status": "healthy",
                "message": "Pinecone API key configured",
                "dense_index": settings.PINECONE_DENSE_INDEX,
                "sparse_index": settings.PINECONE_SPARSE_INDEX
            }
        else:
            health_status["dependencies"]["pinecone"] = {
                "status": "warning",
                "message": "Pinecone API key not configured"
            }
    except Exception as e:
        health_status["dependencies"]["pinecone"] = {
            "status": "warning",
            "message": f"Could not check Pinecone config: {str(e)}"
        }
    
    return health_status