import boto3
import json
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Reader:
    """S3 storage reader for managed ingestion"""
    
    def __init__(self):
        """Initialize S3 client"""
        self.s3_client = None
        if settings.AWS_S3_BUCKET_NAME:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
        self.bucket_name = settings.AWS_S3_BUCKET_NAME
    
    def get_feed_path_from_org_url(self, org_url: str) -> str:
        """
        Generate S3 path from organization URL
        Example: https://www.example.com -> www.example.com/feed.json
        """
        # Parse the URL and extract domain
        parsed = urlparse(org_url)
        domain = parsed.netloc
        
        # If no netloc found, try to parse as if it's just a domain
        if not domain:
            # Remove protocol if present
            clean_url = org_url.replace('http://', '').replace('https://', '')
            # Remove path and query parameters
            domain = clean_url.split('/')[0].split('?')[0]
        
        if not domain:
            raise ValueError(f"Could not extract domain from URL: {org_url}")
        
        # Return the S3 key path
        return f"{domain}/feed.json"
    
    def read_feed(self, org_url: str) -> Optional[Dict[str, Any]]:
        """
        Read feed.json from S3 for given organization URL
        
        Args:
            org_url: Organization URL (e.g., https://www.example.com)
            
        Returns:
            Parsed JSON content of feed.json or None if not found
        """
        if not self.s3_client:
            logger.error("S3 client not initialized. Check AWS_S3_BUCKET_NAME configuration.")
            return None
        
        try:
            # Get S3 key from org URL
            s3_key = self.get_feed_path_from_org_url(org_url)
            logger.info(f"Reading feed from S3: s3://{self.bucket_name}/{s3_key}")
            
            # Get object from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            # Read and parse JSON content
            content = response['Body'].read().decode('utf-8')
            feed_data = json.loads(content)
            
            logger.info(f"Successfully read feed from S3 for {org_url}")
            return feed_data
            
        except self.s3_client.exceptions.NoSuchKey:
            logger.warning(f"Feed not found in S3 for {org_url} at {s3_key}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in feed for {org_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading feed from S3 for {org_url}: {e}")
            return None
    
    def read_feed_shard(self, org_url: str, shard_filename: str) -> Optional[Dict[str, Any]]:
        """
        Read a feed shard file from S3
        
        Args:
            org_url: Organization URL
            shard_filename: Name of the shard file (e.g., feed-001.json)
            
        Returns:
            Parsed JSON content of shard file or None if not found
        """
        if not self.s3_client:
            logger.error("S3 client not initialized. Check AWS_S3_BUCKET_NAME configuration.")
            return None
        
        try:
            # Get base path from org URL
            parsed = urlparse(org_url)
            domain = parsed.netloc or org_url.replace('http://', '').replace('https://', '').split('/')[0]
            
            # Construct S3 key for shard
            s3_key = f"{domain}/{shard_filename}"
            logger.debug(f"Reading shard from S3: s3://{self.bucket_name}/{s3_key}")
            
            # Get object from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            # Read and parse JSON content
            content = response['Body'].read().decode('utf-8')
            shard_data = json.loads(content)
            
            return shard_data
            
        except self.s3_client.exceptions.NoSuchKey:
            logger.warning(f"Shard {shard_filename} not found in S3 for {org_url}")
            return None
        except Exception as e:
            logger.error(f"Error reading shard {shard_filename} from S3 for {org_url}: {e}")
            return None