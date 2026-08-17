def main():
    num1 = float(input("Enter first number: "))
    num2 = float(input("Enter second number: "))

    print("Addition:", num1 + num2)
    print("Subtraction:", num1 - num2)
    print("Multiplication:", num1 * num2)

    if num2 != 0:
        print("Division:", num1 / num2)
        print("Modulus:", num1 % num2)
        print("Floor Division:", num1 // num2)
    else:
        print("Division: Cannot divide by zero")
        print("Modulus: Cannot perform modulus with zero")
        print("Floor Division: Cannot perform floor division with zero")

    print("Exponentiation:", num1 ** num2)


if __name__ == "__main__":
    main()
