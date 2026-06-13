"""
SharePoint Python Client
Based on the Backstage plugin implementation for SharePoint integration
Uses MSAL (Microsoft Authentication Library) for authentication
"""

import requests
import os
from typing import Dict, List, Optional, Any
import json
from datetime import datetime, timedelta
import mimetypes
from msal import ConfidentialClientApplication
import logging
from urllib.parse import urlparse
from secrets_manager import get_secret, get_connector_secret

class SharePointClient:
    """
    Python client for SharePoint integration using Microsoft Graph API
    Uses MSAL for authentication, similar to the Backstage SharePoint plugin implementation
    """
    
    def __init__(self, client_id: str, client_secret: str, tenant_id: str,site_url: str, sharepoint_folder: str,logger: logging.Logger = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.site_url = site_url
        self.sharepoint_folder = sharepoint_folder
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize MSAL Confidential Client Application
        # Similar to SharepointClientManager in the Backstage plugin
        self.msal_app = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}"
        )
        
        self.access_token = None
        self.token_expires_at = None
    
    def get_access_token(self) -> str:
        """
        Acquire access token using MSAL client credentials flow
        Similar to SharepointClientManager.getAccessToken() in the Backstage plugin
        """
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
        
        try:
            # Use MSAL to acquire token by client credentials
            # This matches the pattern used in the Backstage SharepointClientManager
            result = self.msal_app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
            
            if "access_token" not in result:
                error_msg = result.get("error_description", "Failed to acquire token")
                error_code = result.get("error", "")
                
                # Provide specific guidance for common Azure AD errors
                if "AADSTS7000215" in error_msg:
                    self.logger.error(f"⚠️  SHAREPOINT AUTHENTICATION ERROR - INVALID CLIENT SECRET")
                    self.logger.error(f"   Error Code: AADSTS7000215")
                    self.logger.error(f"   Root Cause: The 'client_secret' in your SharePoint connector configuration")
                    self.logger.error(f"               contains the Client Secret ID instead of the Client Secret VALUE.")
                    self.logger.error(f"   ")
                    self.logger.error(f"   How to fix:")
                    self.logger.error(f"   1. Go to Azure Portal > App Registrations > App '{self.client_id}'")
                    self.logger.error(f"   2. Navigate to 'Certificates & secrets' > 'Client secrets'")
                    self.logger.error(f"   3. Create a NEW client secret (the value is only shown once)")
                    self.logger.error(f"   4. Copy the SECRET VALUE (not the Secret ID)")
                    self.logger.error(f"   5. Update the 'client_secret' field in your connector credentials")
                    self.logger.error(f"   ")
                    self.logger.error(f"   Current client_id: {self.client_id}")
                    raise Exception(f"SharePoint authentication failed: Invalid client secret. The stored 'client_secret' appears to be the Secret ID instead of the Secret Value. Please update the SharePoint connector credentials with the correct client secret value from Azure AD.")
                elif "AADSTS7000216" in error_msg:
                    self.logger.error(f"⚠️  SHAREPOINT AUTHENTICATION ERROR - EXPIRED CLIENT SECRET")
                    self.logger.error(f"   The client secret has expired. Create a new secret in Azure AD.")
                    raise Exception(f"SharePoint authentication failed: Client secret has expired. Please create a new client secret in Azure AD and update the connector credentials.")
                elif "AADSTS700016" in error_msg:
                    self.logger.error(f"⚠️  SHAREPOINT AUTHENTICATION ERROR - APP NOT FOUND")
                    self.logger.error(f"   The application '{self.client_id}' was not found in tenant '{self.tenant_id}'.")
                    raise Exception(f"SharePoint authentication failed: Application not found. Verify client_id and tenant_id are correct.")
                else:
                    self.logger.error(f"Error acquiring access token: {error_msg}")
                    raise Exception(f"Failed to acquire access token: {error_msg}")
            
            self.access_token = result["access_token"]
            # Set expiration with 5-minute buffer for safety
            expires_in = result.get("expires_in", 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
            
            self.logger.info("Successfully acquired access token")
            return self.access_token
            
        except Exception as error:
            self.logger.error(f"Error acquiring access token: {error}")
            raise error
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        return {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def get_site_drives(self, site_name: str) -> Dict[str, Any]:
        """
        Get drives (document libraries) for a SharePoint site.
        
        Args:
            site_name: The name of the SharePoint site (e.g., 'aikidowego' for /sites/aikidowego)
        
        Returns:
            Dict containing the list of drives/document libraries for the site
        """
        # Parse the site_url to extract hostname
        site_url = self.site_url
        site_hostname = None
        url_site_name = None
        
        if site_url:
            if site_url.startswith('http://') or site_url.startswith('https://'):
                parsed = urlparse(site_url)
                site_hostname = parsed.netloc  # e.g., "tmnlso.sharepoint.com"
                
                # Extract site name from URL path if present (e.g., /sites/aikidowego)
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) >= 2 and path_parts[0].lower() == 'sites':
                    url_site_name = path_parts[1]
            else:
                site_hostname = site_url.split('/')[0]
        else:
            site_hostname = "wipro365.sharepoint.com"  # fallback default
        
        # IMPORTANT: Always use site name from site_url as that's where the Azure AD app has access
        # The site_name parameter might be incorrectly set to document library name
        effective_site_name = url_site_name if url_site_name else site_name
        
        if url_site_name and site_name and url_site_name.lower() != site_name.lower():
            self.logger.info(f"Note: Using site '{url_site_name}' from site_url. The parameter '{site_name}' appears to be a document library name, not a site.")
        
        url = f"{self.base_url}/sites/{site_hostname}:/sites/{effective_site_name}:/drives"
        self.logger.info(f"Fetching drives from URL: {url}")
        
        try:
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            
            self.logger.info(f"Successfully retrieved drives for site: {effective_site_name}")
            return response.json()
            
        except requests.exceptions.RequestException as error:
            error_detail = ""
            if hasattr(error, 'response') and error.response is not None:
                error_detail = f" | Response: {error.response.text[:500] if error.response.text else 'No response body'}"
                if error.response.status_code == 401:
                    self.logger.error(f"401 Unauthorized accessing SharePoint. This typically means:")
                    self.logger.error(f"  1. The Azure AD app (client_id: {self.client_id[:8]}...) lacks required Graph API permissions")
                    self.logger.error(f"  2. Required permissions: Sites.Read.All or Sites.ReadWrite.All (Application permission)")
                    self.logger.error(f"  3. Or the tenant_id ({self.tenant_id}) doesn't own the SharePoint site")
                    self.logger.error(f"  4. Ensure admin consent has been granted for the API permissions")
            self.logger.error(f"Error getting site drives for {effective_site_name} using hostname '{site_hostname}': {error}{error_detail}")
            raise Exception(f"Error fetching drives for site {effective_site_name}: {error.response.status_code if hasattr(error, 'response') and error.response else 'Unknown'} Client Error: Unauthorized for url: {url}")
    
    def get_drive_by_name(self, drives_response: Dict[str, Any], library_name: str) -> Optional[str]:
        """
        Find a specific drive/document library by name from the drives response.
        
        Args:
            drives_response: Response from get_site_drives()
            library_name: Name of the document library to find (e.g., 'QUANTNIK', 'Documents')
        
        Returns:
            The drive ID if found, None otherwise
        """
        drives = drives_response.get('value', [])
        
        for drive in drives:
            drive_name = drive.get('name', '')
            if drive_name.lower() == library_name.lower():
                self.logger.info(f"Found document library '{library_name}' with drive_id: {drive.get('id')}")
                return drive.get('id')
        
        # Log available drives for debugging
        available_drives = [d.get('name', 'Unknown') for d in drives]
        self.logger.warning(f"Document library '{library_name}' not found. Available libraries: {available_drives}")
        return None
    
    def get_folder_contents(self, drive_id: str, folder_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get contents of a SharePoint folder
        Similar to getFolderContents() in the Backstage implementation
        """
        try:
            if folder_path:
                # Normalize path - replace ~ with /
                normalized_path = folder_path.replace('~', '/')
                url = f"{self.base_url}/drives/{drive_id}/root:/{normalized_path}:/children"
            else:
                url = f"{self.base_url}/drives/{drive_id}/root/children"
            
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            
            data = response.json()
            self.logger.info(f"Successfully retrieved folder contents for drive {drive_id}")
            return data.get('value', [])
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error getting folder contents: {error}")
            if hasattr(error, 'response') and error.response is not None:
                raise Exception(f"Error fetching folder contents: {error.response.status_code} - {error.response.text}")
            else:
                raise Exception(f"Unknown error occurred: {error}")
    
    def upload_file(self, drive_id: str, folder_path: str, file_name: str, file_content: bytes) -> Dict[str, Any]:
        """
        Upload a file to SharePoint
        Similar to uploadDocument() in the Backstage implementation
        """
        try:
            file_extension = ".docx"
            normalized_path = folder_path.replace('~', '/')
            url = f"{self.base_url}/drives/{drive_id}/root:/{normalized_path}/{file_name}:/content"
            
            # Add conflict behavior parameter to handle duplicate files
            url += "?@microsoft.graph.conflictBehavior=rename"
            
            headers = {
                'Authorization': f'Bearer {self.get_access_token()}',
                'Content-Type': 'application/octet-stream'
            }
            
            response = requests.put(url, data=file_content, headers=headers)
            response.raise_for_status()
            
            self.logger.info(f"Successfully uploaded file: {file_name} to {folder_path}")
            return response.json()
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error uploading file {file_name}: {error}")
            if hasattr(error, 'response') and error.response is not None:
                raise Exception(f"Error uploading document to SharePoint: {error.response.status_code} - {error.response.text}")
            else:
                raise Exception(f"Unknown error occurred: {error}")
    
    def download_file(self, drive_id: str, folder_path: str, file_name: str) -> bytes:
        """
        Download a file from SharePoint
        Similar to downloadDocument() in the Backstage implementation
        """
        try:
            normalized_path = folder_path.replace('~', '/')
            url = f"{self.base_url}/drives/{drive_id}/root:/{normalized_path}/{file_name}:/content"
            
            headers = {
                'Authorization': f'Bearer {self.get_access_token()}'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            self.logger.info(f"Successfully downloaded file: {file_name} from {folder_path}")
            return response.content
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error downloading file {file_name}: {error}")
            if hasattr(error, 'response') and error.response is not None:
                raise Exception(f"Error downloading document from SharePoint: {error.response.status_code} - {error.response.text}")
            else:
                raise Exception(f"Unknown error occurred: {error}")
    
    def create_folder(self, drive_id: str, folder_path: str, folder_name: str) -> bool:
        """
        Create a new folder in SharePoint
        Similar to createNewFolder() in the Backstage implementation
        """
        try:
            url = f"{self.base_url}/drives/{drive_id}/root:/{folder_path}:/children"
            
            payload = {
                'name': folder_name,
                'folder': {},
                '@microsoft.graph.conflictBehavior': 'rename'  # Rename if folder exists
            }
            
            response = requests.post(url, headers=self.get_headers(), json=payload)
            response.raise_for_status()
            
            success = response.status_code == 201
            if success:
                self.logger.info(f"Successfully created folder: {folder_name} in {folder_path}")
            return success
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error creating folder {folder_name}: {error}")
            return False
    
    def search_files(self, drive_id: str, query: str) -> List[Dict[str, Any]]:
        """
        Search for files in SharePoint drive
        """
        try:
            url = f"{self.base_url}/drives/{drive_id}/root/search(q='{query}')"
            
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            
            data = response.json()
            self.logger.info(f"Successfully searched for files with query: {query}")
            return data.get('value', [])
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error searching files with query '{query}': {error}")
            return []
    
    def get_file_metadata(self, drive_id: str, item_id: str) -> Dict[str, Any]:
        """
        Get metadata for a specific file
        """
        try:
            url = f"{self.base_url}/drives/{drive_id}/items/{item_id}"
            
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            
            self.logger.info(f"Successfully retrieved metadata for item: {item_id}")
            return response.json()
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error getting file metadata for {item_id}: {error}")
            raise Exception(f"Error getting file metadata: {error}")


class SharePointClientManager:
    """
    SharePoint Client Manager similar to the Backstage implementation
    Handles client instantiation and configuration
    """
    
    def __init__(self, config: 'SharePointConfig', logger: logging.Logger = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.client = None
    
    def get_client(self) -> SharePointClient:
        """Get or create SharePoint client"""
        if not self.client:
            self.client = SharePointClient(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                tenant_id=self.config.tenant_id,
                logger=self.logger
            )
        return self.client


# Configuration class similar to SharepointConfig in TypeScript
class SharePointConfig:
    """SharePoint configuration class"""
    
    def __init__(self, client_id: str = None, client_secret: str = None, tenant_id: str = None, site_url: str = None, sharepoint_folder: str = None):
        # Use connector secret with global context from secrets_manager
        sharepoint_credential = get_connector_secret('sharepoint')
        
        # Ensure sharepoint_credential is a dict (can be None, string, or dict)
        if not isinstance(sharepoint_credential, dict):
            sharepoint_credential = {}
        
        self.client_id = client_id or sharepoint_credential.get("client_id") or get_secret('CLIENTID')
        self.client_secret = client_secret or sharepoint_credential.get("client_secret") or get_secret('CLIENTSECRET')
        self.tenant_id = tenant_id or sharepoint_credential.get("tenant_id") or get_secret('TENANTID')
        self.site_url = site_url or sharepoint_credential.get("site_url") or get_secret('SITEURL')
        self.sharepoint_folder = sharepoint_folder or sharepoint_credential.get("document_library") or get_secret('SHAREPOINT_SITE_FOLDER')
           
        if not all([self.client_id, self.client_secret, self.tenant_id]):
            raise ValueError("SharePoint is not configured for this project.")
        

# Helper functions for common operations
def format_sharepoint_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format SharePoint item similar to ISharepointData interface
    """
    return {
        'id': item.get('id', ''),
        'name': item.get('name', ''),
        'documentType': item.get('file', {}).get('mimeType', 'folder') if item.get('file') else 'folder',
        'isFolder': bool(item.get('folder')),
        'owner': item.get('createdBy', {}).get('user', {}).get('displayName', ''),
        'createdOn': item.get('createdDateTime', ''),
        'webUrl': item.get('webUrl', ''),
        'parentFolder': item.get('parentReference', {}).get('path', '')
    }