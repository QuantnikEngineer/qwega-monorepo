"""
Confluence Python Client.
Uses Confluence REST API with API Key authentication
"""

import requests
import os
import base64
from typing import Dict, List, Optional, Any
import logging
from secrets_manager import get_secret, get_connector_secret


class ConfluenceClient:
    """
    Python client for Confluence integration using Confluence REST API
    Uses API Key authentication (email:API_KEY)
    """
    
    def __init__(self, base_url: str, email: str, api_key: str, space_key: str, logger: logging.Logger = None):
        """
        Initialize Confluence client
        
        Args:
            base_url: Confluence base URL (e.g., https://your-domain.atlassian.net)
                     Can include /wiki suffix, which will be automatically removed
            email: Email address for authentication
            api_key: Confluence API key/token
            logger: Optional logger instance
        """
        # Remove trailing slashes
        base_url = base_url.rstrip('/')
        
        # Remove /wiki suffix if present (it's for web UI, not API)
        if base_url.endswith('/wiki'):
            base_url = base_url[:-5]  # Remove '/wiki'
            if logger:
                logger.info("Removed '/wiki' suffix from base URL for API usage")
        
        self.base_url = base_url
        self.api_base_url = f"{self.base_url}/wiki/rest/api"
        self.email = email
        self.api_key = api_key
        self.space_key = space_key
        self.logger = logger or logging.getLogger(__name__)
        
        # Create Basic Auth header
        credentials = f"{email}:{api_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.auth_header = f"Basic {encoded_credentials}"
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        return {
            'Authorization': self.auth_header,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def list_spaces(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List all Confluence spaces
        
        Args:
            limit: Maximum number of spaces to return
            
        Returns:
            List of space dictionaries
        """
        try:
            url = f"{self.api_base_url}/space"
            params = {
                'limit': limit,
                'expand': 'name,key'
            }
            
            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            
            data = response.json()
            spaces = data.get('results', [])
            
            self.logger.info(f"Successfully retrieved {len(spaces)} spaces")
            return spaces
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error listing Confluence spaces: {error}")
            if hasattr(error, 'response') and error.response is not None:
                raise Exception(f"Error fetching spaces: {error.response.status_code} - {error.response.text}")
            else:
                raise Exception(f"Unknown error occurred: {error}")
    
    def list_pages(self, space_key: Optional[str] = None, limit: int = 100, start: int = 0, fetch_all: bool = True) -> List[Dict[str, Any]]:
        """
        List Confluence pages including all child pages
        
        Args:
            space_key: Optional space key to filter pages
            limit: Maximum number of pages per request
            start: Starting index for pagination
            fetch_all: If True, fetches all pages using pagination (default True)
            
        Returns:
            List of page dictionaries (includes all parent and child pages)
        """
        try:
            all_pages = []
            current_start = start
            
            while True:
                url = f"{self.api_base_url}/content"
                params = {
                    'limit': limit,
                    'start': current_start,
                    'expand': 'space,version,ancestors,children.page'
                }
                
                # Filter by space if provided
                if space_key:
                    params['spaceKey'] = space_key
                
                response = requests.get(url, headers=self.get_headers(), params=params)
                response.raise_for_status()
                
                data = response.json()
                pages = data.get('results', [])
                
                if not pages:
                    break
                    
                all_pages.extend(pages)
                self.logger.info(f"Fetched {len(pages)} pages (total so far: {len(all_pages)})")
                
                # Check if there are more pages to fetch
                if not fetch_all or len(pages) < limit:
                    break
                    
                current_start += limit
            
            self.logger.info(f"Successfully retrieved {len(all_pages)} total pages")
            return all_pages
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error listing Confluence pages: {error}")
            if hasattr(error, 'response') and error.response is not None:
                raise Exception(f"Error fetching pages: {error.response.status_code} - {error.response.text}")
            else:
                raise Exception(f"Unknown error occurred: {error}")

    def get_page_content(self, page_id: str) -> Dict[str, Any]:
        """
        Get page content with full details
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            Page dictionary with content
        """
        try:
            url = f"{self.api_base_url}/content/{page_id}"
            params = {
                'expand': 'body.storage,space,version,ancestors'
            }
            
            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            
            page_data = response.json()
            
            self.logger.info(f"Successfully retrieved page content: {page_id}")
            return page_data
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error getting page content {page_id}: {error}")
            if hasattr(error, 'response') and error.response is not None:
                raise Exception(f"Error fetching page content: {error.response.status_code} - {error.response.text}")
            else:
                raise Exception(f"Unknown error occurred: {error}")

    def extract_text_from_storage(self, storage_content: str) -> str:
        """
        Extract plain text from Confluence storage format (HTML-like)
        Handles Confluence-specific markup and converts to plain text
        
        Args:
            storage_content: Confluence storage format content (HTML-like)
            
        Returns:
            Plain text content
        """
        try:
            import re
            from html import unescape
            
            if not storage_content:
                return ""
            
            # Remove Confluence-specific macros and placeholders
            text = re.sub(r'<ac:structured-macro[^>]*>.*?</ac:structured-macro>', '', storage_content, flags=re.DOTALL)
            text = re.sub(r'<ac:parameter[^>]*>.*?</ac:parameter>', '', text, flags=re.DOTALL)
            text = re.sub(r'<ac:rich-text-body[^>]*>', '', text)
            text = re.sub(r'</ac:rich-text-body>', '', text)
            
            # Replace line breaks with newlines
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
            text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'</h[1-6]>', '\n\n', text, flags=re.IGNORECASE)
            
            # Remove HTML tags but preserve structure
            text = re.sub(r'<[^>]+>', '', text)
            
            # Decode HTML entities
            text = unescape(text)
            
            # Clean up multiple whitespace and newlines
            text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single space
            text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double newline
            text = text.strip()
            
            return text
        except Exception as e:
            self.logger.warning(f"Error extracting text from storage format: {e}")
            # Fallback: return as-is if extraction fails
            return storage_content

    def convert_text_to_storage(self, plain_text: str) -> str:
        """
        Convert plain text to Confluence storage format (XHTML)
        
        Args:
            plain_text: Plain text content to convert
            
        Returns:
            Confluence storage format content (XHTML)
        """
        import re
        from html import escape
        
        if not plain_text:
            return ""
        
        # Escape HTML special characters
        text = escape(plain_text)
        
        # Convert line breaks to paragraph tags
        paragraphs = text.split('\n\n')
        storage_content = ''
        
        # Add AI generated disclaimer at the top in red small fonts
        storage_content += '<p style="text-align: center;"><em><span style="color: #ff0000; font-size: 9pt;">This is AI generated content</span></em></p>'
        
        for para in paragraphs:
            if para.strip():
                # Convert single newlines within paragraphs to <br/>
                para_content = para.replace('\n', '<br/>')
                storage_content += f'<p>{para_content}</p>'
        
        return storage_content

    def create_page(self, title: str, content: str, parent_id: Optional[str] = None, space_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new Confluence page
        
        Args:
            title: Page title
            content: Page content (plain text - will be converted to storage format)
            parent_id: Optional parent page ID for creating child pages
            space_key: Optional space key (defaults to configured space key)
            
        Returns:
            Created page dictionary with id, title, webUrl, etc.
        """
        try:
            url = f"{self.api_base_url}/content"
            
            # Use configured space key if not provided
            target_space_key = space_key or self.space_key
            
            # Convert plain text to Confluence storage format
            storage_content = self.convert_text_to_storage(content)
            
            # Build page data
            page_data = {
                "type": "page",
                "title": title,
                "space": {
                    "key": target_space_key
                },
                "body": {
                    "storage": {
                        "value": storage_content,
                        "representation": "storage"
                    }
                }
            }
            
            # Add parent page if specified
            if parent_id:
                page_data["ancestors"] = [{"id": parent_id}]
            
            response = requests.post(url, headers=self.get_headers(), json=page_data)
            response.raise_for_status()
            
            created_page = response.json()
            
            self.logger.info(f"Successfully created page: {title} (ID: {created_page.get('id')})")
            return created_page
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error creating Confluence page: {error}")
            if hasattr(error, 'response') and error.response is not None:
                error_detail = error.response.text
                self.logger.error(f"Error details: {error_detail}")
                raise Exception(f"Error creating page: {error.response.status_code} - {error_detail}")
            else:
                raise Exception(f"Unknown error occurred: {error}")

    def update_page(self, page_id: str, title: str, content: str, version_number: int) -> Dict[str, Any]:
        """
        Update an existing Confluence page
        
        Args:
            page_id: ID of the page to update
            title: New page title
            content: New page content (plain text - will be converted to storage format)
            version_number: Current version number (will be incremented)
            
        Returns:
            Updated page dictionary
        """
        try:
            url = f"{self.api_base_url}/content/{page_id}"
            
            # Convert plain text to Confluence storage format
            storage_content = self.convert_text_to_storage(content)
            
            page_data = {
                "type": "page",
                "title": title,
                "version": {
                    "number": version_number + 1
                },
                "body": {
                    "storage": {
                        "value": storage_content,
                        "representation": "storage"
                    }
                }
            }
            
            response = requests.put(url, headers=self.get_headers(), json=page_data)
            response.raise_for_status()
            
            updated_page = response.json()
            
            self.logger.info(f"Successfully updated page: {title} (ID: {page_id})")
            return updated_page
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error updating Confluence page: {error}")
            if hasattr(error, 'response') and error.response is not None:
                error_detail = error.response.text
                self.logger.error(f"Error details: {error_detail}")
                raise Exception(f"Error updating page: {error.response.status_code} - {error_detail}")
            else:
                raise Exception(f"Unknown error occurred: {error}")

    def get_page_by_title(self, title: str, space_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a Confluence page by its title
        
        Args:
            title: Page title to search for
            space_key: Optional space key (defaults to configured space key)
            
        Returns:
            Page dictionary if found, None otherwise
        """
        try:
            target_space_key = space_key or self.space_key
            url = f"{self.api_base_url}/content"
            
            params = {
                "title": title,
                "spaceKey": target_space_key,
                "expand": "version,space"
            }
            
            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if results:
                self.logger.info(f"Found existing page: {title} (ID: {results[0].get('id')})")
                return results[0]
            
            return None
            
        except requests.exceptions.RequestException as error:
            self.logger.error(f"Error searching for Confluence page: {error}")
            return None

    def create_or_update_page(self, title: str, content: str, parent_id: Optional[str] = None, space_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new page or update an existing page with the same title
        
        Args:
            title: Page title
            content: Page content (plain text - will be converted to storage format)
            parent_id: Optional parent page ID for creating child pages
            space_key: Optional space key (defaults to configured space key)
            
        Returns:
            Created or updated page dictionary with id, title, webUrl, etc.
        """
        target_space_key = space_key or self.space_key
        
        # Check if page already exists
        existing_page = self.get_page_by_title(title, target_space_key)
        
        if existing_page:
            # Update existing page
            page_id = existing_page.get('id')
            version_number = existing_page.get('version', {}).get('number', 1)
            self.logger.info(f"Page '{title}' already exists (ID: {page_id}). Updating...")
            return self.update_page(page_id, title, content, version_number)
        else:
            # Create new page
            self.logger.info(f"Creating new page: '{title}'")
            return self.create_page(title, content, parent_id, target_space_key)


class ConfluenceConfig:
    """Confluence configuration class"""
    
    def __init__(self, base_url: str = None, email: str = None, api_key: str = None, space_key: str = None):
        """
        Initialize Confluence configuration using global secrets context
        
        Args:
            base_url: Confluence base URL (e.g., https://your-domain.atlassian.net)
            email: Email address for authentication
            api_key: Confluence API key/token
            space_key: Confluence space key
        """
        
        # Use connector secret with global context from secrets_manager
        confluence_credential = get_connector_secret('confluence')
        
        # Handle case where get_connector_secret returns None or non-dict
        if confluence_credential is None or not isinstance(confluence_credential, dict):
            confluence_credential = {}
        
        self.base_url = base_url or confluence_credential.get("site_url") or get_secret('CONFLUENCE_BASE_URL')
        self.email = email or confluence_credential.get("username") or get_secret('CONFLUENCE_EMAIL')
        self.api_key = api_key or confluence_credential.get("api_token") or get_secret('CONFLUENCE_API_KEY')
        self.space_key = space_key or confluence_credential.get("space_key") or get_secret('CONFLUENCE_SPACE_KEY')
        
        if not all([self.base_url, self.email, self.api_key]):
            raise ValueError("Confluence is not configured for this project.")
