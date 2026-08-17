def main():
   num = int(input("Enter a number: "))
   if num < 0:
       print("Please enter a positive integer.")
       return
   reversed_num = 0
   while num > 0:
       reversed_num = reversed_num * 10 + num % 10
       num //= 10
   print("Reversed number:", reversed_num)
if __name__ == "__main__":
    main()
