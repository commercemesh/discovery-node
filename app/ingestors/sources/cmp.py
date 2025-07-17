# app/ingestors/sources/cmp.py
"""
CMP (Commerce Mesh Protocol) source implementation.
"""
import logging
import requests
import json
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.ingestors.sources.base import BaseSource
from app.ingestors.base import SourceError, ValidationError

logger = logging.getLogger(__name__)


class CMPSource(BaseSource):
    """
    Source for CMP (Commerce Mesh Protocol) feeds.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the CMP source with configuration.

        Args:
            config: Configuration dictionary containing registry URL and filters
        """
        super().__init__(config)
        self.registry_url = self.config.get("registry")
        self.filters = self.config.get("filter", {})


    def _convert_github_url(self, url: str) -> str:
        """
        Convert GitHub blob URL to raw URL.
        
        Args:
            url: GitHub URL (blob or raw)
            
        Returns:
            Raw GitHub URL
        """
        if "github.com" in url and "/blob/" in url:
            # Convert blob URL to raw URL
            raw_url = url.replace("/blob/", "/raw/")
            return raw_url
        return url
    

    def fetch_feed_index(self, ingestor_config: Dict[str, Any]) -> str:
        """
        Fetch data from CMP product feeds for matching organizations.
        """
        logger.info("Fetching CMP product feeds for matching organizations")
        print("Fetching CMP product feeds for matching organizations")
        
        try:
            # Get registry data
            registry_data = self.fetch_registry(ingestor_config.get("registry"))
            registry_data = json.loads(registry_data)

            # Filter registry data based on ingestor_config
            filtered_data = self._filter_registry(registry_data, ingestor_config)
            
            # Extract organizations from filtered data
            organizations = []
            if isinstance(filtered_data, list):
                organizations = filtered_data
            elif isinstance(filtered_data, dict):
                if filtered_data.get("@type") == "Organization":
                    organizations = [filtered_data]
                elif "organizations" in filtered_data:
                    organizations = filtered_data["organizations"]
                elif "brands" in filtered_data:
                    organizations = filtered_data["brands"]
                else:
                    organizations = [filtered_data]
            
            # Fetch feed data for each organization
            feed_data_array = []
            
            for org in organizations:
                org_name = org.get('name', 'Unknown')
                logger.info(f"Fetching feed for organization: {org_name}")
                print(f"Fetching feed for organization: {org_name}")
                
                # Get feed URL from organization data
                feed_info = org.get("cmp:productFeed", {})
                feed_url = feed_info.get("url") if isinstance(feed_info, dict) else None
                
                if not feed_url:
                    logger.warning(f"No feed URL found for organization: {org_name}")
                    continue
                
                try:
                    # Fetch feed data using HTTP request
                    raw_url = self._convert_github_url(feed_url)
                    response = requests.get(raw_url, timeout=30)
                    response.raise_for_status()
                    feed_data = response.text
                    feed_json = json.loads(feed_data)
                    
                    # Add organization context to feed data
                    feed_with_context = {
                        "organization": {
                            "name": org_name,
                            "urn": self.get_org_urn(org)
                        },
                        "feed_data": feed_json
                    }
                    
                    feed_data_array.append(feed_with_context)
                    logger.info(f"Successfully fetched feed for organization: {org_name}")
                    print(f"Successfully fetched feed for organization: {org_name}")
                    
                except Exception as e:
                    logger.error(f"Error fetching feed for organization {org_name}: {str(e)}")
                    print(f"Error fetching feed for organization {org_name}: {str(e)}")
                    continue
            
            # Return feed data as JSON string
            if len(feed_data_array) == 1:
                # Single organization - return just the feed data
                return json.dumps(feed_data_array[0]["feed_data"])
            else:
                # Multiple organizations - return array of ProductFeedIndex objects
                # Extract just the feed_data from each organization
                feed_indexes = []
                for org_feed in feed_data_array:
                    feed_indexes.append(org_feed["feed_data"])
                return json.dumps(feed_indexes)
                
        except Exception as e:
            logger.exception(f"Error fetching CMP feeds: {str(e)}")
            raise SourceError(f"Error fetching CMP feeds: {str(e)}")

    def _filter_registry(self, registry_data: Dict[str, Any], ingestor_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter registry data based on organization identifiers in ingestor_config.
        
        Args:
            registry_data: Registry data containing organizations
            ingestor_config: Configuration with filter criteria
            
        Returns:
            Filtered registry data containing only matching organizations
        """
        logger.info("Filtering registry data based on organization identifiers")
        
        try:
            # Get filter configuration
            filter_config = ingestor_config.get("filter", {})
            target_org_urns = filter_config.get("organization", [])
            
            if not target_org_urns:
                logger.warning("No organization filters specified, returning all data")
                return registry_data
            
            logger.info(f"Filtering for organizations: {target_org_urns}")
            print(f"Filtering for organizations: {target_org_urns}")
            
            # Handle different registry formats
            organizations = []
            
            if isinstance(registry_data, list):
                # Registry is a list of organizations
                organizations = registry_data
            elif isinstance(registry_data, dict):
                if registry_data.get("@type") == "Organization":
                    # Single organization
                    organizations = [registry_data]
                elif "organizations" in registry_data:
                    # Registry contains organizations array
                    organizations = registry_data["organizations"]
                else:
                    # Assume it's a single organization
                    organizations = [registry_data]
            
            # Filter organizations based on URN
            filtered_organizations = []
            
            for org in organizations:
                org_urn = self.get_org_urn(org)
                if org_urn in target_org_urns:
                    filtered_organizations.append(org)
                    logger.info(f"Matched organization: {org.get('name', 'Unknown')} with URN: {org_urn}")
                    print(f"Matched organization: {org.get('name', 'Unknown')} with URN: {org_urn}")
            
            logger.info(f"Found {len(filtered_organizations)} matching organizations")
            print(f"Found {len(filtered_organizations)} matching organizations")
            
            # Return filtered data in the same format as input
            if isinstance(registry_data, list):
                return filtered_organizations
            elif isinstance(registry_data, dict):
                if registry_data.get("@type") == "Organization":
                    # Return first matching organization as single org
                    return filtered_organizations[0] if filtered_organizations else {}
                elif "organizations" in registry_data:
                    # Return with organizations array
                    return {"organizations": filtered_organizations}
                elif "brands" in registry_data:
                    # Return with brands array
                    return {"brands": filtered_organizations}
                else:
                    # Return first matching organization
                    return filtered_organizations[0] if filtered_organizations else {}
            
            return filtered_organizations
            
        except Exception as e:
            logger.exception(f"Error filtering registry data: {str(e)}")
            raise SourceError(f"Error filtering registry data: {str(e)}")
    
    def fetch_registry(self, path: str) -> str:
        """
        Fetch data from a CMP registry.
        """
        logger.info(f"Fetching data from CMP source: {path}")
        print(f"Fetching data from CMP source: {path}")

        try:
            # Convert GitHub blob URL to raw URL if needed
            raw_url = self._convert_github_url(path)
            
            # Make HTTP request
            response = requests.get(raw_url, timeout=30)
            response.raise_for_status()
            
            return response.text

        except requests.RequestException as e:
            logger.exception(f"Error fetching CMP data from {path}: {str(e)}")
            raise SourceError(f"Error fetching CMP data: {str(e)}")
        except Exception as e:
            logger.exception(f"Error fetching CMP data from {path}: {str(e)}")
            raise SourceError(f"Error fetching CMP data: {str(e)}")

    def fetch_feed(self, path: str) -> str:
        """
        Fetch data from a CMP feed URL.
        
        Args:
            path: URL to the feed data
            
        Returns:
            Feed data as JSON string, or empty object if error
        """
        logger.info(f"Fetching data from CMP feed: {path}")
        print(f"Fetching data from CMP feed: {path}")

        try:
            # Convert GitHub blob URL to raw URL if needed
            raw_url = self._convert_github_url(path)
            
            # Make HTTP request
            response = requests.get(raw_url, timeout=30)
            
            # Check if response is successful
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"HTTP {response.status_code} for URL: {path}")
                print(f"HTTP {response.status_code} for URL: {path}")
                return "{}"  # Return empty object
                
        except requests.RequestException as e:
            logger.warning(f"Request error for URL {path}: {str(e)}")
            print(f"Request error for URL {path}: {str(e)}")
            return "{}"  # Return empty object
        except Exception as e:
            logger.warning(f"Error fetching feed from {path}: {str(e)}")
            print(f"Error fetching feed from {path}: {str(e)}")
            return "{}"  # Return empty object
    

    

    def get_feed_path(self) -> str:
        """
        Get the feed path from the configuration.
        
        Returns:
            Feed path string
            
        Raises:
            SourceError: If feed_path is not configured
        """
        feed_path = self.config.get("feed_path")
        if not feed_path:
            raise SourceError("feed_path not configured in source configuration")
        return feed_path

    def get_org_urn(self, data: dict) -> str:
        """
        Get the organization URN from the CMP data.

        Args:
            data: CMP data dictionary

        Returns:
            Organization URN string
        """
        logger.info("Getting organization URN from CMP data")
        print("Getting organization URN from CMP data")

        try:
            # Check if this is an organization object
            if data.get("@type") == "Organization":
                identifier = data.get("identifier", {})
                
                if isinstance(identifier, dict):
                    value = identifier.get("value")
                    if value and (value.startswith("urn:cmp:org:")):
                        logger.info(f"Found organization URN: {value}")
                        print(f"Found organization URN: {value}")
                        return value
                    else:
                        logger.warning(f"Invalid organization URN format: {value}")
                        print(f"Invalid organization URN format: {value}")
                        return None
                else:
                    logger.warning(f"Identifier is not a dict, it's: {type(identifier)}")
                    print(f"Identifier is not a dict, it's: {type(identifier)}")
                    return None
            else:
                logger.warning(f"Data is not an Organization, @type is: {data.get('@type')}")
                print(f"Data is not an Organization, @type is: {data.get('@type')}")
                return None
        except (KeyError, AttributeError) as e:
            logger.error(f"Exception in getting org URN: {e}")
            print(f"Exception in getting org URN: {e}")
            return None

    def validate_connection(self) -> bool:
        """
        Validate that the CMP source is accessible.

        Returns:
            True if the CMP source is accessible, False otherwise
        """
        logger.info("Validating CMP source access")
        print("Validating CMP source access")

        try:
            if not self.registry_url:
                logger.warning("No registry URL configured")
                return False
                
            # Test registry URL accessibility
            response = requests.head(self._convert_github_url(self.registry_url), timeout=10)
            return response.status_code == 200

        except Exception as e:
            logger.warning(f"CMP source not accessible: {str(e)}")
            return False 