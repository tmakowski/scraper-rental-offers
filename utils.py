from datetime import datetime as dt
from numpy import concatenate, unique
from os.path import isfile
from pandas import read_csv
from requests import get
from requests.exceptions import ConnectionError
from requests_html import HTMLSession, MaxRetries
from time import sleep


SUPPORTED_MODES = ["rooms", "flats"]
SUPPORTED_PAGES = ["gumtree", "olx"]
URLS = {
    "gumtree": {
        # Poland:
        # "flats": "https://www.gumtree.pl/s-mieszkania-i-domy-do-wynajecia/v1c9008p1",
        # "rooms": "https://www.gumtree.pl/s-pokoje-do-wynajecia/v1c9000p1"

        # Masovian Voivodeship:
        "flats": "https://www.gumtree.pl/s-mieszkania-i-domy-do-wynajecia/mazowieckie/v1c9008l3200001p1",
        "rooms": "https://www.gumtree.pl/s-pokoje-do-wynajecia/mazowieckie/v1c9000l3200001p1"
    },
    "olx": {
        # Poland:
        # "flats": "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/",
        # "rooms": "https://www.olx.pl/nieruchomosci/stancje-pokoje/"

        # Masovian Voivodeship:
        "flats": "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/mazowieckie/",
        "rooms": "https://www.olx.pl/nieruchomosci/stancje-pokoje/mazowieckie/"
    }
}


class GetPageException(Exception):
    def __init__(self, message):
        super().__init__(message)


class SomeOtherException(Exception):
    def __init__(self, message):
        super().__init__(message)


def get_page(url, recursion=0, retry_after=5):
    if recursion > 2:
        raise GetPageException("Get page method failed too many times.")

    try:
        # Creating a new session
        session = HTMLSession()

        # Loading the page to a variable
        page = session.get(url).html
        session.close()

        return page

    except MaxRetries:
        sleep(retry_after)
        return get_page(url, recursion+1)

    except ConnectionError:
        sleep(retry_after)
        return get_page(url, recursion + 1)

    except Exception as err:  # We just skip page in this iteration and try to save
        with open("simple_get_page_log.txt", "a", encoding="utf-8") as lf:
            print(
                "[%s] Error message: %s" % (dt.now().strftime("%Y-%m-%d, %H:%M:%S"), err),
                end="\n%s\n" % ("-"*20),
                file=lf)


def get_url(page_name, mode):
    assert page_name in SUPPORTED_PAGES
    assert mode in SUPPORTED_MODES

    return URLS.get(page_name).get(mode)


def is_duplicate(file_path, key, value):
    """ Method returns information if given value of chosen key is a duplicate to selected file.
    Note: method assumes that key values in file are already unique. """
    def __is_duplicate(el_array, new_el):
        return len(unique(concatenate((el_array, [new_el])))) != len(el_array) + 1

    # If the file does not exist the current value is not a duplicate
    if file_path is None or not isfile(file_path):
        return False

    return __is_duplicate(
        read_csv(file_path,
                 names=["url", "is_room", "price", "loc", "rooms_info", "rooms", "size", "images_urls_list",
                        "scrape_time", "preferred_group", "sharing_type", "room_type"]).loc[:, key],
        value)


def send_message(bot_token, chat_id, text_body):
    url = "https://api.telegram.org/bot%s/sendMessage?text=%s&chat_id=%d" % (bot_token, text_body, chat_id)
    get(url)


def thread_runner(threads, thread_statuses):
    """ Method used by main script to run, monitor and stop threads. """

    # Starting the threads
    for thr in threads:
        thr.start()

    # Printing table's header
    print("|%s|" % "|".join([" %-8s " % thr for thr in thread_statuses.keys()]))
    print("|%s|" % "|".join(["-"*10 for thr in thread_statuses]))

    try:
        # Keep printing status of the threads
        while True:
            print("\r|%s|" % "|".join([" %-8s " % status for status in thread_statuses.values()]), end="")

    except KeyboardInterrupt:
        # Stop the threads
        for thr in threads:
            thr.stop()

        # Keep printing statuses as long as there is a thread alive
        while any([thr.is_alive() for thr in threads]):
            print("\r|%s|" % "|".join([" %-8s " % status for status in thread_statuses.values()]), end="")

    finally:
        # Print last status when everything is finished
        print("\r|%s|" % "|".join([" %-8s " % status for status in thread_statuses.values()]))
