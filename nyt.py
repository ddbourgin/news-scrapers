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
    description='A web scraper for New York Times articles.')

requiredNamed = parser.add_argument_group('required arguments')
requiredNamed.add_argument('-q', '--query', type=str, required=True,
                           help='Query string')

parser.add_argument('-l', '--link_file', type=str, default="",
                    help='Path to a newline-delimited file of article links '
                         'to scrape')
parser.add_argument('-r', '--date_range', type=str, default="",
                    help="A space separated string of dates of the form "
                         "'mm/dd/yyyy mm/dd/yyyy'. Takes precedence over --from_last.")
parser.add_argument('-f', '--from_last', type=int, default=30,
                    help="Pull articles from last X. Valid values are 24[hours], "
                         "7[days], 30[days], 365[days]")
parser.add_argument('-t', '--doc_type', type=str, default="article",
                    help='Type of article to scrape. Valid arguments are "Article", '
                         '"Multimedia", "Blog", "Interactive", "Video" or '
                         '"allresults"')

parser.add_argument('--sleep_time', type=int, default=5,
                    help='Time (in seconds) to wait between queries')
parser.add_argument('--page_timeout', type=int, default=30,
                    help="Time (in seconds) after which we stop trying to load "
                         "a page and retry")
parser.add_argument('--sort_by', type=str, default="newest",
                    help='Metric for ordering search results. Valid arguments are '
                         '"newest", "oldest", or "relevance"')
parser.add_argument('--section', type=str, default="all",
                    help='Section of NYT to pull articles from. Valid arguments '
                         'are "all", "U.S.", "New York and Region", "Opinion", '
                         '"Arts", "Briefing", or "Business Day"')

PAGE_RANGE = [1, 1000]  # only matters if LINKS_FROM_FILE is false

args = parser.parse_args()
QUERY = args.query
QUERY = QUERY.replace(' ', '+')

SLEEP_TIME = args.sleep_time
PAGE_LOAD_TIMEOUT = args.page_timeout
SORT_BY = args.sort_by

LINKS_FROM_FILE = False
if len(args.link_file) > 0:
    LINKS_FROM_FILE = args.link_file

dr = args.date_range
if len(dr) > 0:
    FROM_LAST = dr.split(' ')
    from_month, from_day, from_year = [int(i) for i in FROM_LAST[0].split('/')]
    to_month, to_day, to_year = [int(i) for i in FROM_LAST[1].split('/')]
    FROM_LAST = "from{}{:02}{:02}to{}{:02}{:02}"\
        .format(from_year, from_month, from_day, to_year, to_month, to_day)
else:
    if args.from_last == 24:
        FROM_LAST = "24hours"
    else:
        FROM_LAST = str(args.from_last) + "days"

func = "document_type"
DOCUMENT_TYPE = args.doc_type.lower()
if DOCUMENT_TYPE != "allresults":
    if DOCUMENT_TYPE == "interactive":
        DOCUMENT_TYPE = "Interactive%20Feature"
        func = "type_of_material"
    elif DOCUMENT_TYPE == "blog":
        DOCUMENT_TYPE = "blogpost"

    DOCUMENT_TYPE = "{}%3A%22{}%22".format(func, DOCUMENT_TYPE.lower())

SECTION = args.section
if SECTION == "all":
    SECTION = ""
else:
    SECTION = SECTION.replace(" ", "%20")

def render(query_url):
    browser = webdriver.PhantomJS()
    browser.implicitly_wait(PAGE_LOAD_TIMEOUT)
    browser.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    browser.set_window_size(1120, 550)

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
    base = "http://query.nytimes.com/search/sitesearch/#/"
    content = "{}/{}/{}/{}/allauthors/{}"\
        .format(QUERY, FROM_LAST, DOCUMENT_TYPE, page_num, SORT_BY)
    query_url = os.path.join(base, content)
    return query_url


def search_nyt(query_url):
    result = render(query_url)
    soup = BeautifulSoup(result)
    return soup


def get_article_links(soup):
    hits = soup.findAll("ol", class_="searchResultsList flush")
    article_links = [hit.attrs["href"] for hit in hits[0].findAll("a")]
    return article_links


def collect_links():
    links = []
    prev_page_empty = False
    links_fp = './links/nyt_links_{}_{}.txt'\
        .format(DOCUMENT_TYPE.replace("document_type", "")\
                             .replace("%3A", "")\
                             .replace("%22", ""),
                QUERY)

    if not os.path.exists("./links"):
        os.makedirs("./links")

    for idx in range(*PAGE_RANGE):
        query_url = gen_query_url(idx)

        time.sleep(SLEEP_TIME)
        soup = search_nyt(query_url)
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
    dtype = DOCUMENT_TYPE.replace("document_type", "")\
                         .replace("%3A", "")\
                         .replace("%22", "")
    froml = FROM_LAST.replace("from", "").replace("to", " - ")

    print('\n####### New York Times Scraper #######')
    print('Running query:')
    print('Result pages {} - {} of {}s that contain "{}" from last {}\n'
          .format(PAGE_RANGE[0], PAGE_RANGE[1], dtype, QUERY, froml))

    if not LINKS_FROM_FILE:
        links = collect_links()
    else:
        with open(LINKS_FROM_FILE, 'r') as handle:
            for line in handle:
                links.append(line.strip())

    # de-dupe links
    links = [i.strip() for i in set(links) if i.strip() != '']

    print('\nCollected {} links'.format(len(links)))

    for idx, link in enumerate(links):
        print('\t{}. Scraping {}'.format(idx + 1, link))
        time.sleep(SLEEP_TIME)  # for throttling
        article = construct_article(link)
        articles.append(article)

    data = {'articles': articles,
            'source': 'new-york-times',
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

    save_fp = "./scraped_json/{}_{}_{}.json".format('nyt', date, n)
    print('Saving scraped articles to {}'.format(save_fp))
    save_json(data, save_fp)

if __name__ == "__main__":
    main()
