from exceptions import InvalidDataError


class SalesDataValidator:
    @staticmethod
    def validate_record(record, line_num):
        product_name = record.get("product_name")
        quantity_sold = record.get("quantity_sold")
        price_per_unit = record.get("price_per_unit")

        if not product_name or not isinstance(product_name, str):
            raise InvalidDataError(
                f"Line {line_num}: Product name cannot be empty."
            )

        # Convert quantity
        try:
            quantity_sold = int(quantity_sold)
            if quantity_sold <= 0:
                raise InvalidDataError(
                    f"Line {line_num}: Quantity must be greater than zero."
                )
        except (ValueError, TypeError):
            raise InvalidDataError(
                f"Line {line_num}: Quantity must be an integer."
            )

        # Convert price
        try:
            price_per_unit = float(price_per_unit)
            if price_per_unit <= 0:
                raise InvalidDataError(
                    f"Line {line_num}: Price must be greater than zero."
                )
        except (ValueError, TypeError):
            raise InvalidDataError(
                f"Line {line_num}: Price must be a number."
            )

        return {
            "product_name": product_name,
            "quantity_sold": quantity_sold,
            "price_per_unit": price_per_unit,
        }
