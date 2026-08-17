from file_operations import FileReading
from data_validator import SalesDataValidator
from exceptions import InvalidDataError, FileProcessingError
from logger_config import setup_logger
import os


def main():
    logger = setup_logger(__name__)
    
    # Get paths relative to sales_analyzer directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    data_dir = os.path.join(parent_dir, 'data')
    logs_dir = os.path.join(parent_dir, 'logs')
    
    input_file = os.path.join(data_dir, 'sales_data.txt')
    output_file = os.path.join(data_dir, 'sales_summary.txt')

    logger.info("Sales Analyzer started.")

    try:
        # Step 1: Read raw data
        raw_data = FileReading.read_file(input_file)

        if not raw_data:
            logger.warning("No data found to process.")
            return

        total_sales = 0
        valid_transactions = 0

        # Step 2: Validate and process records
        for line_number, record in enumerate(raw_data, start=1):
            try:
                validated_record = SalesDataValidator.validate_record(
                    record, line_number
                )

                quantity = validated_record["quantity_sold"]
                price = validated_record["price_per_unit"]

                total_sales += quantity * price
                valid_transactions += 1

                logger.info(f"Line {line_number} processed successfully.")

            except InvalidDataError as e:
                logger.error(f"Validation error: {e}")

        # Step 4: Write summary report
        with open(output_file, "w") as summary_file:
            summary_file.write("Sales Summary Report\n")
            summary_file.write("----------------------\n")
            summary_file.write(f"Valid Transactions: {valid_transactions}\n")
            summary_file.write(f"Total Sales Amount: {total_sales:.2f}\n")

        logger.info("Summary report generated successfully.")
        logger.info("Sales Analyzer completed.")

    except FileProcessingError as e:
        logger.critical(f"File processing error: {e}")

    except Exception as e:
        logger.critical(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
