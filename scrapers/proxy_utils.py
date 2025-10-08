"""
Centralized Proxy Management Utility
Provides rotating proxy support for all scrapers (requests, Selenium, etc.)
"""

import os
import random
import time
import requests
from typing import Optional, Dict, List
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Proxy Configuration ---
PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
PROXY_TYPE = os.getenv('PROXY_TYPE', 'residential')  # residential or datacenter
PROXY_LIST = os.getenv('PROXY_LIST', '').split(',') if os.getenv('PROXY_LIST') else []
PROXY_USERNAME = os.getenv('PROXY_USERNAME', '')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')
PROXY_ROTATION_DELAY = float(os.getenv('PROXY_ROTATION_DELAY', '0.5'))  # seconds between requests

# Proxy list can be in format: "ip:port" or "http://ip:port"
# Authentication can be embedded: "http://user:pass@ip:port"
# Or use PROXY_USERNAME and PROXY_PASSWORD for all proxies


class ProxyManager:
    """
    Manages proxy rotation and configuration for web scraping.
    Supports both requests library and Selenium WebDriver.
    """

    def __init__(self):
        self.enabled = PROXY_ENABLED
        self.proxy_list = [p.strip() for p in PROXY_LIST if p.strip()]
        self.username = PROXY_USERNAME
        self.password = PROXY_PASSWORD
        self.rotation_delay = PROXY_ROTATION_DELAY
        self.current_index = 0
        self.request_count = 0

        if self.enabled and not self.proxy_list:
            print("[WARNING] Proxy enabled but no proxy list provided. Proxies will be disabled.")
            self.enabled = False

        if self.enabled:
            print(f"[PROXY] Proxy rotation enabled with {len(self.proxy_list)} proxies")
            print(f"[PROXY] Type: {PROXY_TYPE}")
            print(f"[PROXY] Rotation delay: {self.rotation_delay}s")

    def _format_proxy_url(self, proxy: str, protocol: str = 'http') -> str:
        """
        Format proxy string into proper URL format with authentication if needed.

        Args:
            proxy: Proxy string (ip:port or http://ip:port)
            protocol: Protocol to use (http or https)

        Returns:
            Formatted proxy URL
        """
        # If proxy already has authentication or protocol, return as-is
        if '@' in proxy or proxy.startswith('http'):
            return proxy

        # Add authentication if provided
        if self.username and self.password:
            return f"{protocol}://{self.username}:{self.password}@{proxy}"

        return f"{protocol}://{proxy}"

    def get_next_proxy(self) -> Optional[str]:
        """
        Get the next proxy in rotation.

        Returns:
            Proxy string or None if proxies disabled
        """
        if not self.enabled or not self.proxy_list:
            return None

        proxy = self.proxy_list[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxy_list)
        self.request_count += 1

        return proxy

    def get_random_proxy(self) -> Optional[str]:
        """
        Get a random proxy from the list.

        Returns:
            Proxy string or None if proxies disabled
        """
        if not self.enabled or not self.proxy_list:
            return None

        self.request_count += 1
        return random.choice(self.proxy_list)

    def get_proxies_dict(self, rotate: bool = True) -> Optional[Dict[str, str]]:
        """
        Get proxy dictionary for requests library.

        Args:
            rotate: Whether to rotate to next proxy (True) or get random (False)

        Returns:
            Proxies dict for requests or None if disabled
        """
        if not self.enabled:
            return None

        proxy = self.get_next_proxy() if rotate else self.get_random_proxy()
        if not proxy:
            return None

        http_proxy = self._format_proxy_url(proxy, 'http')
        https_proxy = self._format_proxy_url(proxy, 'https')

        return {
            'http': http_proxy,
            'https': https_proxy
        }

    def configure_selenium_options(self, chrome_options: Options, rotate: bool = True) -> Options:
        """
        Configure Chrome options with proxy settings for Selenium.

        Args:
            chrome_options: Selenium Chrome Options object
            rotate: Whether to rotate to next proxy (True) or get random (False)

        Returns:
            Modified Chrome Options object
        """
        if not self.enabled:
            return chrome_options

        proxy = self.get_next_proxy() if rotate else self.get_random_proxy()
        if not proxy:
            return chrome_options

        # Format proxy for Selenium
        proxy_formatted = self._format_proxy_url(proxy, 'http')

        # Add proxy argument to Chrome
        chrome_options.add_argument(f'--proxy-server={proxy_formatted}')

        print(f"[PROXY] Selenium configured with proxy: {proxy.split('@')[-1] if '@' in proxy else proxy}")

        return chrome_options

    def make_request_with_retry(self, url: str, method: str = 'GET', max_retries: int = 3,
                                rotate_on_error: bool = True, **kwargs) -> Optional[requests.Response]:
        """
        Make HTTP request with automatic proxy rotation on failure.

        Args:
            url: URL to request
            method: HTTP method (GET, POST, etc.)
            max_retries: Maximum number of retry attempts
            rotate_on_error: Whether to rotate proxy on error
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object or None if all retries failed
        """
        for attempt in range(max_retries):
            try:
                # Get proxy for this request
                proxies = self.get_proxies_dict(rotate=rotate_on_error or attempt > 0)

                # Add proxy to kwargs
                if proxies:
                    kwargs['proxies'] = proxies

                # Add delay between requests to mimic human behavior
                if self.request_count > 1 and self.rotation_delay > 0:
                    time.sleep(self.rotation_delay)

                # Make request
                if method.upper() == 'GET':
                    response = requests.get(url, **kwargs)
                elif method.upper() == 'POST':
                    response = requests.post(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Raise exception for bad status codes
                response.raise_for_status()

                return response

            except requests.exceptions.ProxyError as e:
                print(f"[PROXY ERROR] Proxy failed on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1 and rotate_on_error:
                    print(f"[PROXY] Rotating to next proxy...")
                    continue
                else:
                    print(f"[PROXY ERROR] All retries exhausted")
                    return None

            except requests.exceptions.RequestException as e:
                print(f"[REQUEST ERROR] Request failed on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    print(f"[RETRY] Retrying with new proxy...")
                    continue
                else:
                    print(f"[REQUEST ERROR] All retries exhausted")
                    return None

        return None

    def get_stats(self) -> Dict[str, any]:
        """
        Get proxy usage statistics.

        Returns:
            Dictionary with proxy stats
        """
        return {
            'enabled': self.enabled,
            'total_proxies': len(self.proxy_list),
            'total_requests': self.request_count,
            'current_proxy_index': self.current_index,
            'proxy_type': PROXY_TYPE
        }


# Global proxy manager instance
proxy_manager = ProxyManager()


def get_proxy_manager() -> ProxyManager:
    """
    Get the global proxy manager instance.

    Returns:
        ProxyManager instance
    """
    return proxy_manager


def add_delay(min_delay: float = 1.0, max_delay: float = 3.0):
    """
    Add random delay to mimic human behavior and reduce detection risk.

    Args:
        min_delay: Minimum delay in seconds
        max_delay: Maximum delay in seconds
    """
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)
