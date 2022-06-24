from functools import partial

import redis
from environs import Env
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters,
                          MessageHandler, Updater)

from moltin import (add_product_to_cart, create_customer,
                    delete_item_from_cart, get_cart, get_cart_items,
                    get_cart_sum, get_photo_url, get_product, get_products,
                    get_store_token)

COUNT_PLACEHOLDER = "_count_"


def keyboard_maker(buttons, number):
    keyboard = []
    for num in range(0, len(buttons), number):
        keyboard.append(
            [
                InlineKeyboardButton(button["name"], callback_data=button["id"])
                for button in buttons[num : num + number]
            ]
        )
    return keyboard


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
