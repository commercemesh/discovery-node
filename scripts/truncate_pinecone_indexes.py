#!/usr/bin/env python3
"""
Pinecone index truncation script for CMP Discovery Node
Deletes all vectors from existing indexes without removing the indexes themselves
"""

import os
import sys
import logging
from pinecone import Pinecone
from typing import Optional
from app.core.config import settings

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PineconeIndexTruncate:
    def __init__(self):
        self.api_key = settings.PINECONE_API_KEY
        self.environment = settings.PINECONE_ENVIRONMENT
        self.cloud = settings.PINECONE_CLOUD
        self.region = settings.PINECONE_REGION
        self.dense_index_name = settings.PINECONE_DENSE_INDEX
        self.sparse_index_name = settings.PINECONE_SPARSE_INDEX
        self.namespace = settings.PINECONE_NAMESPACE

        if not self.api_key:
            raise ValueError("PINECONE_API_KEY environment variable required")

        self.pinecone_client = Pinecone(api_key=self.api_key)

    def truncate_dense_index(self) -> bool:
        """Truncate (delete all vectors from) the dense index"""

        try:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.pinecone_client.list_indexes()]
            if self.dense_index_name not in existing_indexes:
                logger.warning(
                    f"Index {self.dense_index_name} does not exist, nothing to truncate"
                )
                return False

            logger.info(f"Truncating Pinecone index: {self.dense_index_name}")

            # Get index reference
            index = self.pinecone_client.Index(self.dense_index_name)
            
            # Get current stats before truncation
            stats_before = index.describe_index_stats()
            logger.info(f"Stats before truncation: {stats_before}")
            
            # Delete all vectors from the namespace
            index.delete(delete_all=True, namespace=self.namespace)
            
            # Verify truncation
            stats_after = index.describe_index_stats()
            logger.info(f"Stats after truncation: {stats_after}")

            logger.info(
                f"Index {self.dense_index_name} truncated successfully"
            )
            return True

        except Exception as e:
            logger.error(f"Error truncating index {self.dense_index_name}: {e}")
            raise

    def truncate_sparse_index(self) -> bool:
        """Truncate (delete all vectors from) the sparse index"""

        try:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.pinecone_client.list_indexes()]
            if self.sparse_index_name not in existing_indexes:
                logger.warning(
                    f"Index {self.sparse_index_name} does not exist, nothing to truncate"
                )
                return False

            logger.info(f"Truncating Pinecone index: {self.sparse_index_name}")

            # Get index reference
            index = self.pinecone_client.Index(self.sparse_index_name)
            
            # Get current stats before truncation
            stats_before = index.describe_index_stats()
            logger.info(f"Stats before truncation: {stats_before}")
            
            # Delete all vectors from the namespace
            index.delete(delete_all=True, namespace=self.namespace)
            
            # Verify truncation
            stats_after = index.describe_index_stats()
            logger.info(f"Stats after truncation: {stats_after}")

            logger.info(
                f"Index {self.sparse_index_name} truncated successfully"
            )
            return True

        except Exception as e:
            logger.error(f"Error truncating index {self.sparse_index_name}: {e}")
            raise

    def verify_truncation(self) -> bool:
        """Verify the indexes are empty"""
        try:
            # Check dense index
            index = self.pinecone_client.Index(self.dense_index_name)
            stats = index.describe_index_stats()
            dense_count = stats.get("namespaces", {}).get(self.namespace, {}).get("vector_count", 0)
            logger.info(f"Dense index {self.dense_index_name} vector count: {dense_count}")
            
            # Check sparse index
            index = self.pinecone_client.Index(self.sparse_index_name)
            stats = index.describe_index_stats()
            sparse_count = stats.get("namespaces", {}).get(self.namespace, {}).get("vector_count", 0)
            logger.info(f"Sparse index {self.sparse_index_name} vector count: {sparse_count}")
            
            if dense_count == 0 and sparse_count == 0:
                logger.info("✅ Both indexes successfully truncated")
                return True
            else:
                logger.warning(f"⚠️ Indexes may not be fully truncated - dense: {dense_count}, sparse: {sparse_count}")
                return False
                
        except Exception as e:
            logger.error(f"Truncation verification failed: {e}")
            return False


def main():
    """Main truncation function"""
    try:
        truncate = PineconeIndexTruncate()

        logger.info("Starting Pinecone index truncation...")
        logger.info(f"Environment: {truncate.environment}")
        logger.info(f"Cloud: {truncate.cloud}")
        logger.info(f"Region: {truncate.region}")
        logger.info(f"Dense index: {truncate.dense_index_name}")
        logger.info(f"Sparse index: {truncate.sparse_index_name}")
        logger.info(f"Namespace: {truncate.namespace}")

        # Confirm before truncating
        response = input("\n⚠️  WARNING: This will delete ALL vectors from the indexes. Continue? (yes/no): ")
        if response.lower() != "yes":
            logger.info("Truncation cancelled by user")
            return

        # Truncate indexes
        truncate.truncate_dense_index()
        truncate.truncate_sparse_index()

        # Verify truncation
        truncate.verify_truncation()

        logger.info("✅ Pinecone truncation completed!")

    except Exception as e:
        logger.error(f"❌ Truncation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()