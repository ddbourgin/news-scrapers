## Installation
The scrapers use [PhantomJS](http://phantomjs.org/) to render the Javascript in some of the search pages. If you already use node.js, you can install PhantomJS via npm:

```bash
npm install phantomjs-prebuilt
```

Alternatively, you can install it using Homebrew on OSX:
```bash
brew update
brew install phantomjs
```

Or just download the Linux/OSX/Windows/FreeBSD binaries [here](http://phantomjs.org/download.html).

Once you've installed PhantomJS, clone this repo and install the Python dependencies using pip:

```bash
git clone https://github.com/ddbourgin/news-scrapers.git
cd news-scrapers
pip install -r requirements.txt
```

## Usage
Each scraper can be run from the command-line. To see the available arguments, run `python <scraper_file>.py -h`. You can also run the scrapers in tandem using the provided `scrape.sh` shell script.

Scraping occurs in two phases. In the first phase, the scraper compiles a list of article hyperlinks based on the user query  and saves them in newline-delimited text file in the `./links` directory. In the second phase the scraper loops over each link identified during phase 1 and extracts the article text, saving the final scraped article collection in a JSON file in the `./scraped_json` directory. The output JSON has the the following format:

```json
{
    "articles": [
        {
            "author": ["Netochka Nezvanova"],
            "before_election": false,
            "description": "Article 1 lede",
            "publishedAt": "2016-11-18T00:00:00+00:00",
            "text": "This is the article text.",
            "title": "Article 1 Title",
            "url": "http://www.nytimes.com/2016/11/18/us/article-1.html",
            "urlToImage": null
        },
        {
            "author": ["Rudolph Lingens", "Luther Blissett"],
            "before_election": true,
            "description": "Article 2 lede",
            "publishedAt": "2016-11-05T00:02:00+00:00",
            "text": "This is some more article text.",
            "title": "Article 2 Title",
            "url": "http://www.nytimes.com/2016/11/5/article-2.html",
            "urlToImage": null
        },        
    ],
    "from_last": "30 days",
    "pagerange": [1, 5],
    "query":"my search query",
    "source":"new-york-times",
    "status":"ok"
}
```
