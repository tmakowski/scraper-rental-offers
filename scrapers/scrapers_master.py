from datetime import datetime
from utils import SUPPORTED_PAGES
from scrapers.scrapers_gumtree import *
from scrapers.scrapers_olx import *


class ScraperMissingException(Exception):
    def __init__(self, message):
        super().__init__(message)


def scraper_master(url, offer):

    for page_name in SUPPORTED_PAGES:
        if url.find("%s." % page_name) != -1:
            try:
                response = eval("scraper_%s%s('%s')" % ("main_" if not offer else "", page_name, url))
                response["scrape_time"] = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
                return response
            except Exception as err:
                pass

    raise ScraperMissingException("No suitable scrapers were found for URL: %s" % url)
