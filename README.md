A telegram bot to scrape kleinanzeigen.de and send messages upon the discovery of new entries written in python.

# Setup

## Configuration

To use this bot you need to create a telegram bot and get the API token. Find out how to do this here: https://core.telegram.org/bots#how-do-i-create-a-bot

Copy `.env.example` to `.env` in the root directory of this repo and fill in:

- `TOKEN` -- your Telegram bot API token
- `CHAT_IDS` -- a comma-separated list of the chat IDs the bot is allowed to respond to. Messages from any other chat are ignored.

```
TOKEN=123456:your-telegram-bot-token
CHAT_IDS=123456789,987654321
```

You can find your chat ID by messaging a bot like `@userinfobot`, or by inspecting the logs when the bot ignores your message.

## run using Docker Compose (recommended)

Make sure you have created your `.env` file (see Configuration above), then:

```
cd [install directory]
docker compose up -d --build
```

The `.env` file is injected at runtime via `env_file`, so your token and chat IDs are not baked into the image.

To view logs and stop:

```
docker compose logs -f
docker compose down
```

## run using Docker (manual)

To run the application in a docker container, build and run the image using the `Dockerfile`:

```
cd [install directory]
docker build -t python-kleinanzeigen .
docker run -d --env-file .env python-kleinanzeigen
```

## run using pyton virtual environment

Create a python virtual environment, install required packages and run the project

```
cd [install directory]
py -m venv .
pip install -r requirements.txt
python source/telegram_bot.py
```

## Controlling the Bot

The Bot offers the following commands:

- `/start` -- Show all available commands
- `/add_bot` <name> <link> -- add a bot that scans the specified link
- `/start_bots`  -- start fetching with registered bots
- `/stop` -- stop fetching
- `/remove_bot` <name> -- stop and remove a bot
- `/clear_bots` -- stop and clear all registered bots
- `/status` -- get status information
- `/add_filter` -- add a filter to filter out unwanted messages
- `/show_filters` -- show active filters
- `/clear_filters` -- clear all filters

### Example usage

To specify a search simply go on kleinanzeigen.de, create your search parameters and copy the URL.

1. Add a bot with a name and search link:
```
/add_bot fahrrad https://www.kleinanzeigen.de/s-fahrraeder/herren/c217+fahrraeder.art_s:herren
```
2. Start the bot
```
/start_bots
```
3. Check the status of the running searches:
```
/status
```

You can add or remove multiple Searches. 
If there is a large amount of unwanted messages (eg. searches instead of offers) you can create filters to ignore these messages. Given filters are interpreted in the python regular expression syntax.
