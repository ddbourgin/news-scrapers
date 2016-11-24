import os
import json
import datetime
import time
import argparse

import pytz
from bs4 import BeautifulSoup
from newspaper import Article

from selenium import webdriver
from selenium.common.exceptions import TimeoutException

tz = pytz.utc
ELECTION_DATE = datetime.datetime(2016, 11, 9, 11, tzinfo=tz)

parser = argparse.ArgumentParser(
    description='A web scraper for Washington Post articles.')

requiredNamed = parser.add_argument_group('required arguments')
requiredNamed.add_argument('-q', '--query', type=str, required=True,
                           help='Query string')

parser.add_argument('-l', '--link_file', type=str, default="",
                    help='Path to newline-delimited collection of article links')
parser.add_argument('-f', '--from_last', type=int, default=60,
                    help="Dates to pull articles from. Valid values are 24[hours], "
                    "7[days], 60[days], 365[days], [since]2005")
parser.add_argument('-t', '--doc_type', type=str, default="Article",
                    help='Type of article to scrape. A space separated string of '
                         'values. Valid arguments are "Article" and/or "Blog"')

parser.add_argument('--blog_id', type=str, default="",
                    help="The name of a specific blog to search. Only matters "
                         "if doc_type includes 'Blog'. Valid arguments are "
                         "'The+Fix', 'Politics', 'Opinions', 'Post+Politics'. "
                         "Defaults to all")
parser.add_argument('--sleep_time', type=int, default=5,
                    help='Time (in seconds) to wait between queries')
parser.add_argument('--page_timeout', type=int, default=30,
                    help="Time (in seconds) to wait until we stop trying to load "
                         "a page and retry")

PAGE_RANGE = [1, 1000]  # only matters if LINKS_FROM_FILE is false
args = parser.parse_args()
QUERY = args.query
QUERY = QUERY.replace(' ', '+')

SLEEP_TIME = args.sleep_time
PAGE_LOAD_TIMEOUT = args.page_timeout

LINKS_FROM_FILE = False
if len(args.link_file) > 0:
    LINKS_FROM_FILE = args.link_file

if args.from_last == 24:
    FROM_LAST = "24+Hours"
elif args.from_last == 365:
    FROM_LAST = "12+Months"
elif args.from_last == "2005":
    FROM_LAST = "All+Since+2005"
else:
    FROM_LAST = str(args.from_last) + "+Days"

CONTENT_TYPE = "%2C".join(args.doc_type.split(" "))
BLOG_NAME = "%2C".join(args.blog_id.split(" "))

def render(query_url):
    browser = webdriver.PhantomJS()
    browser.set_window_size(1120, 550)

    browser.implicitly_wait(PAGE_LOAD_TIMEOUT)
    browser.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

    try:
        browser.get(query_url)
        html_source = browser.page_source
        browser.quit()
        return html_source

    except TimeoutException:
        # retry
        print("\t\tRetrying page load after {}s timeout".format(PAGE_LOAD_TIMEOUT))
        return render(query_url)


def gen_query_url(page_num=1):
    base_url = "https://www.washingtonpost.com/newssearch/?"
    content = ("query={}&contenttype={}&searchType=&blogName={}"
               "&datefilter={}&sort=Date#page-{}")\
        .format(QUERY, CONTENT_TYPE, BLOG_NAME, FROM_LAST, page_num)
    query_url = base_url + content
    return query_url


def search_wapo(query_url):
    result = render(query_url)
    soup = BeautifulSoup(result)
    return soup


def get_article_links(soup):
    hits = soup.findAll("div", class_="pb-feed-item ng-scope")
    article_links = [hit.findAll("a")[0].attrs['href'] for hit in hits]
    return article_links


def collect_links():
    links = []
    links_fp = './links/wapo_links_{}_{}.txt'\
        .format(CONTENT_TYPE.replace('%2C', '_'), QUERY)

    if not os.path.exists("./links"):
        os.makedirs("./links")

    prev_page_empty = False
    for idx in range(*PAGE_RANGE):
        query_url = gen_query_url(idx)

        time.sleep(SLEEP_TIME)
        soup = search_wapo(query_url)
        new_links = get_article_links(soup)

        print("\tFound {} article links on page {} of query results"
              .format(len(new_links), idx))
        links += new_links

        # the most recent 2 pages are empty, we have run out of query pages!
        if len(new_links) == 0:
            if prev_page_empty:
                return set(links)
            else:
                prev_page_empty = True
        else:
            prev_page_empty = False
            with open(links_fp, 'a') as handle:
                handle.write('\n'.join(new_links) + "\n")

    return set(links)


def construct_article(link):
    article = {"url": link}

    article_obj = Article(url=link, language='en')
    article_obj.download()
    article_obj.parse()

    authors = article_obj.authors
    article['text'] = article_obj.text
    article['title'] = article_obj.title
    article['author'] = authors if len(authors) != 0 else None
    article['urlToImage'] = None
    article['description'] = article_obj.summary

    article['publishedAt'] = None
    article['before_election'] = None

    if article_obj.publish_date:
        date = tz.localize(article_obj.publish_date)
        article['publishedAt'] = date.isoformat()
        article['before_election'] = True if date < ELECTION_DATE else False
    return article


def scrape_articles():
    articles, links = [], []

    print('\n####### Washingtop Post Scraper #######')
    print('Running query:')
    print('Result pages {} - {} of {}s that contain "{}" from last {}\n'
          .format(PAGE_RANGE[0], PAGE_RANGE[1], CONTENT_TYPE, QUERY, FROM_LAST))

    if not LINKS_FROM_FILE:
        links = collect_links()
    else:
        with open(LINKS_FROM_FILE, 'r') as handle:
            for line in handle:
                links.append(line.strip())

    links = [i.strip() for i in set(links) if i.strip() != '']
    print('\nCollected {} links'.format(len(links)))

    for idx, link in enumerate(links):
        print('\t{}. Scraping {}'.format(idx + 1, link))
        time.sleep(SLEEP_TIME)  # for throttling
        article = construct_article(link)
        articles.append(article)

    data = {'articles': articles,
            'source': 'washington-post',
            'status': "ok",
            'query': QUERY,
            'from_last': FROM_LAST,
            'pagerange': PAGE_RANGE}
    return data


def today():
    return datetime.datetime.strftime(datetime.datetime.now(), "%m%d%y")


def save_json(data, save_fp):
    if not os.path.exists("./scraped_json"):
        os.makedirs("./scraped_json")

    with open(save_fp, 'w') as handle:
        json.dump(data, handle, indent=4,
                  sort_keys=True, separators=(',', ':'))


def main():
    date = today()
    data = scrape_articles()
    n = len(data['articles'])

    save_fp = "./scraped_json/{}_{}_{}.json".format('wapo', date, n)
    print('Saving scraped articles to {}'.format(save_fp))
    save_json(data, save_fp)


if __name__ == "__main__":
    main()
