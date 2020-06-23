from bot import TelegramBot
from classes import Offer, Page
from json import load
from scrapers.scrapers_master import ScraperMissingException
from threading import current_thread
from time import sleep
from utils import GetPageException, is_duplicate, send_message


def read_pages(thread_statuses, url, q_read, interval=30):
    """ A method used to track the given URL and put read offers to a queue.
    :param thread_statuses: used for debugging and checking up on threads
    :param url: address to listen to
    :param q_read: queue of read offers passed to the function processing them
    :param interval: time in seconds between two consecutive refreshes of the page
    """
    thread_statuses[current_thread().name] = "Booting"

    # Save a current version of the page
    page_old = Page(url)

    # Work until the thread has been stopped by parent process
    while not current_thread().is_stopped():
        thread_statuses[current_thread().name] = "Working"

        # One error retry getting the same page
        try:
            page = Page(url)
        except GetPageException:
            continue
        except ScraperMissingException:
            continue

        # Append each new offer to processing queue
        for offer_url in (page - page_old):
            q_read.put(offer_url)

        # Save current page so we can track which offers are new
        page_old = page

        # Wait before refreshing the page and keep updating the status
        for i in range(interval):
            thread_statuses[current_thread().name] = "Wait %02d" % (interval - i)
            sleep(1)
            if current_thread().is_stopped():
                break

    thread_statuses[current_thread().name] = "Stopped"


def process_offers(thread_statuses, q_read, q_offers, db_file, bot_settings_file):
    """ Function processes offers from the read queue and saves them under specified path.
    :param thread_statuses: used for debugging and checking up on threads
    :param q_read: queue of read offers
    :param q_offers: queue of offer objects passed to bot
    :param db_file: file where the offers should be saved
    :param bot_settings_file: json file which contains bot token
    """
    thread_statuses[current_thread().name] = "Booting"
    trouble_meter = 0
    p = 0
    if bot_settings_file is not None:
        with open(bot_settings_file, "r", encoding="utf-8") as sf:
            bot_token = load(sf).get("token")

    # Work until the thread has been stopped by parent process
    while not current_thread().is_stopped():
        thread_statuses[current_thread().name] = "Waiting"

        while q_read.qsize() > 0:
            if bot_settings_file is not None:
                # Send notification if offers are piling up
                if q_read.qsize() // 100 > trouble_meter:
                    trouble_meter += 1
                    send_message(bot_token, 87974246, "Liczba ofert w kolejce wzrasta: %s" % q_read.qsize())
                    if db_file is not None and trouble_meter > 0:
                        with open(db_file, "r", encoding="utf-8") as dbf:
                            if len(dbf.readlines()) > 10000:
                                p += 1
                                db_file = db_file.replace("_p%02d.csv" % (p - 1), "_p%02d.csv" % p)
                                send_message(bot_token, 87974246, "Nowy plik utworzony: %s" % db_file)

                # Send notifications if offers pile-up is getting worked through
                elif q_read.qsize() // 100 < trouble_meter:
                    trouble_meter -= 1
                    send_message(bot_token, 87974246, "Liczba ofert w kolejce maleje: %s" % q_read.qsize())

            # Read URL and update status
            thread_statuses[current_thread().name] = "Work %02d" % q_read.qsize()
            url = q_read.get()

            # Check if it's duplicate
            if is_duplicate(db_file, "url", url):
                continue

            # Reading and processing the offer
            try:
                offer = Offer(url)
                q_offers.put(offer)
                if db_file is not None:
                    offer.save_to_file(db_file)

            # Skip the offer if we were unable to retrieve the page or if the page is not supported
            except ScraperMissingException:
                pass
            except GetPageException:
                pass

    thread_statuses[current_thread().name] = "Stopped"


def bot_runner(thread_statuses, q_offer, bot_settings_file, bot_configs_dir):
    """ Function creates a Telegram Bot and supplies it with offers from q_offer queue.
    :param thread_statuses: used for debugging and checking up on threads
    :param q_offer: offers which are supplied to the bot
    :param bot_settings_file: settings file path
    :param bot_configs_dir: configs directory path
    """
    # Starting the bot
    thread_statuses[current_thread().name] = "Booting"
    try:
        bot = TelegramBot(bot_settings_file, bot_configs_dir)
    except Exception as err:
        thread_statuses[current_thread().name] = "Error -- %s" % err.__str__()
        return
    bot.start()

    while not current_thread().is_stopped():
        thread_statuses[current_thread().name] = "Waiting"

        while q_offer.qsize() > 0:
            # Get an offer and update status
            thread_statuses[current_thread().name] = "Work %02d" % q_offer.qsize()
            offer = q_offer.get()

            # Process the offer (and send it if that's needed
            bot.process_offer(offer)

    bot.stop()
    thread_statuses[current_thread().name] = "Stopped"
