# ==========================================================
#           LIBRARY MANAGEMENT SYSTEM  (BACKEND + console)
# Hash table (books) + Indexed student search + Deque queue
# + Undo stack + Merge sort + CSV file handling
# + Due date + Automatic fine calculation
#
# This file is the BACKEND. library_gui.py imports it.
# Run this file for the console version, or run library_gui.py for the GUI.
# ==========================================================

import csv
import os
from collections import deque
from datetime import date, datetime, timedelta

# ---------------------------- settings ----------------------------
LOAN_DAYS = 14             # days a book can be kept
FINE_PER_DAY = 2           # fine (Rs) per overdue day
MAX_BOOKS_PER_STUDENT = 3
DATE_FMT = "%Y-%m-%d"

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:                      # some online IDEs have no __file__
    BASE_DIR = os.getcwd()

BOOKS_FILE = os.path.join(BASE_DIR, "books.csv")
STUDENTS_FILE = os.path.join(BASE_DIR, "students.csv")
RESERVATIONS_FILE = os.path.join(BASE_DIR, "reservations.csv")


# ==========================================================
# BOOK CLASS
# ==========================================================

class Book:

    def __init__(self, book_id, title, author, category):
        self.book_id = book_id
        self.title = title
        self.author = author
        self.category = category

        self.available = True
        self.borrower_id = None
        self.borrower_name = ""
        self.issue_date = None      # datetime.date or None
        self.due_date = None        # datetime.date or None


# ==========================================================
# STUDENT CLASS
# ==========================================================

class Student:

    def __init__(self, student_id, name):
        self.student_id = student_id
        self.name = name


# ==========================================================
# HASH TABLE FOR BOOKS (separate chaining, auto-resize)
# ==========================================================

class BookHashTable:

    MAX_LOAD = 0.75

    def __init__(self, size=11):
        self.size = size
        self.table = [[] for _ in range(size)]
        self.count = 0

    def hash_function(self, book_id):
        return book_id % self.size

    def insert(self, book):
        if self.search(book.book_id) is not None:
            return False                      # duplicate ID

        if (self.count + 1) / self.size > self.MAX_LOAD:
            self._resize()

        self.table[self.hash_function(book.book_id)].append(book)
        self.count += 1
        return True

    def search(self, book_id):
        for book in self.table[self.hash_function(book_id)]:
            if book.book_id == book_id:
                return book
        return None                           # FIX: original never returned this

    def delete(self, book_id):
        bucket = self.table[self.hash_function(book_id)]
        for i, book in enumerate(bucket):
            if book.book_id == book_id:
                del bucket[i]
                self.count -= 1
                return True
        return False

    def all_books(self):
        return [b for bucket in self.table for b in bucket]

    def _resize(self):
        old_books = self.all_books()
        self.size = self.size * 2 + 1
        self.table = [[] for _ in range(self.size)]
        for b in old_books:
            self.table[self.hash_function(b.book_id)].append(b)


# ==========================================================
# MERGE SORT (stable, O(n log n))
# ==========================================================

def merge_sort(items, key):
    if len(items) <= 1:
        return items
    mid = len(items) // 2
    left = merge_sort(items[:mid], key)
    right = merge_sort(items[mid:], key)

    merged, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if key(left[i]) <= key(right[j]):
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


# ==========================================================
# LIBRARY
# ==========================================================

class Library:

    def __init__(self):
        self.books = BookHashTable()
        self.students = {}          # student_id -> Student      (index by ID)
        self.name_index = {}        # name word  -> {student_id} (index by name)
        self.reservations = {}      # book_id    -> deque[student_id]
        self.undo_stack = []        # stack of action records

    # ---------------------- books ----------------------

    def add_book(self, book_id, title, author, category):
        return self.books.insert(Book(book_id, title, author, category))

    def remove_book(self, book_id):
        book = self.books.search(book_id)
        if book is None:
            return False, "Book not found."
        if not book.available:
            return False, "Book is currently issued; cannot remove."
        self.books.delete(book_id)
        self.reservations.pop(book_id, None)
        self.undo_stack = [r for r in self.undo_stack
                           if r["book_id"] != book_id]
        return True, f"Removed '{book.title}'."

    def search_books(self, text):
        text = text.lower().strip()
        return [b for b in self.books.all_books()
                if text in b.title.lower() or text in b.author.lower()
                or text in b.category.lower()]

    def sorted_books(self, field):
        keys = {
            "id": lambda b: b.book_id,
            "title": lambda b: b.title.lower(),
            "author": lambda b: b.author.lower(),
            "category": lambda b: b.category.lower(),
        }
        return merge_sort(self.books.all_books(), keys[field])

    def count_borrowed(self, student_id):
        return sum(1 for b in self.books.all_books()
                   if not b.available and b.borrower_id == student_id)

    # ---------------------- students ----------------------

    def add_student(self, student_id, name):
        if student_id in self.students:
            return False
        self.students[student_id] = Student(student_id, name)
        for word in name.lower().split():
            self.name_index.setdefault(word, set()).add(student_id)
        return True

    def find_student_by_id(self, student_id):
        return self.students.get(student_id)

    def find_students_by_name(self, query):
        q = query.lower().strip()
        if not q:
            return []
        if " " in q:                                   # full-name search
            return [s for s in self.students.values() if q in s.name.lower()]
        ids = set()
        for word, id_set in self.name_index.items():   # prefix search on index
            if word.startswith(q):
                ids |= id_set
        return [self.students[i] for i in sorted(ids)]

    # ---------------------- fines ----------------------

    @staticmethod
    def calculate_fine(book, today=None):
        today = today or date.today()
        if book.due_date is None:
            return 0
        return max(0, (today - book.due_date).days) * FINE_PER_DAY

    # ---------------------- issue / return ----------------------

    def issue_book(self, book_id, student_id, today=None):
        today = today or date.today()
        book = self.books.search(book_id)
        student = self.students.get(student_id)

        if book is None:
            return False, "Book not found."
        if student is None:
            return False, "Student not found."
        if not book.available:
            return False, (f"Already issued to {book.borrower_name}. "
                           "You can reserve it.")
        if self.count_borrowed(student_id) >= MAX_BOOKS_PER_STUDENT:
            return False, f"Limit of {MAX_BOOKS_PER_STUDENT} books reached."

        queue = self.reservations.get(book_id)
        was_front = False
        if queue:
            if queue[0] != student_id:
                first = self.students[queue[0]].name
                return False, f"Reserved for {first} (first in queue)."
            queue.popleft()
            was_front = True

        book.available = False
        book.borrower_id = student_id
        book.borrower_name = student.name
        book.issue_date = today
        book.due_date = today + timedelta(days=LOAN_DAYS)

        self.undo_stack.append({"type": "issue", "book_id": book_id,
                                "student_id": student_id,
                                "was_front": was_front})
        return True, (f"Issued '{book.title}' to {student.name}. "
                      f"Due on {book.due_date}.")

    def return_book(self, book_id, today=None):
        today = today or date.today()
        book = self.books.search(book_id)
        if book is None:
            return False, "Book not found."
        if book.available:
            return False, "This book is not issued."

        fine = self.calculate_fine(book, today)
        self.undo_stack.append({"type": "return", "book_id": book_id,
                                "student_id": book.borrower_id,
                                "issue_date": book.issue_date,
                                "due_date": book.due_date})
        name = book.borrower_name

        book.available = True
        book.borrower_id = None
        book.borrower_name = ""
        book.issue_date = None
        book.due_date = None

        msg = f"'{book.title}' returned by {name}."
        msg += f" Fine: Rs {fine}." if fine else " No fine."
        queue = self.reservations.get(book_id)
        if queue:
            msg += f" Now held for {self.students[queue[0]].name}."
        return True, msg

    # ---------------------- reservations (queue) ----------------------

    def reserve_book(self, book_id, student_id):
        book = self.books.search(book_id)
        if book is None:
            return False, "Book not found."
        if student_id not in self.students:
            return False, "Student not found."
        if book.available and not self.reservations.get(book_id):
            return False, "Book is available; just issue it."
        if book.borrower_id == student_id:
            return False, "You already have this book."
        queue = self.reservations.setdefault(book_id, deque())
        if student_id in queue:
            return False, "Already in the queue."
        queue.append(student_id)
        return True, f"Added to queue. Position: {len(queue)}."

    def queue_for(self, book_id):
        return [self.students[i] for i in self.reservations.get(book_id, [])]

    # ---------------------- undo (stack) ----------------------

    def undo(self):
        if not self.undo_stack:
            return False, "Nothing to undo."
        rec = self.undo_stack.pop()
        book = self.books.search(rec["book_id"])
        if book is None:
            return False, "Book no longer exists."

        if rec["type"] == "issue":
            book.available = True
            book.borrower_id = None
            book.borrower_name = ""
            book.issue_date = book.due_date = None
            if rec["was_front"]:
                self.reservations.setdefault(rec["book_id"], deque()
                                             ).appendleft(rec["student_id"])
            return True, f"Undid issue of '{book.title}'."

        student = self.students.get(rec["student_id"])
        book.available = False
        book.borrower_id = rec["student_id"]
        book.borrower_name = student.name if student else ""
        book.issue_date = rec["issue_date"]
        book.due_date = rec["due_date"]
        return True, f"Undid return of '{book.title}'."

    # ---------------------- reports ----------------------

    def overdue_books(self, today=None):
        today = today or date.today()
        return [b for b in self.books.all_books()
                if not b.available and b.due_date and b.due_date < today]

    # ---------------------- file handling ----------------------

    def save(self):
        with open(BOOKS_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["book_id", "title", "author", "category", "available",
                        "borrower_id", "borrower_name", "issue_date",
                        "due_date"])
            for b in self.sorted_books("id"):
                w.writerow([b.book_id, b.title, b.author, b.category,
                            int(b.available),
                            "" if b.borrower_id is None else b.borrower_id,
                            b.borrower_name,
                            b.issue_date.strftime(DATE_FMT) if b.issue_date else "",
                            b.due_date.strftime(DATE_FMT) if b.due_date else ""])

        with open(STUDENTS_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["student_id", "name"])
            for s in self.students.values():
                w.writerow([s.student_id, s.name])

        with open(RESERVATIONS_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["book_id", "student_id"])
            for book_id, q in self.reservations.items():
                for sid in q:
                    w.writerow([book_id, sid])

    @staticmethod
    def _parse_date(text):
        try:
            return datetime.strptime(text, DATE_FMT).date() if text else None
        except ValueError:
            return None

    def load(self):
        """Returns True if saved data was found. Never crashes on bad files."""
        try:
            found = self._load_files()
        except (OSError, csv.Error, UnicodeDecodeError) as err:
            print(f"  Warning: could not fully read saved data ({err}).")
            found = True
        # repair inconsistent rows so no book gets stuck
        for b in self.books.all_books():
            if not b.available and (b.borrower_id is None
                                    or b.borrower_id not in self.students):
                b.available = True
                b.borrower_id, b.borrower_name = None, ""
                b.issue_date = b.due_date = None
            elif not b.available and b.due_date is None:
                b.issue_date = b.issue_date or date.today()
                b.due_date = b.issue_date + timedelta(days=LOAN_DAYS)
        return found

    def _load_files(self):
        """Reads the CSV files."""
        if not os.path.exists(BOOKS_FILE) and not os.path.exists(STUDENTS_FILE):
            return False

        if os.path.exists(STUDENTS_FILE):
            with open(STUDENTS_FILE, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    try:
                        self.add_student(int(row["student_id"]), row["name"])
                    except (ValueError, KeyError):
                        continue                      # skip corrupt row

        if os.path.exists(BOOKS_FILE):
            with open(BOOKS_FILE, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    try:
                        b = Book(int(row["book_id"]), row["title"],
                                 row["author"], row["category"])
                        b.available = row["available"] == "1"
                        if not b.available and row["borrower_id"]:
                            b.borrower_id = int(row["borrower_id"])
                            b.borrower_name = row["borrower_name"]
                            b.issue_date = self._parse_date(row["issue_date"])
                            b.due_date = self._parse_date(row["due_date"])
                        self.books.insert(b)
                    except (ValueError, KeyError):
                        continue

        if os.path.exists(RESERVATIONS_FILE):
            with open(RESERVATIONS_FILE, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    try:
                        bid, sid = int(row["book_id"]), int(row["student_id"])
                    except (ValueError, KeyError):
                        continue
                    if self.books.search(bid) and sid in self.students:
                        self.reservations.setdefault(bid, deque()).append(sid)
        return True

    def load_sample_data(self):
        samples = [
            (101, "Python Crash Course", "Eric Matthes", "Programming"),
            (102, "Data Structures Using C", "Reema Thareja", "Programming"),
            (103, "Introduction to Algorithms", "Thomas Cormen", "Algorithms"),
            (104, "Wings of Fire", "A.P.J. Abdul Kalam", "Biography"),
            (105, "Clean Code", "Robert Martin", "Programming"),
        ]
        for s in samples:
            self.add_book(*s)
        for sid, name in [(1, "Arun Kumar"), (2, "Priya Sharma"),
                          (3, "Karthik Raja")]:
            self.add_student(sid, name)


# ==========================================================
# CONSOLE UI
# (To use the window/GUI version instead, run library_gui.py)
# ==========================================================

def read_int(prompt):
    while True:
        text = input(prompt).strip()
        try:
            value = int(text)
        except ValueError:
            print("  Please enter a whole number.")
            continue
        if value <= 0:
            print("  ID must be a positive number.")
            continue
        return value


def safe_save(lib):
    try:
        lib.save()
    except OSError as err:
        print(f"  Warning: could not save data ({err}).")


def read_text(prompt):
    while True:
        text = input(prompt).strip()
        if text:
            return text
        print("  This field cannot be empty.")


def show_books(books):
    if not books:
        print("  (no books)")
        return
    print(f"  {'ID':<6}{'Title':<30}{'Author':<22}{'Category':<14}Status")
    print("  " + "-" * 90)
    for b in books:
        if b.available:
            status = "Available"
        else:
            status = f"{b.borrower_name} (due {b.due_date})"
        print(f"  {b.book_id:<6}{b.title[:28]:<30}{b.author[:20]:<22}"
              f"{b.category[:12]:<14}{status}")


SORT_MENU = """  1. Sort by Book ID
  2. Sort by Title
  3. Sort by Author
  4. Sort by Category
  5. Show only AVAILABLE books
  6. Show only NOT AVAILABLE (issued) books"""

SORT_ALIASES = {
    "1": "id", "id": "id", "book id": "id", "bookid": "id",
    "2": "title", "title": "title", "name": "title", "book name": "title",
    "3": "author", "author": "author", "writer": "author",
    "4": "category", "category": "category", "type": "category",
    "5": "available", "available": "available",
    "6": "issued", "not available": "issued", "notavailable": "issued",
    "unavailable": "issued", "issued": "issued",
}


def ask_sort_mode():
    """Keeps asking until the choice is valid. Blank input cancels."""
    print(SORT_MENU)
    while True:
        text = input("Choose (1-6, or press Enter to cancel): ").strip().lower()
        if text == "":
            return None
        if text in SORT_ALIASES:
            return SORT_ALIASES[text]
        print("  Invalid choice. Enter a number 1-6 (or a word like "
              "title, author, available, not available).")


def show_students(students):
    if not students:
        print("  (no matching students)")
    for s in students:
        print(f"  ID {s.student_id}: {s.name}")


MENU = """
================ LIBRARY MANAGEMENT ================
 1. Add book              7. Issue book
 2. Remove book           8. Return book (fine auto-calculated)
 3. Add student           9. Reserve book (join queue)
 4. Find student         10. View reservation queue
 5. Search books         11. Overdue report
 6. List books (sorted)  12. Undo last issue/return
 0. Save and exit
====================================================="""


def main():
    lib = Library()
    if lib.load():
        print("Loaded saved data.")
    else:
        lib.load_sample_data()
        print("No saved data found. Sample data loaded.")

    while True:
        print(MENU)
        choice = input("Choose: ").strip()
        mutated = True

        if choice == "1":
            bid = read_int("Book ID: ")
            ok = lib.add_book(bid, read_text("Title: "),
                              read_text("Author: "), read_text("Category: "))
            print("  Book added." if ok else "  A book with that ID exists.")

        elif choice == "2":
            print(" ", lib.remove_book(read_int("Book ID: "))[1])

        elif choice == "3":
            sid = read_int("Student ID: ")
            ok = lib.add_student(sid, read_text("Name: "))
            print("  Student added." if ok else "  That student ID exists.")

        elif choice == "4":
            mutated = False
            how = input("Search by (1) ID or (2) name? ").strip()
            if how == "1":
                s = lib.find_student_by_id(read_int("Student ID: "))
                show_students([s] if s else [])
            elif how == "2":
                show_students(lib.find_students_by_name(read_text("Name: ")))
            else:
                print("  Invalid option. Enter 1 or 2.")

        elif choice == "5":
            mutated = False
            show_books(lib.search_books(read_text("Title/author/category: ")))

        elif choice == "6":
            mutated = False
            mode = ask_sort_mode()
            if mode is not None:
                if mode in ("id", "title", "author", "category"):
                    show_books(lib.sorted_books(mode))
                elif mode == "available":
                    show_books([b for b in lib.sorted_books("id")
                                if b.available])
                else:  # "issued"
                    show_books([b for b in lib.sorted_books("id")
                                if not b.available])

        elif choice == "7":
            ok, msg = lib.issue_book(read_int("Book ID: "),
                                     read_int("Student ID: "))
            print(" ", msg)

        elif choice == "8":
            print(" ", lib.return_book(read_int("Book ID: "))[1])

        elif choice == "9":
            ok, msg = lib.reserve_book(read_int("Book ID: "),
                                       read_int("Student ID: "))
            print(" ", msg)

        elif choice == "10":
            mutated = False
            q = lib.queue_for(read_int("Book ID: "))
            if not q:
                print("  Queue is empty.")
            for pos, s in enumerate(q, 1):
                print(f"  {pos}. {s.name} (ID {s.student_id})")

        elif choice == "11":
            mutated = False
            overdue = lib.overdue_books()
            if not overdue:
                print("  No overdue books.")
            for b in overdue:
                print(f"  {b.title} | {b.borrower_name} | due {b.due_date} | "
                      f"fine so far Rs {lib.calculate_fine(b)}")

        elif choice == "12":
            print(" ", lib.undo()[1])

        elif choice == "0":
            safe_save(lib)
            print("Data saved. Goodbye!")
            break

        else:
            mutated = False
            print("  Invalid choice.")

        if mutated:
            safe_save(lib)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting. (Data is saved after every change.)")
