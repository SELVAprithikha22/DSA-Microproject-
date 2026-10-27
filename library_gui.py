# ==========================================================
#   LIBRARY MANAGEMENT SYSTEM - TKINTER GUI
#   Uses the Library class from library_system.py (the backend).
#   Keep BOTH files in the same folder and run THIS file:
#       python library_gui.py
# ==========================================================

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from library_system import (Library, LOAN_DAYS, FINE_PER_DAY,
                            MAX_BOOKS_PER_STUDENT)


class LibraryApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Library Management System")
        self.geometry("1000x640")
        self.minsize(900, 560)

        self.lib = Library()
        if not self.lib.load():
            self.lib.load_sample_data()

        self.status = tk.StringVar(value="Ready.")
        self._build_ui()
        self.refresh_all()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------
    # helpers
    # ------------------------------------------------------
    def persist(self):
        try:
            self.lib.save()
        except OSError as err:
            messagebox.showwarning("Save failed",
                                   f"Could not save data:\n{err}")

    def need_int(self, text, label):
        try:
            value = int(text.strip())
        except ValueError:
            messagebox.showerror("Invalid input",
                                 f"{label} must be a whole number.")
            return None
        if value <= 0:
            messagebox.showerror("Invalid input",
                                 f"{label} must be a positive number.")
            return None
        return value

    def report(self, ok, msg):
        """Show result of a library action, save and refresh on success."""
        self.status.set(msg)
        if ok:
            messagebox.showinfo("Done", msg)
            self.persist()
            self.refresh_all()
        else:
            messagebox.showwarning("Not allowed", msg)

    def make_tree(self, parent, columns, widths):
        frame = ttk.Frame(parent)
        tree = ttk.Treeview(frame, columns=[c for c, _ in columns],
                            show="headings", selectmode="browse")
        for (col, heading), width in zip(columns, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return frame, tree

    # ------------------------------------------------------
    # layout
    # ------------------------------------------------------
    def _build_ui(self):
        header = tk.Label(self, text="Library Management System",
                          font=("Segoe UI", 16, "bold"),
                          bg="#2c3e50", fg="white", pady=8)
        header.pack(fill="x")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)

        self.books_tab = ttk.Frame(self.tabs)
        self.students_tab = ttk.Frame(self.tabs)
        self.circ_tab = ttk.Frame(self.tabs)
        self.overdue_tab = ttk.Frame(self.tabs)

        self.tabs.add(self.books_tab, text="  Books  ")
        self.tabs.add(self.students_tab, text="  Students  ")
        self.tabs.add(self.circ_tab, text="  Issue / Return  ")
        self.tabs.add(self.overdue_tab, text="  Overdue  ")

        self._build_books_tab()
        self._build_students_tab()
        self._build_circulation_tab()
        self._build_overdue_tab()

        bar = tk.Label(self, textvariable=self.status, anchor="w",
                       relief="sunken", padx=6)
        bar.pack(fill="x", side="bottom")

        self.tabs.bind("<<NotebookTabChanged>>", lambda e: self.refresh_all())

    # ---------------------- books tab ----------------------
    def _build_books_tab(self):
        t = self.books_tab

        top = ttk.Frame(t)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Search:").pack(side="left")
        self.book_search = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.book_search, width=24)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda e: self.refresh_books())
        ttk.Button(top, text="Search",
                   command=self.refresh_books).pack(side="left")
        ttk.Button(top, text="Clear", command=self.clear_book_search
                   ).pack(side="left", padx=4)

        ttk.Label(top, text="   Sort by:").pack(side="left")
        self.sort_var = tk.StringVar(value="Book ID")
        sort_box = ttk.Combobox(top, textvariable=self.sort_var, width=10,
                                state="readonly",
                                values=["Book ID", "Title", "Author",
                                        "Category"])
        sort_box.pack(side="left", padx=4)
        sort_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_books())

        ttk.Label(top, text="Show:").pack(side="left")
        self.filter_var = tk.StringVar(value="All")
        filt_box = ttk.Combobox(top, textvariable=self.filter_var, width=12,
                                state="readonly",
                                values=["All", "Available", "Issued"])
        filt_box.pack(side="left", padx=4)
        filt_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_books())

        cols = [("id", "ID"), ("title", "Title"), ("author", "Author"),
                ("category", "Category"), ("status", "Status"),
                ("due", "Due Date")]
        frame, self.book_tree = self.make_tree(
            t, cols, [60, 260, 190, 120, 180, 100])
        frame.pack(fill="both", expand=True, padx=8)
        self.book_tree.tag_configure("issued", foreground="#b9770e")
        self.book_tree.tag_configure("overdue", foreground="#c0392b")

        # add / remove
        box = ttk.LabelFrame(t, text="Add / Remove book")
        box.pack(fill="x", padx=8, pady=8)

        self.nb_id = tk.StringVar()
        self.nb_title = tk.StringVar()
        self.nb_author = tk.StringVar()
        self.nb_cat = tk.StringVar()
        for i, (label, var, w) in enumerate([
                ("ID", self.nb_id, 8), ("Title", self.nb_title, 24),
                ("Author", self.nb_author, 18),
                ("Category", self.nb_cat, 14)]):
            ttk.Label(box, text=label).grid(row=0, column=i * 2,
                                            padx=(8, 2), pady=6)
            ttk.Entry(box, textvariable=var, width=w).grid(
                row=0, column=i * 2 + 1, padx=(0, 6))
        ttk.Button(box, text="Add Book", command=self.add_book
                   ).grid(row=0, column=8, padx=6)
        ttk.Button(box, text="Remove Selected", command=self.remove_book
                   ).grid(row=0, column=9, padx=6)

    def clear_book_search(self):
        self.book_search.set("")
        self.sort_var.set("Book ID")
        self.filter_var.set("All")
        self.refresh_books()

    def add_book(self):
        bid = self.need_int(self.nb_id.get(), "Book ID")
        if bid is None:
            return
        title = self.nb_title.get().strip()
        author = self.nb_author.get().strip()
        cat = self.nb_cat.get().strip()
        if not (title and author and cat):
            messagebox.showerror("Missing data",
                                 "Title, author and category are required.")
            return
        if self.lib.add_book(bid, title, author, cat):
            for v in (self.nb_id, self.nb_title, self.nb_author, self.nb_cat):
                v.set("")
            self.report(True, f"Book '{title}' added.")
        else:
            self.report(False, "A book with that ID already exists.")

    def remove_book(self):
        sel = self.book_tree.selection()
        if not sel:
            messagebox.showinfo("Select a book",
                                "Click a book in the table first.")
            return
        bid = int(sel[0])
        book = self.lib.books.search(bid)
        if book and messagebox.askyesno(
                "Confirm", f"Remove '{book.title}' from the library?"):
            ok, msg = self.lib.remove_book(bid)
            self.report(ok, msg)

    def refresh_books(self):
        for row in self.book_tree.get_children():
            self.book_tree.delete(row)

        field = {"Book ID": "id", "Title": "title", "Author": "author",
                 "Category": "category"}[self.sort_var.get()]
        books = self.lib.sorted_books(field)          # merge sort

        text = self.book_search.get().strip()
        if text:
            ids = {b.book_id for b in self.lib.search_books(text)}
            books = [b for b in books if b.book_id in ids]

        mode = self.filter_var.get()
        if mode == "Available":
            books = [b for b in books if b.available]
        elif mode == "Issued":
            books = [b for b in books if not b.available]

        today = date.today()
        for b in books:
            if b.available:
                status, due, tag = "Available", "", ""
            else:
                status = f"Issued to {b.borrower_name}"
                due = str(b.due_date) if b.due_date else ""
                tag = ("overdue" if b.due_date and b.due_date < today
                       else "issued")
            self.book_tree.insert("", "end", iid=str(b.book_id),
                                  values=(b.book_id, b.title, b.author,
                                          b.category, status, due),
                                  tags=(tag,))

    # ---------------------- students tab ----------------------
    def _build_students_tab(self):
        t = self.students_tab

        top = ttk.Frame(t)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Find student by:").pack(side="left")
        self.stu_mode = tk.StringVar(value="Name")
        ttk.Combobox(top, textvariable=self.stu_mode, width=6,
                     state="readonly", values=["ID", "Name"]
                     ).pack(side="left", padx=4)
        self.stu_query = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.stu_query, width=24)
        e.pack(side="left", padx=4)
        e.bind("<Return>", lambda ev: self.find_student())
        ttk.Button(top, text="Find", command=self.find_student
                   ).pack(side="left")
        ttk.Button(top, text="Show All", command=self.show_all_students
                   ).pack(side="left", padx=4)

        cols = [("id", "Student ID"), ("name", "Name"),
                ("borrowed", f"Books borrowed (max {MAX_BOOKS_PER_STUDENT})")]
        frame, self.stu_tree = self.make_tree(t, cols, [100, 300, 220])
        frame.pack(fill="both", expand=True, padx=8)

        box = ttk.LabelFrame(t, text="Add student")
        box.pack(fill="x", padx=8, pady=8)
        self.ns_id = tk.StringVar()
        self.ns_name = tk.StringVar()
        ttk.Label(box, text="Student ID").grid(row=0, column=0, padx=(8, 2),
                                               pady=6)
        ttk.Entry(box, textvariable=self.ns_id, width=10
                  ).grid(row=0, column=1, padx=(0, 10))
        ttk.Label(box, text="Name").grid(row=0, column=2, padx=(8, 2))
        ttk.Entry(box, textvariable=self.ns_name, width=28
                  ).grid(row=0, column=3, padx=(0, 10))
        ttk.Button(box, text="Add Student", command=self.add_student
                   ).grid(row=0, column=4, padx=6)

        self.stu_filter = None      # None = show all, else list of students

    def add_student(self):
        sid = self.need_int(self.ns_id.get(), "Student ID")
        if sid is None:
            return
        name = self.ns_name.get().strip()
        if not name:
            messagebox.showerror("Missing data", "Name cannot be empty.")
            return
        if self.lib.add_student(sid, name):
            self.ns_id.set("")
            self.ns_name.set("")
            self.stu_filter = None
            self.report(True, f"Student '{name}' added.")
        else:
            self.report(False, "That student ID already exists.")

    def find_student(self):
        q = self.stu_query.get().strip()
        if not q:
            self.stu_filter = None
        elif self.stu_mode.get() == "ID":
            sid = self.need_int(q, "Student ID")
            if sid is None:
                return
            s = self.lib.find_student_by_id(sid)
            self.stu_filter = [s] if s else []
        else:
            self.stu_filter = self.lib.find_students_by_name(q)
        self.refresh_students()
        if self.stu_filter is not None and not self.stu_filter:
            self.status.set("No matching students.")

    def show_all_students(self):
        self.stu_query.set("")
        self.stu_filter = None
        self.refresh_students()

    def refresh_students(self):
        for row in self.stu_tree.get_children():
            self.stu_tree.delete(row)
        students = (self.stu_filter if self.stu_filter is not None
                    else sorted(self.lib.students.values(),
                                key=lambda s: s.student_id))
        for s in students:
            self.stu_tree.insert("", "end", values=(
                s.student_id, s.name, self.lib.count_borrowed(s.student_id)))

    # ---------------------- issue / return tab ----------------------
    def _build_circulation_tab(self):
        t = self.circ_tab

        info = ttk.Label(
            t, text=(f"Loan period: {LOAN_DAYS} days   |   "
                     f"Fine: Rs {FINE_PER_DAY} per overdue day   |   "
                     f"Max {MAX_BOOKS_PER_STUDENT} books per student"),
            font=("Segoe UI", 9, "italic"))
        info.pack(anchor="w", padx=10, pady=(10, 0))

        form = ttk.LabelFrame(t, text="Circulation")
        form.pack(fill="x", padx=8, pady=8)

        self.c_book = tk.StringVar()
        self.c_student = tk.StringVar()
        ttk.Label(form, text="Book ID").grid(row=0, column=0, padx=(8, 2),
                                             pady=8)
        be = ttk.Entry(form, textvariable=self.c_book, width=10)
        be.grid(row=0, column=1, padx=(0, 12))
        be.bind("<KeyRelease>", lambda e: self.refresh_queue())
        ttk.Label(form, text="Student ID").grid(row=0, column=2, padx=(8, 2))
        ttk.Entry(form, textvariable=self.c_student, width=10
                  ).grid(row=0, column=3, padx=(0, 12))

        ttk.Button(form, text="Issue", command=self.issue
                   ).grid(row=0, column=4, padx=4)
        ttk.Button(form, text="Return", command=self.return_book
                   ).grid(row=0, column=5, padx=4)
        ttk.Button(form, text="Reserve", command=self.reserve
                   ).grid(row=0, column=6, padx=4)
        ttk.Button(form, text="Undo Last Issue/Return", command=self.undo
                   ).grid(row=0, column=7, padx=(16, 8))

        qbox = ttk.LabelFrame(t, text="Reservation queue for the Book ID above")
        qbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = [("pos", "Position"), ("id", "Student ID"), ("name", "Name")]
        frame, self.queue_tree = self.make_tree(qbox, cols, [80, 100, 300])
        frame.pack(fill="both", expand=True, padx=6, pady=6)

    def issue(self):
        b = self.need_int(self.c_book.get(), "Book ID")
        s = self.need_int(self.c_student.get(), "Student ID")
        if b is None or s is None:
            return
        ok, msg = self.lib.issue_book(b, s)
        self.report(ok, msg)

    def return_book(self):
        b = self.need_int(self.c_book.get(), "Book ID")
        if b is None:
            return
        ok, msg = self.lib.return_book(b)
        self.report(ok, msg)

    def reserve(self):
        b = self.need_int(self.c_book.get(), "Book ID")
        s = self.need_int(self.c_student.get(), "Student ID")
        if b is None or s is None:
            return
        ok, msg = self.lib.reserve_book(b, s)
        self.report(ok, msg)

    def undo(self):
        ok, msg = self.lib.undo()
        self.report(ok, msg)

    def refresh_queue(self):
        for row in self.queue_tree.get_children():
            self.queue_tree.delete(row)
        try:
            bid = int(self.c_book.get().strip())
        except ValueError:
            return
        for pos, s in enumerate(self.lib.queue_for(bid), 1):
            self.queue_tree.insert("", "end",
                                   values=(pos, s.student_id, s.name))

    # ---------------------- overdue tab ----------------------
    def _build_overdue_tab(self):
        t = self.overdue_tab
        top = ttk.Frame(t)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Refresh", command=self.refresh_overdue
                   ).pack(side="left")
        self.overdue_total = tk.StringVar()
        ttk.Label(top, textvariable=self.overdue_total,
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=16)

        cols = [("id", "Book ID"), ("title", "Title"),
                ("who", "Borrower"), ("due", "Due Date"),
                ("days", "Days Overdue"), ("fine", "Fine (Rs)")]
        frame, self.overdue_tree = self.make_tree(
            t, cols, [70, 260, 180, 100, 100, 90])
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def refresh_overdue(self):
        for row in self.overdue_tree.get_children():
            self.overdue_tree.delete(row)
        today = date.today()
        total = 0
        overdue = self.lib.overdue_books()
        for b in overdue:
            fine = self.lib.calculate_fine(b)
            total += fine
            self.overdue_tree.insert("", "end", values=(
                b.book_id, b.title, b.borrower_name, b.due_date,
                (today - b.due_date).days, fine))
        self.overdue_total.set(
            f"{len(overdue)} overdue book(s)   |   Total fine: Rs {total}"
            if overdue else "No overdue books.")

    # ------------------------------------------------------
    def refresh_all(self):
        self.refresh_books()
        self.refresh_students()
        self.refresh_queue()
        self.refresh_overdue()

    def on_close(self):
        self.persist()
        self.destroy()


if __name__ == "__main__":
    LibraryApp().mainloop()
