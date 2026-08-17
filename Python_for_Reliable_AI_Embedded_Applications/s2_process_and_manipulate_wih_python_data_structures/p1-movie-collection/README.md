## Practice Exercise: Organize and Analyze Movie Collection

### Problem Statement
Develop a Python program to manage and analyze a collection of movies.  
The program should allow users to store, access, update, and analyze movie details efficiently using appropriate Python data structures.

Each movie contains the following details:
- Title
- Year of Release
- Duration (in minutes)
- Genre

---

## Context

A film enthusiast wants to organize their growing movie collection for analytics but finds it difficult to track movie details such as release year, duration, and genre.  

An efficient system is required to:
- Avoid duplicate movie entries
- Allow fast lookup of movie details
- Update information easily
- Perform simple analysis on the collection

---

## Implementation Overview

The solution is implemented using different Python data structures to demonstrate their practical use.

---

### Step 1: Store Movie Details (List of Tuples)

- Each movie is stored as a tuple:
(title, year, duration, genre)

- All movies are stored inside a list.
- Tuples ensure movie records remain immutable.

---

### Step 2: Unique Movie Titles (Set)

- A set comprehension is used to extract unique movie titles.
- Sets automatically ignore duplicate entries.
- All unique movie titles are displayed.

---

### Step 3: Title–Detail Mapping (Dictionary)

- A dictionary is created where:
key → movie title
value → (year, duration, genre)

- This allows:
- Fast lookup
- Easy updates
- Efficient data retrieval

---

### Step 4: Search and Display Movie Details

- The user can search for a movie by title.
- If the movie exists:
- Its details are displayed.
- Otherwise:
- A "Movie not found" message is shown.

---

### Step 5: Update Movie Genre

- The program allows updating the genre of an existing movie.
- Since tuples are immutable:
- A new tuple is created
- The dictionary value is replaced with updated data

---

### Step 6: Analyze Movie Collection

The program performs basic analysis:

- Displays total number of unique movies.
- Displays unique genres using set comprehension.
- Displays movies released after 2000 using list comprehension.

---

## Sample Movie Data

| Title     | Release Year | Duration | Genre   |
|-----------|-------------|----------|---------|
| Inception | 2010        | 148      | Sci-Fi  |
| Titanic   | 1997        | 195      | Romance |
| Avatar    | 2009        | 162      | Sci-Fi  |

---

## Concepts Demonstrated

This exercise demonstrates the practical use of:

- List
- Tuple
- Set
- Dictionary
- Set Comprehension
- List Comprehension
- Dictionary Comprehension

---

## How to Run

1. Ensure Python 3.x is installed.
2. Navigate to the project directory.
3. Run:

```bash
python main.py
```