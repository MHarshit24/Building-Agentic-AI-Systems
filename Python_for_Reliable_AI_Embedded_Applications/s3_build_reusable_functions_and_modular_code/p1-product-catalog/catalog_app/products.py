products = []
def add_product(name, price, category, **kwargs):
    product = {
        "name": name,
        "price": price,
        "category": category,
        **kwargs
    }
    products.append(product)

def add_products(*args):
    for product in args:
        if isinstance(product, dict):
            products.append(product)
        else:
            print("Invalid product format. Must be a dictionary.")