from argparse import ArgumentParser
from classes import StoppableThread
from utils import SUPPORTED_MODES, SUPPORTED_PAGES, get_url, thread_runner
from methods import bot_runner, process_offers, read_pages
from queue import Queue


# ---------- Parsing provided arguments ----------
parser = ArgumentParser()

parser.add_argument("--all", dest="all", default=False, const=True, action="store_const",
                    help="adds every page and every mode")
parser.add_argument("--bot", dest="bot", default=None, nargs=2, metavar=("settings_file", "configs_dir"),
                    help="bot settings file start Telegram bot")
parser.add_argument("--output", dest="output", default=None, metavar="output_file",
                    help="output file where offers are saved")

for page_name in SUPPORTED_PAGES:
    parser.add_argument("--%s" % page_name, dest=page_name, choices=SUPPORTED_MODES, default=[], nargs="+",
                        help="what should be tracked from %s" % page_name)

# Write down choices
selection = vars(parser.parse_args())

# For each page add selected modes (or add all if it was chosen to do so)
urls = []
for page_name in SUPPORTED_PAGES:
    for mode in (SUPPORTED_MODES if selection.get("all") else selection.get(page_name)):
        urls.append(get_url(page_name, mode))


# ---------- Variables initialization ----------
thread_statuses = {}         # dictionary holds names of all threads and information what they are up to
threads = []                 # list of threads
read_offers_queue = Queue()  # offers read by page reader
offers_queue = Queue()       # offers for bot

# ---------- Defining threads ----------
# Page reading threads
for i in range(len(urls)):
    threads.append(
        StoppableThread(
            target=read_pages,
            args=(thread_statuses, urls[i], read_offers_queue),
            name="Reader %d" % i))
    
# Worker thread
thr_worker = StoppableThread(
    target=process_offers,
    args=(thread_statuses, read_offers_queue, offers_queue, selection.get("output"),
          selection.get("bot")[0] if selection.get("bot") is not None else None),
    name="Worker")
# Start worker only if there is a reader
if len(threads) > 0:
    threads.append(thr_worker)

# Bot thread (started only if it was selected)
if selection.get("bot") is not None:
    thr_bot = StoppableThread(
        target=bot_runner,
        args=(thread_statuses, offers_queue, selection.get("bot")[0], selection.get("bot")[1]),
        name="Bot")
    threads.append(thr_bot)


# ---------- Running the threads ----------
if len(threads) == 0:
    exit("No threads were started due to lack of selected options. For help add an -h / --help argument.")
thread_runner(threads, thread_statuses)
