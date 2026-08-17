def main():
    # Step 1: List of tuples
    movies = [
        ("Inception", 2010, 148, "Sci-Fi"),
        ("Titanic", 1997, 195, "Romance"),
        ("Avatar", 2009, 162, "Sci-Fi")
    ]

    # Step 2: Unique movie titles using set comprehension
    unique_titles = {movie[0] for movie in movies}
    print("Unique Movie Titles:")
    for title in unique_titles:
        print(title)

    # Step 3: Dictionary mapping title -> (year, duration, genre)
    movie_dict = {
        movie[0]: (movie[1], movie[2], movie[3])
        for movie in movies
    }

    # Step 4: Search movie by title
    search_title = input("\nEnter movie title to view details: ")

    if search_title in movie_dict:
        year, duration, genre = movie_dict[search_title]
        print(f"{search_title} | Year: {year} | Duration: {duration} mins | Genre: {genre}")
    else:
        print("Movie not found.")

    # Step 5: Update movie genre
    update_title = input("\nEnter movie title to update genre: ")

    if update_title in movie_dict:
        year, duration, old_genre = movie_dict[update_title]
        new_genre = input("Enter new genre: ")

        movie_dict[update_title] = (year, duration, new_genre)
        print(f"Genre updated successfully for {update_title}.")
    else:
        print("Movie not found.")

    # Step 6: Analysis
    print("\n--- Movie Collection Analysis ---")

    # Total unique movies
    print(f"Total unique movies: {len(movie_dict)}")

    # Unique genres using set comprehension
    unique_genres = {details[2] for details in movie_dict.values()}
    print("Unique genres:", unique_genres)

    # Movies released after 2000 using list comprehension
    movies_after_2000 = [
        title for title, details in movie_dict.items()
        if details[0] > 2000
    ]

    print("Movies released after 2000:", movies_after_2000)


if __name__ == "__main__":
    main()