from datetime import datetime as dt
from telegram.ext import CommandHandler, Updater
from telegram.error import InvalidToken
from os.path import isdir, isfile, join
import json


DEFAULT_CONFIG = {
    "online": False,
    "chat_admins": [],
    "fav": [],
    "loc": [],
    "price": {"min": float("-inf"), "max": float("inf")},
    "size": {"min": float("-inf"), "max": float("inf")},
    "rooms": {"min": float("-inf"), "max": float("inf")},
    "mode": None  # is_room equivalent
}


class TelegramBot:
    def __init__(self, bot_settings_file, users_configs_dir):
        # Assert that token file exists
        if not isfile(bot_settings_file):
            raise Exception("settings file does not exist")

        # Assert that configs directory exists
        if not isdir(users_configs_dir):
            raise Exception("configs dir does not exist")

        # Save locations of files
        self.settings_file = bot_settings_file
        self.configs_dir = users_configs_dir

        # Load bot settings
        with open(bot_settings_file, "r", encoding="utf-8") as sf:
            self.bot_settings = json.load(sf)
            if set(self.bot_settings.keys()) != {"token", "bot_admins", "chat_ids"}:
                Exception("incorrect bot config file")

        # Defining the bot's updater
        try:
            self.updater = Updater(token=self.bot_settings.get("token"),
                                   request_kwargs={'read_timeout': 60, 'connect_timeout': 60})
        except InvalidToken:
            raise Exception("invalid token")

        # Loading chat configs
        self.configs = {}
        for chat_id in self.get_chat_ids():
            self.load_config(chat_id)

        # Adding handlers and job queue
        self.add_command_handlers()
        self.add_message_handlers()
        self.start_timestamp = None

    # ------------------------------ User's config methods ------------------------------
    def get_config(self, chat_id, key=None):
        """ Method returns user config or config's specific key's value. """
        user_config = self.configs.get(chat_id)

        # Returns key value only if config exists
        return user_config if key is None or user_config is None else user_config.get(key)

    def load_config(self, chat_id):
        """ Method loads the chat config. """
        config_path = join(self.configs_dir, "%s.json" % chat_id)

        # If config file does not exist then create one
        if not isfile(config_path):
            self.save_config(chat_id, default=True)

        # Load the config file
        with open(config_path, "r", encoding="utf-8") as cfg_file:
            self.configs[chat_id] = json.load(cfg_file)

        # Add new keys if present
        new_keys = set(DEFAULT_CONFIG.keys()) - set(self.get_config(chat_id).keys())
        if new_keys != set():
            for new_key in new_keys:
                self.configs[chat_id][new_key] = DEFAULT_CONFIG.get(new_key)
            self.save_config(chat_id)

        return self

    def save_config(self, chat_id, default=False):
        """ Method saves chat's config to a file or creates a new config file if one does not exist yet. """
        config_path = join(self.configs_dir, "%s.json" % chat_id)

        # Save either default or user's config
        with open(config_path, "w", encoding="utf-8") as cfg_file:
            json.dump(DEFAULT_CONFIG if default else self.get_config(chat_id), cfg_file, indent=4)

        return self

    def update_config(self, chat_id, key, value, add=None):
        """ Function modifies config's values corresponding to provided key. """
        # Adding/removing a value from parameter which contains list
        if key in ["loc", "chat_admins", "fav"] and add is not None:
            if add:
                if isinstance(value, list):  # Adding multiple values
                    for val in value:
                        self.configs[chat_id][key].append(val)
                else:
                    self.configs[chat_id][key].append(value)
                self.configs[chat_id][key] = list(dict.fromkeys(self.get_config(chat_id, key)))  # Removing duplicates
            else:
                if isinstance(value, list):  # Removing multiple values
                    for val in value:
                        self.configs[chat_id][key].remove(val)
                else:
                    self.configs[chat_id][key].remove(value)

        # Setting the numerical parameters min and max
        elif key in ["price", "size", "rooms"]:
            self.configs[chat_id][key]["min"] = value[0]
            self.configs[chat_id][key]["max"] = value[1]

        # Setting the flag parameters values
        elif key in ["mode", "online"]:
            self.configs[chat_id][key] = value

        # Saving the updated config
        self.save_config(chat_id)

        return self

    # ------------------------------ Offer processing methods ------------------------------
    def process_offer(self, offer):
        """ Method sends offer to chat which might be interested in it (based on chat's config). """

        def __check_numeric_variable(off, u_cfg, var_name, allow_none=False):
            """ Function checks whether numeric variable of given offer falls into users config's limits.
            Note: function returns True on failed check. """
            if u_cfg.get(var_name) is not None:
                if getattr(off, var_name) is None:
                    return not allow_none  # True == skip offer
                elif (getattr(off, var_name) is not None and
                        u_cfg.get(var_name).get("min") > getattr(off, var_name) or
                        u_cfg.get(var_name).get("max") < getattr(off, var_name)):
                    return True

        def __check_categorical_variable(off, u_cfg, var_name):
            """ Function checks whether categorical variable of given offer falls into users config's choices.
            Note: function returns True on failed check. """
            if u_cfg.get(var_name) is not None:
                if getattr(off, var_name) is None or getattr(off, var_name) not in u_cfg.get(var_name):
                    return True

        # For each chat check if offer is eligible
        for chat_id in self.get_chat_ids():
            user_config = self.get_config(chat_id)

            # Check price
            if __check_numeric_variable(offer, user_config, "price"):
                continue

            # Check measurement
            if __check_numeric_variable(offer, user_config, "size"):
                continue

            # Check localisation
            if __check_categorical_variable(offer, user_config, "loc"):
                continue

            # Check if it's room
            if user_config.get("mode") is not None:
                if offer.is_room != user_config.get("mode"):
                    continue

            # Check number of rooms
            if not offer.is_room:
                if __check_numeric_variable(offer, user_config, "rooms", allow_none=True):
                    continue

            # If all check were passed then send the offer
            self.send_offer(offer, chat_id)

    def send_offer(self, offer, chat_id):
        """ Method sets given offer to chat with provided id if the chat has messages turned on. """
        def __format_offer(o):
            """ Function which returns formatted message body of an offer. """
            format_dict = {
                "Price": "%s" % o.price,
                "Location": "%s" % o.loc,
                "Size": "%s" % o.size}

            # Add info about rooms (only if it's a flat)
            if not o.is_room:
                format_dict["Rooms"] = "%s" % (o.rooms if o.rooms is not None else "b/d")

            # Values alignment
            just_len = len(max(format_dict.keys(), key=len))

            # Constructing message body
            msg_body = "\n".join(["`%s  %s`" % (k.ljust(just_len), v) for k, v in format_dict.items()])  # Attributes
            msg_body += "\n\n%s" % o.url

            return msg_body

        def __send_offer(bot, job):
            """ Callback function passed to job queue. """
            bot.send_message(text=job.context.get("text"), chat_id=job.context.get("chat_id"), parse_mode="Markdown")

        # Send only if chat is online
        if self.check_chat_status(chat_id):
            self.updater.job_queue.run_once(callback=__send_offer, when=0,
                                            context={
                                                "text": __format_offer(offer),
                                                "chat_id": chat_id})

    # ------------------------------ Bot methods ------------------------------
    def check_chat_id(self, chat_id):
        """ Checks if given chat is currently serviced. """
        return chat_id in self.get_chat_ids()

    def check_chat_status(self, chat_id):
        """ Check if given chat is online. """
        return self.get_config(chat_id, key="online")

    def check_timestamp(self):
        """ Checks if current timestamp is higher than the start timestamp.
        Used to avoid responding to handlers which were activated while bot was offline. """
        return dt.timestamp(dt.now()) > self.start_timestamp

    def get_chat_ids(self):
        """ Returns list of currently serviced chat ids. """
        return self.bot_settings.get("chat_ids")

    def is_bot_admin(self, user_id):
        """ Check if user with provided id is a bot admin. """
        return user_id in self.bot_settings.get("bot_admins")

    def is_chat_admin(self, chat_id, user_id):
        """ Check if user with provided id is a chat admin of chat with the provided id. """
        return user_id in self.get_config(chat_id, "chat_admins")

    def start(self):
        """ Starts the updater and saves the timestamp. """
        self.start_timestamp = dt.timestamp(dt.now())
        self.updater.start_polling()

    def stop(self):
        """ Stops the updater. """
        self.updater.stop()

    def update_settings(self, chat_id=None, add=True):
        """ Method saves the settings. Additionally, it adds/removes chat_id to/from bot settings prior to saving. """
        if chat_id is not None:
            # If chat id was provided and we are adding user, do so
            if add:
                self.bot_settings["chat_ids"].append(chat_id)
                self.bot_settings["chat_ids"] = list(set(self.get_chat_ids()))

            # Remove chat from serviced chat if there are no chat admins left
            elif len(self.get_config(chat_id, "chat_admins")) == 0:
                self.bot_settings["chat_ids"].remove(chat_id)

        # Saving the settings
        with open(self.settings_file, "w", encoding="utf-8") as sf:
            json.dump(self.bot_settings, sf, indent=4)

        return self

    # ------------------------------ Handlers ------------------------------
    def add_command_handlers(self):
        """ Command handlers and their methods which will be added to the bot. """

        # -------------------- Bot admin's methods --------------------
        def __modify_chat_admins(bot, update, args):
            """ Method used to add/remove admins to/from given chat. """
            # Checking timestamp so that the bot won't respond to handlers sent whilst it was offline
            if self.check_timestamp():
                message = update.message
                user = message.from_user
                confirmation = None  # 0 -- wrong ids provided

                # Proceed only if the user using this command is a bot admin
                if self.is_bot_admin(user.id):
                    if len(args) == 3 and args[0] in ["add", "remove"]:
                        action = args[0] == "add"  # Whether user should be added or removed
                        try:
                            chat_id = int(args[1])
                            user_id = int(args[2])

                            # Load config for given chat (to create a new config)
                            self.load_config(chat_id)

                        except ValueError:
                            confirmation = 0

                        # Check if we are adding an already-admin to admins
                        if self.is_chat_admin(chat_id, user_id) and action:
                            bot.send_message(text="User %d already is an admin of chat %d." % (user_id, chat_id),
                                             chat_id=message.chat_id)

                        # Check if we are removing not-admin from admin
                        elif not self.is_chat_admin(chat_id, user_id) and not action:
                            bot.send_message(text="User %d is not an admin of chat %d." % (user_id, chat_id),
                                             chat_id=message.chat_id)

                        # Update chat admins
                        else:
                            self.update_config(chat_id, "chat_admins", user_id, add=action)  # Modify the chat's admins
                            self.update_settings(chat_id, add=action)  # Add id to the list of serviced chats

                            # Send confirmation message
                            bot.send_message(
                                text="User id %d %s successfully %s chat %d admins. "
                                     "Current admins: %s" % (user_id, ["removed", "added"][action], ["from", "to"][action],
                                                             chat_id, self.get_config(chat_id, "chat_admins")),
                                chat_id=message.chat_id)

                        # If arguments were not correct then send appropriate message
                        if confirmation == 0:
                            bot.send_message(
                                text="Command usage not recognized. Get help with `/help chat_admins`.",
                                chat_id=message.chat_id, parse_mode="Markdown")

        # -------------------- Public methods --------------------
        def __chat_info(bot, update):
            """ Sends message stating user's id, chat id and chat admins if given chat is serviced. """
            if self.check_timestamp():
                message = update.message
                user = message.from_user

                # Construct response message's body
                msg_body = "%s, your id: *%d*\n" \
                           "This chat's id: *%d*" % (user.mention_markdown(), user.id, message.chat_id)

                # Add information about admins if there are any
                if self.check_chat_id(message.chat_id):
                    msg_body += "\nThis chat's admins: %s" % ", ".join(
                        ["*%d*" % a_id for a_id in self.get_config(message.chat_id, "chat_admins")])

                # Send the composed message
                bot.send_message(text=msg_body, chat_id=message.chat_id, parse_mode="Markdown")

        def __help(bot, update, args):
            """ Method to display help on available commands. """
            if self.check_timestamp():
                message = update.message
                user = message.from_user

                # Public methods' descriptions
                desc = {
                    "help": "/help -- displays this message",
                    "chat_info": "/chat\\_info -- displays chat & user's id"
                }

                # Private methods' descriptions
                desc_private = {
                    "config": "/config -- displays all settings\n"
                              "/config `[loc/mode/price/size]` -- displays current settings of chosen parameter\n"
                              "/config `loc [add/remove] location1, location2, ...` -- adds/removes location\n"
                              "/config `mode [flats/rooms/all]` -- changes mode\n"
                              "/config `[price/size/rooms] min max` -- sets new limits",
                    # "favorite": "",
                    "status": "/status -- displays if bot is working in this chat",
                    "toggle": "/toggle -- turns bot on/off in this chat"
                }

                # Admin methods' descriptions
                desc_admin = {
                    "chat_admins": "/chat\\_admins `[add/remove] chat_id user_id` "
                                   "-- adds/removes chat admin privileges to a given user of a given chat"
                }

                # Adding private methods
                if self.check_chat_id(message.chat_id):
                    if self.is_chat_admin(message.chat_id, user.id):
                        desc = {**desc, **desc_private}
                    else:
                        desc["status"] = desc_private.get("status")  # Only status method work for non-admins

                # Adding admin methods
                if self.is_bot_admin(user.id):
                    desc = {**desc, **desc_admin}

                # Update help for commands description
                desc["help"] += "\n/help `[%s]` -- display help on selected command" % "/".join(
                    [k for k in desc.keys() if k != "help"])

                # Update help for Warsaw's districts
                if self.check_chat_id(message.chat_id):
                    desc["help"] += "\n/help `dzielnice` -- wyświetla poprawną pisownię wszystkich dzielnic Warszawy"

                # Checking if help was requested for single (known) command or for all commands
                if len(args) == 1 and args[0] in desc.keys():
                    bot.send_message(text=desc.get(args[0]), chat_id=message.chat_id, parse_mode="Markdown")

                # Sending help on Warsaw's districts
                elif len(args) == 1 and args[0] == "dzielnice":
                    districts = ['Bemowo', 'Białołęka', 'Bielany', 'Mokotów', 'Ochota', 'Praga Południe',
                                 'Praga Północ', 'Rembertów', 'Śródmieście', 'Targówek', 'Ursus', 'Ursynów', 'Wawer',
                                 'Wesoła', 'Wilanów', 'Wola', 'Włochy', 'Żoliborz']
                    bot.send_message(text="Obsługiwane dzielnice:\n%s" % ", ".join(districts), chat_id=message.chat_id)

                else:
                    bot.send_message(text="\n\n".join(desc.values()), chat_id=message.chat_id, parse_mode="Markdown")

        # -------------------- Private methods --------------------
        def __config(bot, update, args):
            """ Method used by users to modify their chat settings. """
            # Dictionary with config formatted for displaying
            def __formatted_config(c_id):
                return {
                    "mode": "Mode: `%s`" % dict(
                        [(v, k) for (k, v) in mode_dict.items()]).get(self.get_config(c_id, "mode")),
                    "price": "Price: min `%0.f`, max `%0.f`" % tuple(self.get_config(c_id, "price").values()),
                    "size": "Size: min `%0.f`, max `%0.f`" % tuple(self.get_config(c_id, "size").values()),
                    "rooms": "Rooms: min `%0.f`, max `%0.f`" % tuple(self.get_config(c_id, "rooms").values()),
                    "loc": "Locations: %s" % ", ".join(["`'%s'`" % str(loc) for loc in self.get_config(c_id, "loc")])}

            if self.check_timestamp():
                message = update.message
                user = message.from_user
                chat_id = message.chat_id

                # Method variables
                mode_dict = {"rooms": True, "flats": False, "all": None}
                confirmation = None  # 0 -- command not recognized, 1 -- settings updated, 2 -- settings reset

                # Proceed only if chat is serviced and user which calls method is this chat's admin
                if self.check_chat_id(chat_id) and self.is_chat_admin(chat_id, user.id):

                    # Display whole config
                    if len(args) == 0:
                        msg_body = "*Settings*\n" + "\n".join(__formatted_config(chat_id).values())
                        bot.send_message(text=msg_body, chat_id=chat_id, parse_mode="Markdown")

                    # Display specific parameter config
                    elif len(args) == 1 and args[0] in ["price", "size", "loc", "mode", "rooms"]:
                        msg_body = "*Settings*\n" + __formatted_config(chat_id).get(args[0])
                        bot.send_message(text=msg_body, chat_id=chat_id, parse_mode="Markdown")

                    # ToDo: Reset settings to defaults
                    elif len(args) == 1 and args[0] == "reset":
                        # confirmation = 2
                        confirmation = 0  # Not recognized for now

                    # ToDo: Reset specific settings to defaults
                    elif len(args) == 2 and args[0] in ["price", "size", "loc", "mode"] and args[1] == "reset":
                        # confirmation = 2
                        confirmation = 0  # Not recognized for now

                    # Modify provided locations
                    elif len(args) >= 3 and args[0] == "loc" and args[1] in ["add", "remove"]:
                        # ToDo: verify correctness of provided location (check with existing locations base)
                        provided_locations = [loc.replace(",", "") for loc in (" ".join(args[2:])).split(", ")]
                        self.update_config(chat_id, args[0], provided_locations, add=args[1] == "add")
                        confirmation = 1

                    # Set search mode
                    elif len(args) == 2 and args[0] == "mode" and args[1] in mode_dict.keys():
                        self.update_config(chat_id, args[0], mode_dict.get(args[1]))
                        confirmation = 1

                    # Set price and size. Check arg[0] to avoid empty confirmation
                    elif len(args) == 3 and args[0] in ["price", "size", "rooms"]:
                        try:
                            min_arg = float(args[1])
                            max_arg = float(args[2])
                            self.update_config(chat_id, args[0], [min_arg, max_arg])
                            confirmation = 1
                        except ValueError:
                            confirmation = 0

                    # Call was not recognized
                    else:
                        confirmation = 0

                    # Command usage not recognized
                    if confirmation == 0:
                        bot.send_message(text="Command usage not recognized. Get help with `/help config`.",
                                         chat_id=chat_id, parse_mode="Markdown")

                    # Settings' update confirmation
                    elif confirmation == 1:
                        msg_body = "*Settings updated*\n" + __formatted_config(chat_id).get(args[0])
                        bot.send_message(text=msg_body, chat_id=chat_id, parse_mode="Markdown")

                    # Reset confirmation
                    elif confirmation == 2:
                        msg_body = "*Settings reset*\n"

                        # All settings reset
                        if args[0] == "reset":
                            msg_body += "\n".join(__formatted_config(chat_id).values())

                        # Only one setting reset
                        else:
                            msg_body += __formatted_config(chat_id).get(args[0])

                        # Send composed message
                        bot.send_message(text=msg_body, chat_id=chat_id, parse_mode="Markdown")

        def __favorite(bot, update, args):  # ToDo
            if self.check_timestamp():
                pass

        def __status(bot, update):
            """ Sends information whether bot is will send messages to chat or not. """
            if self.check_timestamp():
                chat_id = update.message.chat_id

                if self.check_chat_id(chat_id):
                    if self.check_chat_status(chat_id):
                        msg_body = "Currently working here! :)"
                    else:
                        msg_body = "I am on a break now."

                        # Only chat admins are allowed to toggle bot, so add this part only for them
                        if self.is_chat_admin(chat_id, update.message.from_user.id):
                            msg_body += " But I'm ready to start if you say so!"

                    bot.send_message(text=msg_body, chat_id=chat_id, parse_mode="Markdown")

        def __toggle(bot, update):
            """ Switches bot's flag for sending offers to that chat. """
            chat_id = update.message.chat_id

            # Proceed only if chat is serviced and user which calls method is this chat's admin
            if self.check_chat_id(chat_id) and self.is_chat_admin(chat_id, update.message.from_user.id):
                current_status = self.check_chat_status(chat_id)
                self.update_config(chat_id, "online", not current_status)

                # Send confirmation only if we answer handler that was just sent
                if self.check_timestamp():
                    bot.send_message(text=["Getting to work!", "Gonna take a break now..."][current_status],
                                     chat_id=chat_id)

        self.updater.dispatcher.add_handler(CommandHandler("chat_admins", __modify_chat_admins, pass_args=True))
        self.updater.dispatcher.add_handler(CommandHandler("chat_info", __chat_info))
        self.updater.dispatcher.add_handler(CommandHandler("help", __help, pass_args=True))
        self.updater.dispatcher.add_handler(CommandHandler("config", __config, pass_args=True))
        # self.updater.dispatcher.add_handler(CommandHandler("favorite", __favorite, pass_args=True))
        self.updater.dispatcher.add_handler(CommandHandler("status", __status))
        self.updater.dispatcher.add_handler(CommandHandler("toggle", __toggle))
        return self

    def add_message_handlers(self):  # ToDo
        """ Message handlers which will be added to the bot. """
        pass


# ToDo: add /start handler with welcome message
# ToDo: update available commands and hints at BotFather
