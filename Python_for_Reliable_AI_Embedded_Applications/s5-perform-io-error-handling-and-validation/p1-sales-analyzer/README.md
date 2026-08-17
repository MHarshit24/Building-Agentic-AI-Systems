# 📊 Sales Analyzer App

## 📌 Overview

The **Sales Analyzer App** is a Python-based application designed to process, validate, and analyze retail sales records efficiently.

This project demonstrates how:

- File handling
- Custom exception management
- Data validation
- Logging
- Modular architecture

work together to build a reliable and maintainable data processing system.

The application reads sales data from a text file, validates each record, logs key events, and generates a structured summary report.

---

## 🎯 Problem Statement

Design a Python application to:

- Read sales records from a file
- Validate each record
- Handle file and data errors gracefully
- Maintain detailed logs for debugging and monitoring
- Generate a final sales summary report

---

## 🏗 Project Structure

```
p1-sales-analyzer/
├── data/
│   ├── sales_data.txt
│   └── sales_summary.txt
├── sales_analyzer/
│   ├── file_operations.py
│   ├── data_validator.py
│   ├── exceptions.py
│   ├── logger_config.py
│   └── main.py
└── logs/
    └── app.log
```


---

# 🧩 Step-by-Step Implementation

---

## 🔹 Step 1: File Reading (`file_operations.py`)

- Reads `sales_data.txt`
- Processes each line in format:
  
product_name, quantity, amount


- Handles:
- Missing file
- Incorrect line formatting
- File I/O errors

Uses `FileProcessingError` for controlled file-related failures.

---

## 🔹 Step 2: Data Validation (`data_validator.py`, `exceptions.py`)

- Validates each sales record
- Ensures:
- Product name is not empty
- Quantity is numeric and greater than zero
- Price is numeric and greater than zero
- Converts values to proper types:
- Quantity → `int`
- Price → `float`

Uses custom exceptions:

- `InvalidDataError`
- `FileProcessingError`

This ensures only valid data is used in analysis.

---

## 🔹 Step 3: Logging Configuration (`logger_config.py`)

- Configures reusable logger
- Logs to:
- Console (INFO level and above)
- File (`logs/app.log`, DEBUG level)
- Includes:
- Timestamp
- Log level
- Module name
- Message

Logging captures:

- File operations
- Validation errors
- Processing success
- Critical failures

---

## 🔹 Step 4: Integration and Report Generation (`main.py`)

- Reads raw sales data
- Validates each record
- Skips invalid records
- Calculates:
- Total sales amount
- Number of valid transactions
- Writes formatted summary to:

sales_summary.txt


- Logs completion and error details

---

# 📄 Example Input (`sales_data.txt`)

Laptop,2,1500
Phone,3,900
TV,1,1200
Mouse,-2,300
InvalidLine


---

# 📄 Example Output (`sales_summary.txt`)

Sales Summary Report
Valid Transactions: 3
Total Sales Amount: 6900.00


---

# 📋 Logging Example (`logs/app.log`)

2026-02-19 19:30:12 - INFO - main - Sales Analyzer started.
2026-02-19 19:30:13 - ERROR - data_validator - Line 4: Quantity must be greater than zero.
2026-02-19 19:30:14 - INFO - main - Summary report generated successfully.


---

# 🚀 How to Run

1. Ensure Python 3.x is installed.
2. Ensure `sales_data.txt` is placed in the `data/` directory.
3. Navigate to the `sales_analyzer` directory:
```bash
cd sales_analyzer
```
4. Run the application:
```bash
python main.py
```

5. Check output files:
- `../data/sales_summary.txt`
- `../logs/app.log`


# ✅ Conclusion
The Sales Analyzer App simulates a real-world retail data processing system.
It highlights how structured validation, logging, and error handling contribute to reliable and traceable business analytics applications.