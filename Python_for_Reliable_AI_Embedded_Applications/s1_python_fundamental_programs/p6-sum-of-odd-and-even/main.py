def main():
    num = int(input("Enter a number: "))

    if 9999999 < num < 100000000:
        sum_even = 0
        sum_odd = 0

        for digit in str(num):
            d = int(digit)
            if d % 2 == 0:
                sum_even += d
            else:
                sum_odd += d

        print(f"Sum of even numbers: {sum_even}")
        print(f"Sum of odd numbers: {sum_odd}")
    else:
        print("Please enter an 8-digit number.")


if __name__ == "__main__":
    main()
