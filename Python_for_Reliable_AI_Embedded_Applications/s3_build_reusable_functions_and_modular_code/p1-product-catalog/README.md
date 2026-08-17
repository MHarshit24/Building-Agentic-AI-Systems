# 📦 Modular Product Catalog & Discount Engine

## 📌 Overview

This project implements a **modular product catalog and discount engine** for a small online store using Python.

The system demonstrates:

- Modular programming
- Functional programming concepts
- Closures
- `*args` and `**kwargs`
- `map()` and `filter()`
- Clean separation of concerns

The application simulates how an online retailer manages products, filters them based on conditions, and dynamically applies discount strategies.

---

## 🎯 Problem Statement

Develop a modular Python program to:

- Store and manage product information
- Apply dynamic discount strategies
- Filter and analyze products
- Maintain a clean and reusable architecture

---

## 🧠 Concepts Demonstrated

| Concept | Implementation |
|----------|---------------|
| `*args` | Adding multiple products at once |
| `**kwargs` | Handling optional product details |
| Closures | Creating reusable discount calculators |
| `filter()` + lambda | Filtering products by price/category |
| `map()` + lambda | Applying discounts to products |
| Modular Programming | Separate Python files for each responsibility |

---

## 🏗 Project Structure


```text
p1_product_catalog_app/
    ├──catalog_app
        ├── products.py      # Product storage and management
        ├── discounts.py     # Closure-based discount logic
        ├── filters.py       # Filtering and mapping operations
        └── main.py          # Application entry point
```


---

## 🔹 Module Responsibilities

### 1️⃣ `products.py`

Handles product creation and storage.

Functions:
- `add_product(name, price, category, **kwargs)`
- `add_products(*args)`
}

```python
products = []
```
Each product is stored as a dictionary:

```python
{
    "name": "Laptop",
    "price": 50000,
    "category": "Electronics",
    "stock": 10,
    "brand": "Dell"
}
```

---

### 2️⃣ `discounts.py`
Defines a closure-based discount generator.

```python
Safe dictionary unpacking using **

✅ Conclusion
This project demonstrates how small, well-structured Python modules can simulate real-world retail systems while applying core programming concepts in a scalable and maintainable way.
```

Example:

```python
festival_discount = discount_calculator(20)
festival_discount(5000)  # → 4000
```
The inner function remembers the discount percentage using closure.

---

### 3️⃣ `filters.py`
Handles functional operations:

```python
filter_by_price(products, min_price)
filter_by_category(products, category)
apply_discount_to_products(products, discount_function)
```

Uses:

- `filter()` with lambda expressions
- `map()` with lambda expressions
- Dictionary unpacking (`**p`) to avoid modifying original data

Example of safe dictionary update:

```python
{**p, "price": new_price}
```

---

### 4️⃣ `main.py`
Coordinates the workflow:

- Adds products
- Creates a 20% Festival Discount
- Filters products priced above ₹2000
- Applies discount
- Displays formatted output

---

## ⚙️ Program Workflow

```text
Add Products
      ↓
Create Discount Closure
      ↓
Filter Products (> ₹2000)
      ↓
Apply 20% Discount
      ↓
Display Results
```

---

## ▶️ Sample Output

```text
===== Products Above ₹2000 =====
Name: Laptop
Price: ₹50000
Category: Electronics
------------------------------
Name: Smartphone
Price: ₹25000
Category: Electronics
------------------------------
Name: Headphones
Price: ₹3000
Category: Electronics
------------------------------

===== After 20% Festival Discount on Products Above ₹2000 =====
Name: Laptop
Price: ₹40000.0
Category: Electronics
------------------------------
Name: Smartphone
Price: ₹20000.0
Category: Electronics
------------------------------
Name: Headphones
Price: ₹2400.0
Category: Electronics
------------------------------
```

---

## ▶️ How to Run

Navigate to the project directory:

```bash
cd p1_product_catalog_app/catalog_app
```

Run the application:

```bash
python main.py
```
---

## ✅ Conclusion

This project demonstrates how small, well-structured Python modules can simulate real-world retail systems while applying core programming concepts in a scalable and maintainable way.