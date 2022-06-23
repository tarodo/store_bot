from functools import partial

import redis
import requests
from environs import Env
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters,
                          MessageHandler, Updater)

COUNT_PLACEHOLDER = "_count_"
CART_PREFIX = "cart_"


def button_maker(buttons, chunks_number):
    for num in range(0, len(buttons), chunks_number):
        yield [
            InlineKeyboardButton(button["name"], callback_data=button["id"])
            for button in buttons[num : num + chunks_number]
        ]


def keyboard_maker(buttons, number):
    keyboard = list(button_maker(buttons, number))
    return keyboard


def get_headers(store_token):
    return {
        "Authorization": f"Bearer {store_token}",
    }


def get_store_token():
    data = {
        "client_id": "lLnAy1hG6T0YcBypZXT9Dlg6D6LQBHtORHaqv1gC1z",
        "client_secret": "DGMMqrh2QLWPLuyZku01U0RC37qMh0l4VUfWZBL2Yg",
        "grant_type": "client_credentials",
    }

    response = requests.post("https://api.moltin.com/oauth/access_token", data=data)

    return response.json()["access_token"]


def get_products(store_token):
    products = []
    headers = get_headers(store_token)
    response = requests.get(f"https://api.moltin.com/v2/products", headers=headers)
    response.raise_for_status()
    for elem in response.json()["data"]:
        products.append({"id": elem["id"], "name": elem["name"]})
    return products


def get_product(store_token, product_id):
    headers = get_headers(store_token)
    response = requests.get(
        f"https://api.moltin.com/v2/products/{product_id}", headers=headers
    )
    response.raise_for_status()
    product = response.json()["data"]
    product_info = product["description"]
    img_id = product["relationships"]["main_image"]["data"]["id"]

    return product_info, img_id


def get_photo_url(store_token, img_id):
    headers = get_headers(store_token)
    response = requests.get(
        f"https://api.moltin.com/v2/files/{img_id}", headers=headers
    )
    response.raise_for_status()
    return response.json()["data"]["link"]["href"]


def create_cart(store_token, chat_id):
    headers = get_headers(store_token)
    data = {"data": {"name": str(chat_id)}}
    response = requests.post(
        "https://api.moltin.com/v2/carts", json=data, headers=headers
    )
    response.raise_for_status()
    return response.json()["data"]["id"]


def get_cart(store_token, chat_id, db):
    cart_id = db.get(f"{CART_PREFIX}{chat_id}")
    if not cart_id:
        cart_id = create_cart(store_token, chat_id)
        db.set(f"{CART_PREFIX}{chat_id}", cart_id)
    else:
        cart_id = cart_id.decode("utf-8")
    return cart_id


def get_cart_info(cart):
    return [
        {
            "name": position["name"],
            "qty": position["quantity"],
            "id": position["id"],
            "price": position["meta"]["display_price"]["with_tax"]["unit"]["formatted"],
            "value": position["meta"]["display_price"]["with_tax"]["value"][
                "formatted"
            ],
        }
        for position in cart["data"]
    ]


def add_product_to_cart(store_token, product_id, count, chat_id, db):
    headers = get_headers(store_token)
    cart_id = get_cart(store_token, chat_id, db)
    data = {"data": {"id": product_id, "type": "cart_item", "quantity": count}}
    response = requests.post(
        f"https://api.moltin.com/v2/carts/{cart_id}/items", json=data, headers=headers
    )
    response.raise_for_status()
    if response.status_code == 201:
        return get_cart_info(response.json())


def get_cart_items(store_token, cart_id):
    headers = get_headers(store_token)
    response = requests.get(
        f"https://api.moltin.com/v2/carts/{cart_id}/items", headers=headers
    )
    response.raise_for_status()
    return get_cart_info(response.json())


def get_cart_sum(store_token, cart_id):
    headers = get_headers(store_token)
    response = requests.get(
        f"https://api.moltin.com/v2/carts/{cart_id}", headers=headers
    )
    response.raise_for_status()
    return response.json()["data"]["meta"]["display_price"]["with_tax"]["formatted"]


def delete_item_from_cart(store_token, cart_id, item_id):
    headers = get_headers(store_token)
    response = requests.delete(
        f"https://api.moltin.com/v2/carts/{cart_id}/items/{item_id}", headers=headers
    )
    response.raise_for_status()
    return True


def create_customer(store_token, user_name, user_email):
    headers = get_headers(store_token)
    data = {"data": {"type": "customer", "name": user_name, "email": user_email}}
    response = requests.post(
        f"https://api.moltin.com/v2/customers", headers=headers, json=data
    )
    response.raise_for_status()
    return response.json()["data"]["id"]


def start(bot, update, **kwargs):
    text = "Покупай и точка!"
    products = get_products(kwargs["store_token"])
    keyboard = keyboard_maker(products, 1)
    keyboard.append([InlineKeyboardButton("Корзина", callback_data="cart")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.effective_user.send_message(text, reply_markup=reply_markup)
    return "HANDLE_MENU"


def show_cart(bot, update, store_token, chat_id, db):
    cart_id = get_cart(store_token, chat_id, db)
    cart_items = get_cart_items(store_token, cart_id)
    cart_sum = get_cart_sum(store_token, cart_id)
    cart_text = "\n".join(
        [
            f"Товар: {item['name']}\n"
            f"Цена: {item['price']}\n"
            f"Количество {item['qty']}\n"
            f"Сумма: {item['value']}\n"
            for item in cart_items
        ]
    )
    cart_text += f"\nИтог: {cart_sum}"
    buttons = [
        {"name": f'Удалить {item["name"]}', "id": item["id"]} for item in cart_items
    ]
    keyboard = [[InlineKeyboardButton("Оплатить", callback_data="pay")]]
    keyboard_items = keyboard_maker(buttons, 1)
    if keyboard_items:
        keyboard.append(keyboard_items[0])
    keyboard.append([InlineKeyboardButton("В Меню", callback_data="menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.effective_user.send_message(cart_text, reply_markup=reply_markup)
    return "HANDLE_CART"


def handle_menu(bot, update, **kwargs):
    query = update.callback_query
    query.answer()

    bot.delete_message(
        chat_id=query.message.chat_id, message_id=query.message.message_id
    )

    if query.data == "cart":
        return show_cart(
            bot, update, kwargs["store_token"], query.message.chat_id, kwargs["db"]
        )

    product_id = query.data
    info, img_id = get_product(kwargs["store_token"], product_id)

    keyboard = []
    if img_id:
        photo_url = get_photo_url(kwargs["store_token"], img_id)
        keyboard.append(
            [
                InlineKeyboardButton(
                    item,
                    callback_data=f"{product_id}{COUNT_PLACEHOLDER}{item.split()[0]}",
                )
                for item in ["1 item", "5 items", "10 items"]
            ]
        )
        keyboard.append([InlineKeyboardButton("Назад", callback_data="back")])

        bot.send_photo(
            chat_id=query.message.chat_id,
            photo=photo_url,
            caption=info,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        keyboard.append([InlineKeyboardButton("Назад", callback_data="back")])
        update.effective_user.send_message(
            info, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    return "HANDLE_DESCRIPTION"


def handle_description(bot, update, **kwargs):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    if query.data == "back":
        bot.delete_message(chat_id=chat_id, message_id=query.message.message_id)
        return start(bot, update, **kwargs)

    elif COUNT_PLACEHOLDER in query.data:
        product_id, count = query.data.split(COUNT_PLACEHOLDER)
        cart = add_product_to_cart(
            kwargs["store_token"], product_id, int(count), chat_id, kwargs["db"]
        )
    return "HANDLE_DESCRIPTION"


def handle_cart(bot, update, **kwargs):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    bot.delete_message(chat_id=chat_id, message_id=query.message.message_id)
    if query.data == "menu":
        return start(bot, update, **kwargs)
    elif query.data == "pay":
        text = "Пришлите Вашу почту, мы с Вами свяжемся"
        update.effective_user.send_message(text)
        return "WAITING_EMAIL"
    else:
        item_id = query.data
        store_token = kwargs["store_token"]
        db = kwargs["db"]
        cart_id = get_cart(store_token, chat_id, db)
        delete_item_from_cart(store_token, cart_id, item_id)
        return show_cart(bot, update, store_token, chat_id, db)


def waiting_email(bot, update, **kwargs):
    user_email = update.message.text
    user_name = f"{update.message.chat.first_name} {update.message.chat.last_name}"
    customer_id = create_customer(kwargs["store_token"], user_name, user_email)
    update.effective_user.send_message(
        f"Мы свяжемся с вами по этому адресу: {user_email}"
    )
    return "WAITING_EMAIL"


def handle_users_reply(db, store_token, bot, update):
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply in ["/start"]:
        user_state = "START"
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        "START": start,
        "HANDLE_MENU": handle_menu,
        "HANDLE_DESCRIPTION": handle_description,
        "HANDLE_CART": handle_cart,
        "WAITING_EMAIL": waiting_email,
    }
    state_handler = states_functions[user_state]
    try:
        next_state = state_handler(bot, update, store_token=store_token, db=db)
        db.set(chat_id, next_state)
    except Exception as err:
        print(err)


if __name__ == "__main__":
    env = Env()
    env.read_env()

    bot_token = env.str("TELEGRAM_BOT_TOKEN")
    moltin_token = get_store_token()

    REDIS_URL = env.str("REDIS_URL")
    REDIS_PORT = env.str("REDIS_PORT")
    REDIS_PASS = env.str("REDIS_PASS")
    redis_conn = redis.Redis(host=REDIS_URL, port=REDIS_PORT, db=0, password=REDIS_PASS)

    updater = Updater(bot_token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(
        CallbackQueryHandler(partial(handle_users_reply, redis_conn, moltin_token))
    )
    dispatcher.add_handler(
        MessageHandler(
            Filters.text, partial(handle_users_reply, redis_conn, moltin_token)
        )
    )
    dispatcher.add_handler(
        CommandHandler("start", partial(handle_users_reply, redis_conn, moltin_token))
    )
    updater.start_polling()
