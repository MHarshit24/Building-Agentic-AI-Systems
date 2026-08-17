def filter_by_price(products, min_price):
    return list(filter(lambda product: product['price'] > min_price, products))

def filter_by_category(products, category):
    return list(filter(lambda product: product['category'] == category, products))


def apply_discount_to_products(products, discount_func):
    return list(
        map(
            lambda product: {**product, 'price': discount_func(product['price'])}, products
            )
        )