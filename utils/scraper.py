import requests
import cloudscraper
from bs4 import BeautifulSoup
import re
import asyncio
from playwright.async_api import async_playwright,TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
import sys
import argparse
from collections import Counter
import time

class Scrape_URL:
    def __init__(self, url, threshold = 80, browser = "Chrome", user_agent = None, requests_failure= False ):
        self.url = url
        self.threshold = threshold
        self.browser = browser
        self.user_agent = user_agent
        self.requests_failure = requests_failure

        self.user_agents = {
            "chromium": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
            "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
               "Gecko/20100101 Firefox/122.0",
            "webkit": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) "
              "Version/16.4 Safari/605.1.15"
        }

    def validate_url(self):
        """ 
        Checks if the url supplied is valid with regex
        the url with the protocol must be supplied for playwright to work 
        """
        url_pattern = r"^(https?://)?"  # http or https
        url_pattern += r"([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}"  # Domain name
        url_pattern += r"(:[0-9]+)?"  # Optional port number
        url_pattern += r"(/.*)?$"  # Optional path and query parameters

        match = re.match(url_pattern, self.url)
        return bool(match)
    
    def _browser_type(self):
        browser = self.browser.lower()
        chromium = ["chrome", "brave", "microsoft edge", "opera", "vivaldi", "libreWolf"]
        if browser in chromium:
            return "chromium"
        elif browser == "firefox":
            return "firefox"
        elif browser == "safari":
            return "webkit"
        else:
            print("The provided browser is not supported by the script!!")
            sys.exit(1)
    
    def _detect_interactive_environment():
        # Checking if the environment is interactive or a script for scraping with Playwright
        return hasattr(sys, 'ps1') or sys.flags.interactive or "ipykernel" in sys.modules
    
    def _requires_playwright(self, count):
        """
        The scraping can be done with requests, and if the content is too small < threshold
        then only we use playwright. Only made this function so that the flow is clear and documentation purposes
        """

        return True if count < self.threshold else False
    
    def _get_headers(self, return_ua = True):
        """
        returns user's own user agent if provided, else returns for the browser arg provided
        """
        if self.user_agent:
            ua = self.user_agent
        else:
            browser = self._browser_type()
            ua = self.user_agents[browser]

        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Connection": "keep-alive",
        }

        if return_ua:
            headers["User-Agent"] = ua

        return headers
        
    def _soup(self, html):
        # Clean the html response
        soup = BeautifulSoup(html, 'html.parser')
        tags = soup.find_all(['p', 'ul', 'ol', 'pre'])
        output = []

        for tag in tags:
            # Skip if it's <ul> or <ol> and is inside a <p>
            if tag.name in ['ul', 'ol', 'pre'] and tag.find_parent('p'):
                continue
            # Otherwise, get its text
            output.append(tag.get_text(separator=' ', strip=True))

        all_text = '\n'.join(output)

        return all_text
    
    def _requests_scrape(self):
        # Returns count of words in scraped url and the content if successful
        print("Requests scrape job starting....")
        # cloudscraper makes request in same way as requests while handling cloudflare block
        scraper = cloudscraper.create_scraper()
        try:
            headers = self._get_headers()
            response = scraper.get(self.url, timeout=10, headers=headers)
            response.raise_for_status()  # Raises HTTPError for bad responses
            html = response.text
            content = self._soup(html)
            count = Counter(content.split(" ")).total()
            print(f"Requests scrape job completed with {count} words worth of content")
            return count, content
        except (requests.exceptions.HTTPError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                cloudscraper.exceptions.CloudflareChallengeError) as e:
            # Recoverable: log and return None to allow script to continue
            print(f"[Recoverable Error] Failed to scrape {self.url}: {e}")
            self.requests_failure = True
            return None, None

        # Unrecoverable: handle separately
        except (KeyboardInterrupt, SystemExit):
            print("\n[Unrecoverable] Script interrupted by user or system. Exiting.")
            sys.exit(1)

        except Exception as e:
            # Unrecoverable: unexpected bug or system error
            print(f"[Unrecoverable Error] Unexpected failure during scraping {self.url}: {e}")
            sys.exit(1)

    async def _playwright_scrape(self):
        print("Playwright scrape job starting....")

        async def countdown_timer(duration):
            for i in range(duration + 1):
                print(f"\r{i}/{duration}s", end="", flush=True)
                await asyncio.sleep(1)

        async def run():
            async with async_playwright() as p:
                browser_type = self._browser_type()
                browser = await getattr(p, browser_type).launch(headless=True)
                headers = self._get_headers(False)
                user_agent = self.user_agents[browser_type]
                context = await browser.new_context(user_agent = user_agent, extra_http_headers=headers)

                page = await context.new_page()
                await page.goto(self.url, wait_until="domcontentloaded")
                timer = asyncio.create_task(countdown_timer(60)) # Display minute counter
                await page.wait_for_timeout(60000) # Wait for a minute

                html = await page.content()
                await browser.close()
                return html

        try:
            action = self._detect_interactive_environment()

            if action:
                html = await run()
            else:
                html = asyncio.run(run())

            content = self._soup(html)
            count = Counter(content.split(" ")).total()
            print(f"Playwright scrape job completed with {count} words worth of content")
            return count, content
        
        except PlaywrightTimeoutError as te:
            
            if not self.requests_failure:
                print(f"[Recoverable] Timeout while loading page: {te}")
                return None, None
            else:
                print("Scraping job failed!!")
                sys.exit(1)

        except PlaywrightError as pe:
            if not self.requests_failure:
                print(f"[Recoverable] Playwright browser error: {pe}")
                return None, None
            else:
                print("Scraping job failed!!")
                sys.exit(1)

        except Exception as e:
            print(f"[Unrecoverable] Unexpected error: {e}")
            sys.exit(1) 

    def scrape(self):
        
