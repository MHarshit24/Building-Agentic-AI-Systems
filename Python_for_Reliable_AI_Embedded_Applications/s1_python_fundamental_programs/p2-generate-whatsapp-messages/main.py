def main():
    customer_name = "Ravi Kumar"
    order_id = "ORD98765"
    address = (
        "A-12, Sunrise Apartments,\n"
        "Opp. M.G. Library,\n"
        "Mall Road, Indore - 450021"
    )
    delivery_date = "15-Jan-2025"

    message = f"""Hello {customer_name},

We are happy to inform you that your order {order_id} has been successfully shipped on {delivery_date} to:
{address}

Thank you for shopping with us!
"""

    print(message)


if __name__ == "__main__":
    main()
