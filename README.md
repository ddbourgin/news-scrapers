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
Each scraper can be run from the command-line. To see the available arguments, run `python <scraper_file>.py -h`. You can run the scrapers in tandem using the provided `scrape.sh` shell script.

Scraping occurs in two phases. In the first phase, the scraper compiles a list of hyperlinks to the relevant articles based on a passed query value. In the second phase the scraper extracts the article text from each link, and saves the collection in a JSON file with the following format:

```json
{
    "articles": [
        {
            "author": ["John Doe"],
            "before_election": false,
            "description": "Article 1 lede",
            "publishedAt": "2016-11-18T00:00:00+00:00",
            "text": "This is the article text.",
            "title": "Article 1 Title",
            "url": "http://www.nytimes.com/aponline/2016/11/18/us/article-1.html",
            "urlToImage": null
        },
        {
            "author": ["Jane Doe"],
            "before_election": true,
            "description": "Article 2 lede",
            "publishedAt": "2016-11-05T00:02:00+00:00",
            "text": "This is some more article text.",
            "title": "Article 2 Title",
            "url": "http://www.nytimes.comreuters/2016/11/5/business/article-2.html",
            "urlToImage": null
        },        
    ],
    "from_last": "30+Days",
    "pagerange": [1, 5],
    "query":"my search query",
    "source":"new-york-times",
    "status":"ok"
}
```
