from products import add_product, add_products, products
from discounts import discount_calculator
from filters import filter_by_price, apply_discount_to_products

def display_products(title, product_list):
    """
    Utility function to neatly display products.
    """
    print(f"\n===== {title} =====")
    for product in product_list:
        print(f"Name: {product['name']}")
        print(f"Price: ₹{product['price']}")
        print(f"Category: {product['category']}")
        print("-" * 30)

def main():
    add_product("Laptop", 50000, "Electronics", stock=10, brand="Dell")
    add_product("Smartphone", 25000, "Electronics", stock=15, brand="Samsung")
    add_product("Shoes", 1500, "Fashion", stock=30, brand="Nike")

    add_products(
        {"name": "Headphones", "price": 3000, "category": "Electronics", "stock": 20},
        {"name": "Watch", "price": 1800, "category": "Accessories", "stock": 25},
    )
    
    display_products("All Products", products)
    
    expensive_products = filter_by_price(products, 2000)
    display_products("Products Above ₹2000", expensive_products)
    
    festival_discount = discount_calculator(20)
    
    discounted_products = apply_discount_to_products(expensive_products, festival_discount)
    display_products("After 20% Festival Discount on Products Above ₹2000", discounted_products)
    
if __name__ == "__main__":
    main()


