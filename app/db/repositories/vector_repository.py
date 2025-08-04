import time
import random
import requests
import logging
from pinecone import Pinecone, ServerlessSpec
from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorRepository:
    def __init__(self):
        self.pinecone = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.batch_size = settings.PINECONE_BATCH_SIZE or 96
        self.dense_index = self.pinecone.Index(settings.PINECONE_DENSE_INDEX)
        self.sparse_index = self.pinecone.Index(settings.PINECONE_SPARSE_INDEX)
        self.namespace = settings.PINECONE_NAMESPACE

    def _retry_with_backoff(self, func, max_retries=3):
        for attempt in range(max_retries):
            try:
                result = func()
                return result
            except Exception as e:
                if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = (2**attempt) + random.uniform(0, 1)
                        logger.warning(
                            f"Rate limit hit, retrying in {wait_time:.2f} seconds (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                raise e
        return func()  # Final attempt

    def _batch_upsert(self, index, records: list[dict]):
        """Upsert records into the given Pinecone index in batches with rate limit handling."""
        for i in range(0, len(records), self.batch_size):
            batch = records[i : i + self.batch_size]
            self._retry_with_backoff(
                lambda b=batch: index.upsert_records(namespace="__default__", records=b)
            )

    def upsert_products_into_dense_index(self, records: list[dict]):
        """Upsert products into Pinecone dense index with rate limit handling, in batches"""
        self._batch_upsert(self.dense_index, records)

    def upsert_products_into_sparse_index(self, records: list[dict]):
        """Upsert products into Pinecone sparse index with rate limit handling, in batches"""
        self._batch_upsert(self.sparse_index, records)

    def _search_products(
        self,
        query: str,
        top_k: int = 20,
        alpha: float = 0.7,
        include_metadata: bool = True,
        filter: dict = None,
    ):
        """Search for products using Pinecone's Inference API"""
        start_time = time.time()
        logger.info("🔍 Starting dense index query with inference...")
        logger.info(f"the query is {query}")

        try:
            # Build search query
            search_query = {"top_k": top_k, "inputs": {"text": query}}
            if filter:
                search_query["filter"] = filter
                
            results = self.dense_index.search(
                namespace=self.namespace, query=search_query
            )

            query_time = time.time() - start_time
            logger.info(f"✅ Dense query completed in {query_time:.3f}s")

            return results

        except Exception as e:
            logger.error(f"❌ Dense query failed: {str(e)}")
            raise

    def _search_dense_index(
        self,
        query: str,
        top_k: int = 20,
        alpha: float = 0.7,
        include_metadata: bool = True,
        filter: dict = None,
    ):
        """Search for products using Pinecone's dense index"""
        return self._search_products(query, top_k, alpha, include_metadata, filter)

    def _search_sparse_index(
        self,
        query: str,
        top_k: int = 20,
        alpha: float = 0.7,
        include_metadata: bool = True,
        filter: dict = None,
    ):
        """Search for products using Pinecone's sparse index"""
        start_time = time.time()
        logger.info("🔍 Starting sparse index query with inference...")
        logger.info(f"the query is {query}")

        try:
            # Build search query
            search_query = {"top_k": top_k, "inputs": {"text": query}}
            if filter:
                search_query["filter"] = filter
                
            results = self.sparse_index.search(
                namespace=self.namespace, query=search_query
            )

            query_time = time.time() - start_time
            logger.info(f"✅ Sparse query completed in {query_time:.3f}s")

            return results

        except Exception as e:
            logger.error(f"❌ Sparse query failed: {str(e)}")
            raise
