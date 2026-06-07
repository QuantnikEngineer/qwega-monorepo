import os
from dotenv import load_dotenv
import logging
import requests
import urllib3


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Disable SSL warnings when SSL verification is disabled
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API base URL for credentials
BUILDAI_BACKEND_API_URL = os.getenv("BUILDAI_BACKEND_API_URL")
if not BUILDAI_BACKEND_API_URL:
    raise RuntimeError("BUILDAI_BACKEND_API_URL environment variable must be set to reach the credentials service")
BUILDAI_BACKEND_API_URL = BUILDAI_BACKEND_API_URL.rstrip("/")
CREDENTIALS_API_BASE_URL = f"{BUILDAI_BACKEND_API_URL}/v1.0/connectors/credentials"

# Module-level SSL verification setting (default: False)
_VERIFY_SSL = False

# Global context for secrets retrieval
_PROJECT_ID: str | None = None
_CLOUD_PROVIDER: str | None = None

def init_secrets_context(project_id: str | None = None, cloud_provider: str | None = None):
    """Initialize default context for secrets retrieval.

    Args:
        project_id: Default project id for connector secrets when not provided explicitly.
        cloud_provider: Default cloud provider (e.g., 'azure', 'aws', 'gcp').
    """
    global _PROJECT_ID, _CLOUD_PROVIDER
    if project_id:
        _PROJECT_ID = project_id
        logger.info(f"[secrets] context project_id set to '{_PROJECT_ID}'")
    if cloud_provider:
        _CLOUD_PROVIDER = cloud_provider.strip().lower() or os.getenv("CLOUD_PROVIDER").strip().lower()
        logger.info(f"[secrets] context cloud_provider set to '{_CLOUD_PROVIDER}'")

def set_verify_ssl(enabled: bool):
    """Set the SSL verification setting for API requests.
    
    Args:
        enabled: True to enable SSL verification, False to disable
    """
    global _VERIFY_SSL
    _VERIFY_SSL = enabled

def get_verify_ssl() -> bool:
    """Get the current SSL verification setting.
    
    Returns:
        bool: True if SSL verification is enabled, False otherwise
    """
    return _VERIFY_SSL

# Get vault access key value
def get_secret(secret_key, auth_provider=None, default_value=""):
    """
    Get vault access key value. Tries fetching from API endpoint first,
    falls back to environment variable if error or not found.
    
    Args:
        secret_key: Name of the vault key
        auth_provider: Cloud provider (e.g., 'azure', 'aws', 'gcp'). If None, uses global _CLOUD_PROVIDER
        default_value: Default value to return if secret is not found (defaults to empty string)
    
    Returns:
        Key value as string, or default_value if not found
    """
    # Try fetching from API if vaultaccesskey and authprovider are provided
    logger.info(f"start fetching secret")
    
    # Use global _CLOUD_PROVIDER if auth_provider not provided
    provider = auth_provider if auth_provider is not None else _CLOUD_PROVIDER
    
    try:
        # Get SSL verification setting
        verify_ssl = get_verify_ssl()
        
        api_url = f"{CREDENTIALS_API_BASE_URL}/{secret_key}"
        params = {"cloud_provider": provider}
        
        logger.info(f"Fetching secret from API: {api_url} with provider: {provider}")
        
        response = requests.get(api_url, params=params, timeout=10, verify=verify_ssl)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract credentials from the response structure
            # Response format: {"status": "success", "message": "...", "data": {"credentials": "..."}}
            if data.get('status') == 'success' and 'data' in data:
                credentials = data['data'].get('credentials')
                
                if credentials:
                    logger.info(f"Secret successfully fetched from API for: {secret_key}")
                    return credentials
                else:
                    logger.warning(f"Credentials field not found in API response data")
            else:
                logger.warning(f"API response status is not success or data field is missing")
        else:
            logger.warning(f"API request failed with status code: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch secret from API: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error while fetching secret from API: {str(e)}")
    
    # Return default value if API fetch failed
    logger.info(f"Returning default value for secret: {secret_key}")
    return default_value

# Get the secrets for connectors (eg. GitHub, Sharepoint, Jira, Confluence)
def get_connector_secret(connector_name, project_id=None, auth_provider=None, default_value="allprojects"):
    """
    Get connector secret json data from API.
    
    Args:
        connector_name: Name of the connector (e.g., 'GITHUB', 'SHAREPOINT', 'JIRA', 'CONFLUENCE')
        project_id: Project ID. If None, uses global _PROJECT_ID
        auth_provider: Cloud provider (e.g., 'azure', 'aws', 'gcp'). If None, uses global _CLOUD_PROVIDER
        default_value: Default value to return if secret is not found (defaults to empty string)
    
    Returns:
        Connector secret as a json data
    """
    # Use global context values if not provided, default to aws
    proj_id = project_id if project_id is not None else _PROJECT_ID
    provider = auth_provider if auth_provider is not None else (_CLOUD_PROVIDER or "aws")

    if connector_name and proj_id:
        try:
            # Get SSL verification setting
            verify_ssl = get_verify_ssl()
            
            connector_name_upper = connector_name.upper()
            secret_key = f"{proj_id}-{connector_name_upper}"
            api_url = f"{CREDENTIALS_API_BASE_URL}/{secret_key}"
            params = {"cloud_provider": provider}
            
            logger.info(f"Fetching connector secret from API: {api_url} with provider: {provider}")
            
            response = requests.get(api_url, params=params, timeout=10, verify=verify_ssl)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract credentials from the response structure
                # Response format: {"status": "success", "message": "...", "data": {"credentials": "..."}}
                if data.get('status') == 'success' and 'data' in data:
                    credentials = data['data'].get('credentials')
                    
                    if credentials:
                        logger.info(f"Connector secret successfully fetched from API for: {connector_name}")
                        return credentials
                    else:
                        logger.warning(f"Credentials field not found in API response data")
                else:
                    logger.warning(f"API response status is not success or data field is missing")
            else:
                logger.warning(f"API request failed with status code: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch connector secret from API: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while fetching connector secret from API: {str(e)}")

    # No fallback to allprojects - always require project-specific credentials
    logger.warning(f"No connector secret found for project '{proj_id}', connector '{connector_name}'")
    return None