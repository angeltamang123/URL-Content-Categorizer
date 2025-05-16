# URL-Content-Categorizer

Get topic for provided URL with WebOrganizer's [topic-classifer](https://huggingface.co/WebOrganizer/TopicClassifier-NoURL). The model classifies URL content into 24 distinct classes, and is a fine-tune of gte-base-en-v1.5. URL Content Categorizer makes it easy for you to get contents from a URL and infer topic-classifier model with a single python script

## Web-Scraping

The Scraper uses requests and playwright, combined with beautiful soup to prepare content as input for the model. Scraper, itself, handles which scraping method's output to use for inference. Requests usually fails due to Js usage on a webpage, this is where the playwright scraping job kicks in. Scraper uses a heuristic where the content scraped length less than a threshold set 80, and contains obfuscated HTML/ CSS, causes playwright to kick in. There's no special interaction implementaion with playwright as it simply waits for the DOM content to load for webpage with JS.

## Installing

1. Clone the repo, and cd:

```bash
$ git clone https://github.com/angeltamang123/URL-Content-Categorizer.git
$ cd URL-Content-Categorizer
```

2. At this point you should be in a virtual environment, if not already in one. You can create one for this project (not neccessary if you're using cloud interactive notebooks):

```bash
URL-Content-Categorizer$ python3 -m venv .venv
URL-Content-Categorizer$ source .venv/bin/activate
```

3. Install dependencies:

```bash
URL-Content-Categorizer$ pip install -r requirements.txt
```

4. Install headless browser binaries with playwright install:

```bash
URL-Content-Categorizer$ playwright install --with-deps
```

> [!Important]
> If you get error logs like: host OS missing dependencies
> Then your host OS won't run playwright (an issue I faced during development as my local machine is on Ubuntu 23.04 which is EOS)
> For this case, you are better off using cloud interactive notebooks(Google Colab, Kaggle Notebooks)
> If you decided to use kaggle, you need to cd from the console and then perform the installation of playwright browsers.
> While in colab using cd command in similar way is only available in colab pro

## Usage

1. Run the script, example

```bash
URL-Content-Categorizer$  python categorize.py --url https://angel-tamang.vercel.app
```

> The topic is categorized as Education & Jobs with the model being 74.47% confident

2. You can also use the script to skip inference and retreive scrapped content only with -s flag

```bash
URL-Content-Categorizer$  python categorize.py --url https://angel-tamang.vercel.app -s
```

> Page loaded.
> Playwright working: 60/60s Projects
> Hello!
> Hello!
> Experiences Educations
> A n g e l T a m a n g ...........

## Consideraions for Usage

> [!Important]
> Topic-classifer is hosted on a free service using my account, so the project shall be used only for testing, personal research,sharing, etc, and not for commercial purposes.
> You can use the script to just scrape url with -s flag as it doesn't use the resources inferring the model. However, there are better tools that can be tailered for your custom requirements.
> The scraping job might fail if a page heavily uses Js and needs browser interactions to get contents.

> [!Warning]
> Scraping some pages are strictly against their policies. Do check their /robots.txt file before scraping off the content. You are solely responsible for how you use this tool as I assume no liability for any misuse, legal issues, or consequences resulting from scraping protected or restricted content.

# Future

Package the project and make it available to install from pip and uv, and make a demo website ??
