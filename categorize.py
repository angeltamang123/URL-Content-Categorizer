from gradio_client import Client
from utils.scraper import Scrape_URL
import sys, asyncio, argparse

# Helper function to print to stderr
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class Categorizer:
    def __init__(self, url, threshold = 80, browser = "Chrome", user_agent = None, scrape_only = False):
        self.url = url
        self.threshold = threshold
        self.browser = browser 
        self.user_agent = user_agent
        self.scrape_only = scrape_only

    async def _scrape(self):
        scraper = Scrape_URL(url=self.url, threshold=self.threshold, 
                                browser=self.browser, user_agent=self.user_agent,
                                scrape_only=self.scrape_only
                                )
        scraper_used, count, content = await scraper.scrape()
        if self.scrape_only:
            return None
        else:
            return scraper_used, count, content
        
    def _detect_interactive_environment():
        # Checking if the environment is interactive or a script for scraping with Playwright
        return hasattr(sys, 'ps1') or sys.flags.interactive or "ipykernel" in sys.modules
    
    def predict(self):
        if self._detect_interactive_environment():
                    try:
                        import nest_asyncio
                        nest_asyncio.apply()
                    except ImportError:
                        eprint("Warning: nest_asyncio not installed. Async operations in interactive environments might behave unexpectedly.")

        scraper_used, count, content = asyncio.run(self._scrape())
        if not self.scrape_only:
            try: 
                eprint(f"Using the scraping output of {scraper_used} with word count of {count} \nas input to the model")
                space_id = "Vyke2000/WebOrganizer-TopicClassifier-NoURL_on_Gradio_Spaces"
                client = Client(space_id)
                result = client.predict(content, api_name="/predict")
                print(f"The topic is categorized as {result['topic']} with the model being {result['confidence'] * 100}% confident ")
            except Exception as e:
                    print("Ops!! Something went wrong while inferring the model: {e}")

def main():
    parser = argparse.ArgumentParser(description="Scrape a webpage with requests and Playwright.")
    parser.add_argument("--url", type = str, required=True, help="The URL of the webpage to scrape (with protocol)")
    parser.add_argument("--threshold", "-t", default=80, type=int, help="Threshold for word count to switch to Playwright. Default 80 and not recommended to tweak.")
    parser.add_argument("--browser", "-b", default="Chrome", type=str, help="Browser type for Playwright (Chrome, Firefox, Safari)")
    parser.add_argument("--user-agent", "-ua", type=str, help="User-agent. The script handles User Agent passed to headers on it's own, use only if required.")
    parser.add_argument("--scrape-only", "-s", action="store_true", help="Only return the scraped content")

    args = parser.parse_args()

    infer = Categorizer(url=args.url, threshold=args.threshold, 
                        browser=args.browser, user_agent=args.user_agent,
                        scrape_only=args.scrape_only 
                        )
    
    infer.predict()

if __name__ == '__main__':
    main()
                     




                    
