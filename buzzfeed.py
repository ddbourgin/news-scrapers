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
    description='A web scraper for Buzzfeed articles.')

requiredNamed = parser.add_argument_group('required arguments')
requiredNamed.add_argument('-q', '--query', type=str, required=True,
                           help='Query string')

parser.add_argument('-l', '--link_file', type=str, default="",
                    help='Path to newline-delimited collection of article links')
parser.add_argument('-r', '--date_range', type=str, default="",
                    help="A space separated string of dates of the form "
                         "'mm/dd/yyyy mm/dd/yyyy'. Defaults to standard search.")

parser.add_argument('--sleep_time', type=int, default=5,
                    help='Time (in seconds) to wait between queries')
parser.add_argument('--page_timeout', type=int, default=30,
                    help="Time (in seconds) to wait until we stop trying to load "
                         "a page and retry")

PAGE_RANGE = [1, 1000]
args = parser.parse_args()
QUERY = args.query
QUERY = QUERY.replace(' ', '+')

SLEEP_TIME = args.sleep_time
PAGE_LOAD_TIMEOUT = args.page_timeout

LINKS_FROM_FILE = False
if len(args.link_file) > 0:
    LINKS_FROM_FILE = args.link_file

dr = args.date_range
if len(dr) > 0:
    FROM_LAST = dr.split(' ')
else:
    FROM_LAST = None


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
        print("\t\tRetrying page load after {}s timeout".format(PAGE_LOAD_TIMEOUT))
        return render(query_url)


def gen_query_url(page_num=1):
    base_url = "https://www.buzzfeed.com/tag"
    content = "{}?p={}".format(QUERY, page_num)
    query_url = os.path.join(base_url, content)
    return query_url


def search_buzzfeed(query_url):
    result = render(query_url)
    soup = BeautifulSoup(result)
    return soup


def get_article_links(soup):
    base = "https://www.buzzfeed.com"
    hits = soup.findAll("article")
    article_links = [hit.findAll("a")[0].attrs['href'] for hit in hits]
    article_links = [base + link for link in article_links]
    return article_links


def get_archive_links(soup):
    base = "https://www.buzzfeed.com"
    hits = soup.findAll("ul", class_="flow")
    link_data = [(a.attrs['title'], a.contents[0], a.attrs['href']) for a in
                 hits[0].findAll("a")]

    links = []
    for lede, title, link in link_data:
        if QUERY.replace("+", " ").lower() in lede.lower():
            links.append(link)
        elif QUERY.replace("+", " ").lower() in title.lower():
            links.append(link)

    archive_links = [base + link for link in links]
    return archive_links


def date_range(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + datetime.timedelta(n)


def gen_archive_url(yy, mm, dd):
    base_url = "https://www.buzzfeed.com/archive/"
    content = "{}/{}/{}".format(yy, mm, dd)
    query_url = os.path.join(base_url, content)
    return query_url


def search_buzzfeed_archive():
    from_month, from_day, from_year = [int(i) for i in FROM_LAST[0].split('/')]
    to_month, to_day, to_year = [int(i) for i in FROM_LAST[1].split('/')]

    start_date = datetime.date(from_year, from_month, from_day)
    end_date = datetime.date(to_year, to_month, to_day)

    dates = []
    for date in date_range(start_date, end_date):
        dates.append([int(i) for i in date.strftime("%Y-%m-%d").split('-')])

    links = []
    links_fp = './links/buzzfeed_links_{}_{}-{}.txt'\
        .format(QUERY,
                datetime.datetime.strftime(start_date, "%m%d%y"),
                datetime.datetime.strftime(end_date, "%m%d%y"))

    for year, month, day in dates:
        archive_url = gen_archive_url(year, month, day)

        time.sleep(SLEEP_TIME)
        soup = search_buzzfeed(archive_url)
        new_links = get_archive_links(soup)

        print("\tFound {} article links for archive date {}"
              .format(len(new_links), "{}/{}/{}".format(month, day, year)))
        links += new_links

        with open(links_fp, 'a') as handle:
            handle.write('\n'.join(new_links) + "\n")
    return set(links)


def collect_links():
    links = []
    links_fp = './links/buzzfeed_links_{}.txt'.format(QUERY)

    if not os.path.exists("./links"):
        os.makedirs("./links")

    # if user passes a date range, we have to search the buzzfeed
    # archives rather than running a search query
    if isinstance(FROM_LAST, list):
        return search_buzzfeed_archive()

    prev_page_empty = False
    for idx in range(*PAGE_RANGE):
        query_url = gen_query_url(idx)

        time.sleep(SLEEP_TIME)
        soup = search_buzzfeed(query_url)
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

    print('\n####### Buzzfeed Scraper #######')
    print('Running query:')
    if not FROM_LAST:
        print('Scraping recent pages with the tag "{}"\n'.format(QUERY))
    else:
        print('Scraping pages which contain "{}" from archives between '
              '{} and {}\n'.format(QUERY, *args.date_range.split(' ')))

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
            'source': 'buzzfeed',
            'status': "ok",
            'query': QUERY,
            'from_last': None,
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

    save_fp = "./scraped_json/{}_{}_{}.json".format('buzzfeed', date, n)
    print('Saving scraped articles to {}'.format(save_fp))
    save_json(data, save_fp)


if __name__ == "__main__":
    main()
