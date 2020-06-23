from utils import get_page
import re


def scraper_main_gumtree(url):
    """ Reads pages with offers from GumTree and provides URLS to said offers. """

    # Loading the page
    page = get_page(url)

    # Putting the offer's URLs together
    offers = page.element("div[class='view'] div[class='title'] a")

    return {
        "url": url,
        "offers_urls": ["https://www.gumtree.pl" + off.attrib.get("href") for off in offers]
    }


def scraper_gumtree(url):
    """ Extracts the relevant information from provided offer page. """
    page = get_page(url)

    # Extracting price
    try:
        price = int("".join([
            d for d
            in page.find("div[class=vip-content-header] span[class=value]", first=True).text
            if d.isdigit()
        ]))
    except ValueError:
        price = None
    except AttributeError:
        price = None

    # Extracting images' url list
    try:
        url_img_dict = dict(eval(
            page.find("script[id=vip-gallery-data]", first=True).text
        ))
        url_img_large_str = url_img_dict["large"]
        url_img_list = (url_img_large_str[1:-1]).split(", ")
    except Exception:
        url_img_list = None

    # Extracting attributes' name and values
    attr_dict = dict(zip(
        [name.text for name in page.find("div[class=vip-details] span[class=name]")],
        [val.text for val in page.find("div[class=vip-details] span[class=value]")]
    ))

    # Adding the localisation if it wasn't added before
    if "Lokalizacja" in attr_dict.keys():
        loc = re.search("[^,]*", attr_dict["Lokalizacja"]).group()
    else:
        loc = None

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

    # Saving flat's measurement
    try:
        size = int(attr_dict.get("Wielkość (m2)"))
    except ValueError:
        size = None
    except TypeError:
        size = None

    # Checking if it's room offer
    is_room = url.find("pokoje-do-wynajecia") != -1

    # Reading room's preference
    preferred_group = attr_dict.get("Preferowana płeć")

    # Reading what is being shared
    sharing_type = attr_dict.get("Współdzielenie")

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
        "sharing_type": sharing_type,
        "room_type": None
    }
