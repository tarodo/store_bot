# Store Bot
Telegram Bot that sell you everything and save customer email

## Redis reg
For free registration, use https://redis.com/
And use REDIS_URL, REDIS_PORT, REDIS_PASS from your instance configuration.

## Env
The following environment variables are required:
- TELEGRAM_BOT_TOKEN - str, token from [BotFather](https://t.me/botfather)
- REDIS_URL - str, url from [Redis config](https://app.redislabs.com/#/subscriptions)
- REDIS_PORT - str, port from [Redis config](https://app.redislabs.com/#/subscriptions)
- REDIS_PASS - str, pass from [Redis config](https://app.redislabs.com/#/subscriptions)
- CLIENT_ID - str, Client ID from [Moltin](https://euwest.cm.elasticpath.com/)
- CLIENT_SECRET - str, Client secret from [Moltin](https://euwest.cm.elasticpath.com/)

## Local start
1. Create `.env` from `.env.Exmaple`
2. `pip install -r requirements.txt`
3. `python tg_bot.py`

## Heroku start
Create an app on [heroku](https://www.heroku.com/) and add variables in Settings -> Config Vars