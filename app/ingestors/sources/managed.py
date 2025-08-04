# app/ingestors/sources/managed.py
"""
Managed source implementation for S3-based feeds.
"""
import logging
import json
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.ingestors.sources.base import BaseSource
from app.ingestors.base import SourceError
from app.storage.s3_reader import S3Reader
from app.db.base import get_db_session
from app.services.organization_service import OrganizationService

logger = logging.getLogger(__name__)


class ManagedSource(BaseSource):
    """
    Source for managed feeds stored in S3.
    Reads feeds for all organizations in the database.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the managed source with configuration.

        Args:
            config: Configuration dictionary (not used for managed source)
        """
        super().__init__(config)
        self.s3_reader = S3Reader()
        
    def fetch_feed_index(self, ingestor_config: Dict[str, Any]) -> str:
        """
        Fetch feed data from S3 for all organizations in the database.
        
        Returns:
            JSON string containing array of feed data for all organizations
        """
        logger.info("Fetching managed feeds from S3 for all organizations")
        print("Fetching managed feeds from S3 for all organizations")
        
        try:
            # Get database session
            db = next(get_db_session())
            org_service = OrganizationService(db)
            
            # Get all organizations
            organizations = org_service.list_organizations(skip=0, limit=1000)
            logger.info(f"Found {len(organizations)} organizations to process")
            print(f"Found {len(organizations)} organizations to process")
            
            # Fetch feed data for each organization
            feed_data_array = []
            
            for org in organizations:
                org_name = org.name
                org_url = org.url
                org_urn = org.urn
                
                logger.info(f"Processing organization: {org_name} ({org_url})")
                print(f"Processing organization: {org_name} ({org_url})")
                
                try:
                    # Read feed from S3 using organization URL
                    feed_data = self.s3_reader.read_feed(org_url)
                    
                    if feed_data:
                        # Add organization context to feed data
                        feed_with_context = {
                            "organization": {
                                "name": org_name,
                                "urn": org_urn
                            },
                            "feed_data": feed_data
                        }
                        
                        feed_data_array.append(feed_with_context)
                        logger.info(f"Successfully fetched feed for organization: {org_name}")
                        print(f"Successfully fetched feed for organization: {org_name}")
                    else:
                        logger.warning(f"No feed found for organization: {org_name}")
                        print(f"No feed found for organization: {org_name}")
                        
                except Exception as e:
                    logger.error(f"Error fetching feed for organization {org_name}: {str(e)}")
                    print(f"Error fetching feed for organization {org_name}: {str(e)}")
                    continue
            
            logger.info(f"Successfully fetched feeds for {len(feed_data_array)} organizations")
            print(f"Successfully fetched feeds for {len(feed_data_array)} organizations")
            
            # Return feed data as JSON string
            if len(feed_data_array) == 0:
                logger.warning("No feeds found for any organization")
                return "[]"
            elif len(feed_data_array) == 1:
                # Single organization - return just the feed data
                return json.dumps(feed_data_array[0]["feed_data"])
            else:
                # Multiple organizations - return array of feed data
                feed_indexes = []
                for org_feed in feed_data_array:
                    feed_indexes.append(org_feed["feed_data"])
                return json.dumps(feed_indexes)
                
        except Exception as e:
            logger.exception(f"Error fetching managed feeds: {str(e)}")
            raise SourceError(f"Error fetching managed feeds: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()
    
    def fetch_registry(self, path: str) -> str:
        """
        Fetch registry data. For managed source, we generate registry from database.
        
        Returns:
            JSON string containing registry data for all organizations
        """
        logger.info("Generating registry data from database for managed source")
        
        try:
            # Get database session
            db = next(get_db_session())
            org_service = OrganizationService(db)
            
            # Get all organizations and build registry
            organizations = org_service.list_organizations(skip=0, limit=1000)
            
            registry_data = []
            for org in organizations:
                org_data = {
                    "@type": "Organization",
                    "name": org.name,
                    "url": org.url,
                    "identifier": {
                        "@type": "PropertyValue",
                        "propertyID": "urn",
                        "value": org.urn
                    }
                }
                
                # Add logo if available
                if org.logo_url:
                    org_data["logo"] = org.logo_url
                
                # Add description if available
                if org.description:
                    org_data["description"] = org.description
                
                # Add feed URL (S3 path)
                if org.url:
                    feed_path = self.s3_reader.get_feed_path_from_org_url(org.url)
                    org_data["cmp:productFeed"] = {
                        "url": f"s3://{self.s3_reader.bucket_name}/{feed_path}"
                    }
                
                registry_data.append(org_data)
            
            return json.dumps(registry_data)
            
        except Exception as e:
            logger.exception(f"Error generating registry data: {str(e)}")
            raise SourceError(f"Error generating registry data: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()
    
    def fetch_feed(self, path: str) -> str:
        """
        Fetch a specific feed from S3.
        
        Args:
            path: S3 path or organization URL
            
        Returns:
            Feed data as JSON string
        """
        logger.info(f"Fetching managed feed from S3: {path}")
        
        try:
            # If path starts with s3://, extract the key
            if path.startswith("s3://"):
                # Extract bucket and key from S3 URL
                # Format: s3://bucket-name/domain/feed.json
                parts = path.replace("s3://", "").split("/", 1)
                if len(parts) > 1:
                    # Extract domain from key
                    domain = parts[1].split("/")[0]
                    # Use domain as org URL for S3 reader
                    path = f"https://{domain}"
            
            # Read feed using organization URL
            feed_data = self.s3_reader.read_feed(path)
            
            if feed_data:
                return json.dumps(feed_data)
            else:
                logger.warning(f"No feed found at path: {path}")
                return "{}"
                
        except Exception as e:
            logger.warning(f"Error fetching feed from {path}: {str(e)}")
            return "{}"
    
    def get_feed_path(self) -> str:
        """
        Get the feed path. Not used for managed source.
        
        Returns:
            Empty string
        """
        return ""
    
    def get_org_urn(self, data: dict) -> str:
        """
        Get the organization URN from the data.
        
        Args:
            data: Organization data dictionary
            
        Returns:
            Organization URN string
        """
        try:
            if data.get("@type") == "Organization":
                identifier = data.get("identifier", {})
                if isinstance(identifier, dict):
                    return identifier.get("value", "")
            return ""
        except Exception:
            return ""
    
    def validate_connection(self) -> bool:
        """
        Validate that the S3 bucket is accessible.
        
        Returns:
            True if S3 bucket is configured, False otherwise
        """
        logger.info("Validating managed source S3 access")
        
        try:
            # Check if S3 is configured
            if not self.s3_reader.bucket_name:
                logger.warning("S3 bucket not configured")
                return False
            
            # Check if S3 client is initialized
            if not self.s3_reader.s3_client:
                logger.warning("S3 client not initialized")
                return False
            
            # Try to list objects (limit to 1) to test connectivity
            try:
                self.s3_reader.s3_client.list_objects_v2(
                    Bucket=self.s3_reader.bucket_name,
                    MaxKeys=1
                )
                logger.info("S3 bucket is accessible")
                return True
            except Exception as e:
                logger.warning(f"S3 bucket not accessible: {str(e)}")
                return False
                
        except Exception as e:
            logger.warning(f"Error validating S3 access: {str(e)}")
            return False