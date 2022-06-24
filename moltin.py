import requests

CART_PREFIX = "cart_"


def get_headers(store_token):
    return {
        "Authorization": f"Bearer {store_token}",
    }


def get_store_token(client_id, client_secret):
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }

    response = requests.post("https://api.moltin.com/oauth/access_token", data=data)
    response.raise_for_status()

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
