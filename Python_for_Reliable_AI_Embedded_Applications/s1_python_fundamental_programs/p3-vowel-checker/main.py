def main():
    ch = input("Enter an alphabet: ").strip().lower()

    if len(ch) != 1 or not ch.isalpha():
        print("Invalid input")
    elif ch in ('a', 'e', 'i', 'o', 'u'):
        print("Vowel")
    else:
        print("Consonant")


if __name__ == "__main__":
    main()
