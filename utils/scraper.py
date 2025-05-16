import requests, cloudscraper, re, asyncio, sys, argparse, time
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright,TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from collections import Counter
import functools

# Helper function to print to stderr
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

  
print = functools.partial(print, flush=True)

class Scrape_URL:
    def __init__(self, url, threshold = 80, browser = "Chrome", user_agent = None, requests_failure = False, scrape_only = False):
        self.url = url
        self.threshold = threshold
        self.browser = browser.lower() 
        self.user_agent = user_agent
        self.requests_failure = requests_failure
        self.scrape_only = scrape_only
       

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
        url_pattern = r"^https?://"  # http or https
        url_pattern += r"([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}"  # Domain name
        url_pattern += r"(:[0-9]+)?"  # Optional port number
        url_pattern += r"(/.*)?$"  # Optional path and query parameters

        match = re.match(url_pattern, self.url)

        return bool(match)
    
    def _browser_type(self):
        browser = self.browser
        chromium = ["chrome", "brave", "microsoft edge", "opera", "vivaldi", "libreWolf"]
        if browser in chromium:
            return "chromium"
        elif browser == "firefox":
            return "firefox"
        elif browser == "safari":
            return "webkit"
        else:
            eprint("The provided browser is not supported by the script!!")
            sys.exit(1)
    
    def _detect_interactive_environment():
        # Checking if the environment is interactive or a script for scraping with Playwright
        return hasattr(sys, 'ps1') or sys.flags.interactive or "ipykernel" in sys.modules
    
    def _requires_playwright(self, count):
        """
        The scraping can be done with requests, and if the content is too small < threshold
        then only we use playwright. Only made this function so that the flow is clear and documentation purposes
        """

        return count < self.threshold
    
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
    
    def _is_content_junk(self, text_content, word_count):
        """
        Analyzes text content to determine if it's mostly junk (CSS classes, inline styles, etc.).
        """
        if not text_content or word_count == 0:
            return False
        
        tokens = text_content.split() 

        if not tokens:
            return False

        junk_tokens = 0

        # Regex for common CSS class patterns (like css-xxxx, MuiXxxx, names with multiple hyphens)
        # and simple inline style fragments.
        css_class_pattern = re.compile(
            r"^(css-|mui-|data-|aria-|js-|wp-|fa-|glyphicon-)|(^([a-zA-Z]+-){2,})|(\w+:\s*[\w#-]+(?:;|\s|$))"
        )


        for token in tokens:
            if css_class_pattern.search(token.lower()): # make it case-insensitive for Mui etc.
                junk_tokens += 1
            elif '{' in token or '}' in token or ';' in token and ':' in token: # simple check for js/css code
                if len(token) < 30 : # only for relatively short tokens
                    junk_tokens += 1


        if not tokens: 
            return False

        junk_ratio = junk_tokens / len(tokens)

        # Decision: if > 50% of tokens are junk, or if very few "real" words remain.
        # These thresholds might need tuning.
        min_real_words_for_requests = self.threshold * 0.75 # e.g., if threshold is 80, need at least 60 real words

        if junk_ratio > 0.3: # If 30% of tokens look like junk
            if not self.scrape_only:
                eprint(f"[Debug] High junk ratio: {junk_ratio:.2f} ({junk_tokens}/{len(tokens)} tokens).")
            return True
        if (word_count - junk_tokens) < min_real_words_for_requests and word_count > 10 : # If few real words and there was some content
            if not self.scrape_only:
                eprint(f"[Debug] Low real word count: {word_count - junk_tokens} (Total: {word_count}, Junk: {junk_tokens}).")
            return True

        return False
    
    def _requests_scrape(self):
        # Returns count of words in scraped url and the content if successful
        if not self.scrape_only:
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
            if not self.scrape_only:
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
            eprint("\n[Unrecoverable] Script interrupted by user or system. Exiting.")
            eprint("Exiting...")
            time.sleep(2)
            sys.exit(1)

        except Exception as e:
            # Unrecoverable: unexpected bug or system error
            eprint(f"[Unrecoverable Error] Unexpected failure during scraping {self.url}: {e}")
            eprint("Exiting...")
            time.sleep(2)
            sys.exit(1)

    async def _playwright_scrape(self):
        if not self.scrape_only:
            print("Playwright scrape job starting....")

         # Timer to interactively show process running
        async def countdown_timer_local(duration_seconds, page_to_monitor, message_prefix="Playwright waiting"):
            for i in range(duration_seconds + 1):
                if page_to_monitor.is_closed():
                    eprint(f"\r{' ' * 70}\r Timer stopped.", flush=True) 
                    break
                # Pad with spaces to clear previous longer messages
                eprint(f"\r{message_prefix}: {i}/{duration_seconds}s{' ' * 20}", end="", flush=True) 
                await asyncio.sleep(1)
            if not page_to_monitor.is_closed():
                eprint(f"\r{message_prefix}: Wait time {duration_seconds}s elapsed.{' ' * 20}", flush=True) 
            eprint() # Newline after timer completion/stop, to stderr

        timer_task_handle = None # To hold the asyncio.Task for the timer

        async def run():
            nonlocal timer_task_handle
            page_instance = None
            async with async_playwright() as p:
                
                browser_type = self._browser_type()
                browser = await getattr(p, browser_type).launch(headless=True)
                headers = self._get_headers(False)
                user_agent = self.user_agents[browser_type]
                context = await browser.new_context(user_agent = user_agent, extra_http_headers=headers)

                page_instance = await context.new_page()
                
                # Timer for waiting page load 
                async def fetch_with_timeout(page_instance, url, timeout_seconds=60):
                    """
                    To-do: The timer cancellation after scraping still doesn't work, 
                    I need to check it again. For now it works, too
                    """
                    async def timer():
                        await asyncio.sleep(timeout_seconds)
                        eprint(f"Timeout of {timeout_seconds}s reached!")

                    timer_task = asyncio.create_task(timer())
                    try:
                        await asyncio.wait_for(
                        page_instance.goto(url, wait_until="domcontentloaded"),
                        timeout=timeout_seconds
                    )
                    except asyncio.TimeoutError:
                        eprint(f"[ERROR] Page load timed out after {timeout_seconds} seconds.")
                        raise  
                    finally:              
                        # Cancel the timer if still running
                        if not timer_task.done():
                            timer_task.cancel()
                            try:
                                await timer_task
                            except asyncio.CancelledError:
                                eprint("Page loaded.")

                wait_duration_ms = 60000
                wait_duration_s = wait_duration_ms // 1000



                await fetch_with_timeout(page_instance, self.url, timeout_seconds=wait_duration_s)

                # Start the countdown timer task
                timer_task_handle = asyncio.create_task(
                    countdown_timer_local(wait_duration_s, page_instance , f"Playwright working")
                )

                # The actual Playwright wait operation
                main_wait_task = asyncio.create_task(
                    page_instance.wait_for_timeout(wait_duration_ms)
                )
                await main_wait_task
                html = await page_instance.content()
                await browser.close()
                return html

        try:
            html = await run()
            
            content = self._soup(html)
            count = Counter(content.split(" ")).total()
            if not self.scrape_only:
                print(f"Playwright scrape job completed with {count} words worth of content")
            return count, content
        
        except PlaywrightTimeoutError as te:
            
            if not self.requests_failure:
                eprint(f"[Recoverable] Timeout while loading page: {te}")
                return None, None
            else:
                eprint("Scraping job failed!!")
                eprint("Exiting...")
                time.sleep(2)
                sys.exit(1)

        except PlaywrightError as pe:
            if not self.requests_failure:
                eprint(f"[Recoverable] Playwright browser error: {pe}")
                return None, None
            else:
                eprint("Scraping job failed!!")
                eprint("Exiting...")
                time.sleep(2)
                sys.exit(1)

        except Exception as e:
            eprint(f"[Unrecoverable] Unexpected error: {e}")
            eprint("Exiting...")
            time.sleep(2)
            sys.exit(1) 

    async def scrape(self):
        """
        The actual function that undertakes the scraping job
        returns:
        scraper - Str denoting which scraper's job is returned
        count - The words count of content scraped
        content - The scraped content
        """
        # Validaing the url string
        valid = self.validate_url()
        if not valid:
            eprint("Please provide a proper url with scheme i.e http/s://www.<your_page>")
            time.sleep(2)
            sys.exit(1)

        # Run synchronous _requests_scrape in an executor to not block the event loop
        loop = asyncio.get_event_loop()
        requests_count, requests_content = await loop.run_in_executor(None,self._requests_scrape)

        requests_count = requests_count or 0
        requests_content = requests_content or ""

        requests_content_is_junk = self._is_content_junk( requests_content, requests_count)

        if requests_content_is_junk:
            playwright_count, playwright_content = await self._playwright_scrape()
            if self.scrape_only:
                    return playwright_content
            else:
                    return "playwright",playwright_count, playwright_content

        # Check if requests job is satisfactory and is not junk, else start playwright scraping job
        if self._requires_playwright(requests_count) and not requests_content_is_junk:
            playwright_count, playwright_content = await self._playwright_scrape()
            if playwright_count > requests_count:
                if self.scrape_only:
                    print(playwright_content if playwright_content else f"No content scraped from {self.url}")
                    return playwright_content
                else:
                    return "playwright",playwright_count, playwright_content
            else:
                if self.scrape_only:             
                    print(requests_content if requests_content else f"No content scraped from {self.url}")
                    return requests_content
                else:
                    return "requests", playwright_count ,requests_content
            
        if not self.scrape_only:
            return "requests",requests_count, requests_content
        else:
            print(requests_content if requests_content else f"No content scraped from {self.url}")
            return requests_content
        
        

async def main():
    parser = argparse.ArgumentParser(description="Scrape a webpage with requests and Playwright.")
    parser.add_argument("--url", type = str, required=True, help="The URL of the webpage to scrape (with protocol)")
    parser.add_argument("--threshold", "-t", default=80, type=int, help="Threshold for word count to switch to Playwright. Default 80 and not recommended to tweak.")
    parser.add_argument("--browser", "-b", default="Chrome", type=str, help="Browser type for Playwright (Chrome, Firefox, Safari)")
    parser.add_argument("--user-agent", "-ua", type=str, help="User-agent. The script handles User Agent passed to headers on it's own, use only if required.")
    parser.add_argument("--scrape-only", "-s", action="store_true", help="Only return the scraped content")

    args = parser.parse_args()

    scraper = Scrape_URL(url=args.url, threshold=args.threshold, browser=args.browser,user_agent=args.user_agent, scrape_only=args.scrape_only)
    # Scraping job as a script
    await scraper.scrape()

if __name__ == "__main__":
    if Scrape_URL._detect_interactive_environment():
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            eprint("Warning: nest_asyncio not installed. Async operations in interactive environments might behave unexpectedly.")
            
    asyncio.run(main())

    


        
