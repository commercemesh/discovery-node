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
        "DATA_DIR", "/Users/shiv/Documents/CMP/new/discovery-node/"
    )
    TRIGGER_INGESTION_ON_STARTUP: bool = (
        os.getenv("TRIGGER_INGESTION_ON_STARTUP", "false").lower() == "true"
    )
    INGESTION_CONFIG_PATH: str = os.getenv(
        "INGESTION_CONFIG_PATH",
        "/Users/shiv/Documents/CMP/new/discovery-node/ingestion.yaml",
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
    MCP_REDIS_URL: str = os.getenv("MCP_REDIS_URL", "redis://localhost:6379/1")
    
    @property
    def mcp_redis_url(self) -> str:
        """Get MCP Redis URL with database 1 for isolation"""
        base_url = os.getenv("MCP_REDIS_URL", "redis://localhost:6379/1")
        # If no database specified, use database 1 for MCP
        if "/" not in base_url.split("://")[1]:
            return f"{base_url}/1"
        return base_url

    model_config = ConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
