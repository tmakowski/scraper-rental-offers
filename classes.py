from csv import DictWriter
from scrapers.scrapers_master import scraper_master
from threading import Event, Thread


class Offer:
    """ Class used to manage the offers. It holds all the important information from given offer. """
    def __init__(self, url):
        self.scrape_dict = scraper_master(url, offer=True)

    def __dir__(self):
        return ["url", "is_room", "price", "loc", "rooms_info", "rooms", "size", "images_urls_list",
                "scrape_time", "preferred_group", "sharing_type", "room_type"]

    def __getattr__(self, item):
        if item not in self.scrape_dict.keys():
            raise AttributeError("type object 'Offer' has no attribute '%s'" % item)
        return self.scrape_dict.get(item)

    def __repr__(self):
        return "Offer('%s')" % self.url

    def __str__(self):
        return "\n".join(["%-17s%s" % (k, v) for (k, v) in self.scrape_dict.items() if k != "images_urls_list"])

    def save_to_file(self, file_name):
        """ Method to save offers basic information to the database.
         Note: it neither does save information about images nor images themselves. """

        with open(file_name, "a", encoding="utf-8") as out_file:
            writer = DictWriter(out_file, self.__dir__())
            writer.writerow(self.scrape_dict)


class Page:
    """ Class used by reader threads to manage pages of offers.
    Iterating over the Page will return consecutive URLs it contains."""
    def __init__(self, url, offers_urls_arg=None):
        """ This constructor uses scrapers to retrieve list of offers' URLs from a page with given URL. """

        if offers_urls_arg is None:
            scrape_dict = scraper_master(url, offer=False)
            for (attr, attr_value) in scrape_dict.items():
                self.__setattr__(attr, attr_value)
        else:
            self.url = url
            self.offers_urls = offers_urls_arg
            self.scrape_time = None  # Since it was not actually scraped

    def __getitem__(self, item):
        return self.offers_urls[item]

    def __iter__(self):
        self.iter_index = 0
        return self

    def __next__(self):
        try:
            result = self.offers_urls[self.iter_index]
        except IndexError:
            raise StopIteration
        self.iter_index += 1
        return result

    def __repr__(self):
        return "Page('%s', %s)" % (self.url, self.offers_urls)

    def __str__(self):
        return "[%s]" % ",\n ".join([url_.__repr__() for url_ in self.offers_urls])  # Formatting the list to look clean

    def __sub__(self, other):
        """ Used to get the set difference of URLs between two pages.
        I.e. (page_A-page_B) will return only the URLs which the page_A contains and the page_B doesn't. """
        assert self.url == other.url  # Subtraction of two different pages does not make too much sense
        return Page(self.url, list(set(self.offers_urls) - set(other.offers_urls)))

    def create_offers(self):
        """ Convenient method for creating Offer objects based on every offer URL this page holds. """
        return [Offer(url) for url in self.offers_urls]


class StoppableThread (Thread):
    """ A thread class with an additional stop() method.
    The thread is supposed to use a is_stopped() method to check regularly whether it is supposed to stop already. """

    def __init__(self, **kwargs):
        """ A created thread has an additional field which determines whether the thread has already been stopped. """
        super().__init__(**kwargs)
        self.__stop_event = Event()

    def stop(self):
        """ A method setting the stop field. """
        self.__stop_event.set()

    def is_stopped(self):
        """ The method used to check from within the thread whether it has been stopped already. """
        return self.__stop_event.is_set()
