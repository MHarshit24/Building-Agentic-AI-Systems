def discount_calculator(percent):
    def apply_discount(price):
        return price * (1 - percent / 100)
    return apply_discount
