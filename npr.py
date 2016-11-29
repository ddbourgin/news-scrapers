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


parser = argparse.ArgumentParser(
    description='A web scraper for NPR News articles.')

requiredNamed = parser.add_argument_group('required arguments')
requiredNamed.add_argument('-q', '--query', type=str, required=True,
                           help="Query string")

parser.add_argument('-l', '--link_file', type=str, default="",
                    help="Path to a newline-delimited file of article links "
                         "to scrape")
parser.add_argument('-f', '--from_last', type=int, default=30,
                    help="Pull articles from last X. Valid values are 24[hours], "
                         "7[days], 30[days], 42[days], 365[days], or 0[all dates]")

parser.add_argument('--sleep_time', type=int, default=5,
                    help="Time (in seconds) to wait between queries")
parser.add_argument('--page_timeout', type=int, default=30,
                    help="Time (in seconds) after which we stop trying to load "
                         "a page and retry")
parser.add_argument('--sort_by', type=str, default="newest",
                    help="Metric for ordering search results. Valid arguments are "
                         "'newest' or 'relevance'")
parser.add_argument('--section', type=str, default="all",
                    help="Section of NPR to pull articles from. Valid arguments "
                         "are 'all', 'All Songs Considered', 'All Things Considered', "
                         "'Ask Me Another', 'Fresh Air', 'Invisibilia', 'Latino USA', "
                         "'Morning Edition', 'Snap Judgment', or 'TED Radio Hour', "
                         "'Weekend Edition - Saturday', 'Weekend Edition - Sunday', "
                         "'Wait Wait... Don't Tell Me!', and 'World Cafe'")

def parse_args(parser):
    args = parser.parse_args()
    QUERY = args.query
    QUERY = QUERY.replace(' ', '+')

    SLEEP_TIME = args.sleep_time
    PAGE_LOAD_TIMEOUT = args.page_timeout

    if args.sort_by == 'newest':
        SORT_BY = 'date'
    else:
        SORT_BY = 'match'

    LINKS_FROM_FILE = False
    if len(args.link_file) > 0:
        LINKS_FROM_FILE = args.link_file

    if args.from_last == 24:
        FROM_LAST = 1
    else:
        FROM_LAST = args.from_last

    show_ids = {'All Songs Considered': 37,
                'All Things Considered': 2,
                'Ask Me Another': 58,
                'Fresh Air': 13,
                'Invisibilia': 64,
                'Latino USA': 22,
                'Morning Edition': 3,
                'Snap Judgment': 62,
                'TED Radio Hour': 57,
                'Weekend Edition - Saturday': 7,
                'Weekend Edition - Sunday': 10,
                "Wait Wait... Don't Tell Me!": 35,
                'World Cafe': 39}

    SECTION = args.section
    if SECTION == "all":
        SECTION = ""
    elif SECTION in show_ids:
        SECTION = show_ids[SECTION]
    else:
        raise ValueError('Did not recognize section name {}'.format(SECTION))

    return QUERY, SLEEP_TIME, PAGE_LOAD_TIMEOUT, SORT_BY, LINKS_FROM_FILE, \
        FROM_LAST, SECTION


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
    base = "http://www.npr.org/search/index.php?"
    content = "searchinput={}&dateId={}&programId={}&sort={}&start={}"\
        .format(QUERY, FROM_LAST, SECTION, SORT_BY, 10 * (page_num - 1))
    query_url = base + content
    return query_url


def search_npr(query_url):
    result = render(query_url)
    soup = BeautifulSoup(result)
    return soup


def get_article_links(soup):
    hits = soup.findAll("article", class_="item")
    article_links = [hit.findAll("a")[0].attrs["href"] for hit in hits]
    return article_links


def collect_links():
    links = []
    prev_page_empty = False
    links_fp = './links/npr_links_{}.txt'.format(QUERY)

    if not os.path.exists("./links"):
        os.makedirs("./links")

    for idx in range(*PAGE_RANGE):
        query_url = gen_query_url(idx)

        time.sleep(SLEEP_TIME)
        soup = search_npr(query_url)
        new_links = get_article_links(soup)

        print("\tFound {} article links on page {} of query results"
              .format(len(new_links), idx))
        links += new_links

        # if the most recent 2 pages are empty, we have run out of query pages!
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
    froml = 'from last {} days'.format(FROM_LAST) if FROM_LAST != 0 else ""

    print('\n####### NPR Scraper #######')
    print('Running query:')
    print('Result pages {} - {} of {} articles that contain "{}" {}\n'
          .format(PAGE_RANGE[0], PAGE_RANGE[1], SECTION, QUERY, froml))

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
            'source': 'national-public-radio',
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

    save_fp = "./scraped_json/{}_{}_{}.json".format('npr', date, n)
    print('Saving scraped articles to {}'.format(save_fp))
    save_json(data, save_fp)

if __name__ == "__main__":
    tz = pytz.utc
    PAGE_RANGE = [1, 1000]
    ELECTION_DATE = datetime.datetime(2016, 11, 9, 11, tzinfo=tz)
    QUERY, SLEEP_TIME, PAGE_LOAD_TIMEOUT, SORT_BY, LINKS_FROM_FILE, \
        FROM_LAST, SECTION = parse_args(parser)

    main()
