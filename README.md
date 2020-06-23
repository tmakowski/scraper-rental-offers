## Flat Rental Offers' Scraper with Telegram Integration

This is an implementation of flat rental offers' scraper I made back in the day. At the time I did not write any manual hence, apart from the brief introduction, I leave figuring how this scraper works to the reader.


### Introduction

 * The scraper was designed to work with two offers' boards: [GumTree](https://www.gumtree.pl/) and [OLX](https://www.olx.pl/).
 * The scraper was intented to work with the city of Warsaw.
    * Other cities *might* work out of the box if the URLs within `utils.py` were changed.
    * Names of districts are hardcoded - those might have changed.
    * The filtering options were designed to work for Warsaw. 
 * The scraper refreshes provided URLs every 30 seconds and processes any new offers.
 * The scraper works for both flats and rooms.
 * The scraper has an option to utililze [Telegram Bot API](https://core.telegram.org/bots/api) to send new offers.
    * The bot config is has to be a `.json` file with fields `token` (string), `bot_admins` (array of ints) and `chat_ids` (array of ints).
    * The bot supports multiple chats but ignores any message which outside of the `chat_ids` provided in the bot config.
    * Each chat has it's own config and channel admins (who can modify config).
    * The channel admins are added via a special command for bot admin (defined within the bot config).
