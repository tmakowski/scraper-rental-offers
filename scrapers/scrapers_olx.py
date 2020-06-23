from utils import get_page
import re


def scraper_main_olx(url):
    """ Reads pages with offers from OLX and provides URLS to said offers. """

    def __create_url_olx(offs_ids, prefix="https://www.olx.pl"):
        """ Method creates an olx offer link from parts read from a main page. """
        return [
            "/".join([
                prefix,
                "oferta",
                "CID3-ID" + o_id + ".html"
            ])
            for o_id in offs_ids
        ]

    # Loading the page
    page = get_page(url)

    # Reading the offers' ids
    offers_ids = [
        re.search("[^_]*$", off.attrib["class"]).group()[2:]
        for off in page.element("table[id=offers_table] table[summary=Ogłoszenie]")
    ]

    return {
        "url": url,
        "offers_urls": __create_url_olx(offers_ids)
    }


def scraper_olx(url):
    """ Extracts the relevant information from provided offer page. """
    page = get_page(url)

    # Reading the images url list
    url_img_list = [
        re.search("[^;]*", elem.attrib["src"]).group()
        for elem in page.element("div[class=photo-glow] img")]

    # Extracting price
    try:
        price = int("".join([
            d for d
            in page.find("div[class=price-label]", first=True).text
            if d.isdigit()
        ]))
    except ValueError:
        price = None
    except AttributeError:
        price = None

    # Reading the location
    try:
        loc_raw = page.find("a[class=show-map-link]", first=True).text
        loc = re.search("^[^, ]*", loc_raw).group()

        if loc == "Warszawa":
            loc = re.search("[^, ]*$", loc_raw).group()  # Save district if it's Warsaw
            loc = loc.replace("-", " ")

    except AttributeError:
        loc = None

    # Reading the attributes
    try:
        attr_dict = dict([e.text.split(sep="\n")
                          for e in page.find("div[id=offerdescription] table[class=item]")])
    except ValueError:
        attr_dict = {}

    # Reading number of rooms
    rooms = attr_dict.get("Liczba pokoi")
    try:
        if rooms is None:
            rooms_number = None
        else:
            rooms_number_raw = re.search("[0-9]*", rooms).group()
            rooms_number = int(rooms_number_raw) if len(rooms_number_raw) > 0 else 0
    except ValueError:
        rooms_number = None
    except TypeError:
        rooms_number = None

    # Reading the size of the flat
    size_raw = attr_dict.get("Powierzchnia")
    try:
        size = int(re.search("[0-9]*", size_raw).group())
    except ValueError:
        size = None
    except TypeError:
        size = None

    # Checking if it's room offer
    try:
        is_room = page.element("div[class='wrapper'] td li")[-1].find("a").attrib.get("href")\
                      .find("stancje-pokoje") != -1
    except IndexError:
        is_room = None

    # Reading room's preference
    preferred_group = attr_dict.get("Preferowani")

    # Reading room type
    room_type = attr_dict.get("Rodzaj pokoju")

    return {
        "url": url,
        "is_room": is_room,
        "price": price,
        "loc": loc,
        "rooms_info": rooms,
        "rooms": rooms_number,
        "size": size,
        "images_urls_list": url_img_list,
        "preferred_group": preferred_group,
        "sharing_type": None,
        "room_type": room_type
    }
