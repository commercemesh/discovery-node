from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
from pydantic import ConfigDict

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cmp_discovery"
    )
    DB_MIN_CONNECTIONS: int = int(os.getenv("DB_MIN_CONNECTIONS", "5"))
    DB_MAX_CONNECTIONS: int = int(os.getenv("DB_MAX_CONNECTIONS", "20"))
    DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
    )
    FEED_CHECK_INTERVAL: int = int(os.getenv("FEED_CHECK_INTERVAL", "300"))
    EMBEDDING_UPDATE_INTERVAL: int = int(os.getenv("EMBEDDING_UPDATE_INTERVAL", "3600"))
    CLEANUP_INTERVAL: int = int(os.getenv("CLEANUP_INTERVAL", "3600"))
    DATA_DIR: str = os.getenv(
        "DATA_DIR", "/tmp/discovery-node/"
    )
    TRIGGER_INGESTION_ON_STARTUP: bool = (
        os.getenv("TRIGGER_INGESTION_ON_STARTUP", "false").lower() == "true"
    )
    INGESTION_CONFIG_PATH: str = os.getenv(
        "INGESTION_CONFIG_PATH",
        "/tmp/ingestion.yaml",
    )
    # Other settings
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
    PINECONE_BATCH_SIZE: int = int(os.getenv("PINECONE_BATCH_SIZE", "96"))
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY")
    PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "dev01")
    PINECONE_CLOUD: str = os.getenv("PINECONE_CLOUD", "aws")
    PINECONE_REGION: str = os.getenv("PINECONE_REGION", "us-east-1")
    PINECONE_DENSE_INDEX: str = os.getenv(
        "PINECONE_DENSE_INDEX", "dev01-cmp-discovery-dense"
    )
    PINECONE_SPARSE_INDEX: str = os.getenv(
        "PINECONE_SPARSE_INDEX", "dev01-cmp-discovery-sparse"
    )
    PINECONE_NAMESPACE: str = os.getenv("PINECONE_NAMESPACE", "__default__")
    

    # Vector provider settings
    VECTOR_PROVIDER: str = os.getenv("VECTOR_PROVIDER", "pgvector")  # pgvector (default) or pinecone
    
    # PgVector settings
    PGVECTOR_EMBEDDING_SERVICE_URL: str = os.getenv("PGVECTOR_EMBEDDING_SERVICE_URL", "")
    
    # Embedding model settings for pgvector
    EMBEDDING_MODEL_PROVIDER: str = os.getenv("EMBEDDING_MODEL_PROVIDER", "openai")  # openai, cohere, etc.
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")  # API key for embedding provider
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "1536"))  # 1536 for text-embedding-3-small
    
    # Multi-tenant settings
    MULTI_TENANT_MODE: bool = os.getenv("MULTI_TENANT_MODE", "false").lower() == "true"
    DEFAULT_ORGANIZATION_ID: str = os.getenv("DEFAULT_ORGANIZATION_ID", "")  # Used in single-tenant mode
    
    # CMP URN generation settings
    CMP_NAMESPACE: str = os.getenv("CMP_NAMESPACE", "")  # UUID namespace for deterministic URN generation
    
    # Host configuration for feed URL generation
    HOST: str = os.getenv("HOST", "localhost:8000")  # Host for feed URL generation
    
    # S3 settings for managed ingestion
    AWS_S3_BUCKET_NAME: str = os.getenv("AWS_S3_BUCKET_NAME", "")  # S3 bucket for managed feeds
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    

    @property
    def celery_broker_url(self) -> str:
        """Get Celery broker URL with database 0"""
        url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        # If no database specified, append /0
        if "/" not in url.split("://")[1].split("@")[-1]:
            return f"{url}/0"
        return url
    
    @property
    def celery_result_backend(self) -> str:
        """Get Celery result backend URL with database 0"""
        url = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        # If no database specified, append /0
        if "/" not in url.split("://")[1].split("@")[-1]:
            return f"{url}/0"
        return url
    
    @property
    def mcp_redis_url(self) -> str:
        """Get MCP Redis URL with database 1 for isolation"""
        url = os.getenv("MCP_REDIS_URL", "redis://localhost:6379/1")
        # If no database specified, append /1
        if "/" not in url.split("://")[1].split("@")[-1]:
            return f"{url}/1"
        return url
    
    @property
    def cache_redis_url(self) -> str:
        """Get Cache Redis URL with database 2 for isolation"""
        url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/2")
        # If no database specified, append /2
        if "/" not in url.split("://")[1].split("@")[-1]:
            return f"{url}/2"
        return url

    model_config = ConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
