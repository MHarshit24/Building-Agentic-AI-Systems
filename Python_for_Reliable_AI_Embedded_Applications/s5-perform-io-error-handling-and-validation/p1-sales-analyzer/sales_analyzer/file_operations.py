from exceptions import FileProcessingError


class FileReading:
    @staticmethod
    def read_file(file_path):
        sales_data = []

        try:
            with open(file_path, "r") as file:
                for line_num, line_content in enumerate(file, start=1):
                    line_content = line_content.strip()

                    if not line_content:
                        continue

                    parts = line_content.split(",")

                    if len(parts) != 3:
                        raise FileProcessingError(
                            f"Line {line_num} is in incorrect format: '{line_content}'"
                        )

                    product_name = parts[0].strip()
                    quantity_sold = parts[1].strip()
                    price_per_unit = parts[2].strip()

                    sales_data.append(
                        {
                            "product_name": product_name,
                            "quantity_sold": quantity_sold,
                            "price_per_unit": price_per_unit,
                        }
                    )

            return sales_data

        except FileNotFoundError:
            raise FileProcessingError(
                f"The file '{file_path}' was not found."
            )

        except IOError as e:
            raise FileProcessingError(
                f"IO error while reading file '{file_path}': {e}"
            )
