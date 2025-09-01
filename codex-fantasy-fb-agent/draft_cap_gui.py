import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os
import sys


def resource_path(rel_path: str) -> str:
    """Resolve resource path for both dev and PyInstaller builds."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, rel_path)


class DraftApp:
    def __init__(self, root):
        """Initialize the Draft Salary Cap GUI application."""
        self.root = root
        self.root.title("Draft Salary Cap Editor")

        # Initial data (attempt to load from CSV first)
        self.players = []
        self.last_values = []
        self.cap = 200  # default salary cap

        initial_csv = resource_path(os.path.join("data", "initial_roster.csv"))
        if os.path.exists(initial_csv):
            try:
                with open(initial_csv, newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                # skip header if present
                if rows and rows[0] and rows[0][0].strip().lower() == "player":
                    rows = rows[1:]
                for row in rows:
                    if not row:
                        continue
                    key0 = row[0].strip()
                    # Allow a special row to set cap, e.g., "Cap,200"
                    if key0.lower() in ("cap", "salary cap", "draft cap"):
                        try:
                            self.cap = int(float(row[1])) if len(row) > 1 else self.cap
                        except Exception:
                            pass
                        continue

                    name = key0
                    if not name:
                        continue
                    salary = 0
                    if len(row) > 1:
                        try:
                            salary = int(float(row[1]))
                        except Exception:
                            salary = 0
                    self.players.append(name)
                    self.last_values.append(salary)
            except Exception:
                # Fallback to hardcoded list on any error
                self.players = []
                self.last_values = []

        if not self.players:
            # Fallback defaults if no CSV present/parsed
            self.players = [
                "Christian McCaffrey",
                "Justin Jefferson",
                "Ja'Marr Chase",
                "Tyreek Hill",
                "Travis Kelce",
            ]
            self.last_values = [0 for _ in self.players]

        # Logging: open file for append mode
        # Use utf-8 to avoid encoding issues
        self.log_file = open("draft_log.txt", "a", encoding="utf-8")

        # Layout frames
        self.frame_top = tk.Frame(root)
        self.frame_top.pack(padx=10, pady=5, fill="x")
        self.frame_table = tk.Frame(root)
        self.frame_table.pack(padx=10, pady=5)
        self.frame_bottom = tk.Frame(root)
        self.frame_bottom.pack(padx=10, pady=5, fill="x")

        # Top frame: Save and Load buttons
        save_button = tk.Button(self.frame_top, text="Save", command=self.save_to_file)
        load_button = tk.Button(self.frame_top, text="Load", command=self.load_from_file)
        save_button.pack(side="left", padx=5)
        load_button.pack(side="left", padx=5)

        # Top frame: Cap adjustment controls on the right
        cap_control_frame = tk.Frame(self.frame_top)
        cap_control_frame.pack(side="right")
        tk.Label(cap_control_frame, text="New Cap:").pack(side="left")
        self.cap_entry = tk.Entry(cap_control_frame, width=8)
        self.cap_entry.pack(side="left", padx=5)
        self.cap_entry.insert(0, str(self.cap))
        set_cap_button = tk.Button(cap_control_frame, text="Set Cap", command=self.update_cap)
        set_cap_button.pack(side="left")

        # Table frame: Column headers for Player and Salary
        header_font = ("Arial", 10, "bold")
        tk.Label(self.frame_table, text="Player", font=header_font).grid(row=0, column=0, padx=5, pady=2)
        tk.Label(self.frame_table, text="Salary", font=header_font).grid(row=0, column=1, padx=5, pady=2)

        # Create initial table rows
        self.name_labels = []
        self.salary_entries = []
        # Populate table rows using current data
        self.refresh_table(self.last_values)

        # Bottom frame: total salary and cap display labels
        self.total_label = tk.Label(self.frame_bottom, text="Total Salary: $0")
        self.total_label.pack(side="left", padx=5)
        self.cap_label = tk.Label(self.frame_bottom, text=f"Cap: ${self.cap}")
        self.cap_label.pack(side="left", padx=15)

        # Calculate initial total
        self.update_total_label()

        # Handle window close to close log file
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_total_label(self):
        """Recalculate total salary and update the total label (turn red if over cap)."""
        total = 0
        for entry in self.salary_entries:
            try:
                val = int(entry.get())
            except ValueError:
                val = 0  # treat invalid or empty as 0
            total += val
        # Update text and color of total label
        self.total_label.config(text=f"Total Salary: ${total}")
        if total > self.cap:
            self.total_label.config(fg="red")
        else:
            self.total_label.config(fg="black")

    def on_salary_change(self, idx):
        """Called when a salary entry loses focus; logs the change if any."""
        self.update_total_label()  # ensure total is updated
        try:
            new_salary = int(self.salary_entries[idx].get())
        except ValueError:
            new_salary = 0
        if new_salary != self.last_values[idx]:
            player_name = self.players[idx]
            log_message = f"{player_name} salary changed to ${new_salary}\n"
            self.log_file.write(log_message)
            self.log_file.flush()
            self.last_values[idx] = new_salary

    def update_cap(self):
        """Update the cap value based on entry input and refresh the display and validation."""
        cap_text = self.cap_entry.get().strip()
        try:
            new_cap = int(cap_text)
        except ValueError:
            messagebox.showerror("Invalid Cap", "Please enter a valid number for the cap.")
            # Restore the entry to the current cap value
            self.cap_entry.delete(0, tk.END)
            self.cap_entry.insert(0, str(self.cap))
            return
        self.cap = new_cap
        self.cap_label.config(text=f"Cap: ${self.cap}")
        # Re-validate total color
        self.update_total_label()
        log_message = f"Cap changed to ${self.cap}\n"
        self.log_file.write(log_message)
        self.log_file.flush()

    def save_to_file(self):
        """Save the current player list and salaries to a CSV file chosen by the user."""
        file_path = filedialog.asksaveasfilename(
            title="Save roster",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not file_path:
            return  # canceled
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                # Optional header for readability in spreadsheets
                writer.writerow(["Player", "Salary"])
                for i, name in enumerate(self.players):
                    try:
                        salary_val = int(self.salary_entries[i].get())
                    except ValueError:
                        salary_val = 0
                    writer.writerow([name, salary_val])
            log_message = f"Saved roster to file {file_path}\n"
            self.log_file.write(log_message)
            self.log_file.flush()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save file:\n{e}")

    def load_from_file(self):
        """Load player list and salaries from a CSV file chosen by the user."""
        file_path = filedialog.askopenfilename(
            title="Load roster",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not file_path:
            return  # canceled
        try:
            with open(file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile)
                new_players = []
                new_salaries = []
                for row in reader:
                    if not row:
                        continue
                    # Skip header row if present
                    if (
                        len(row) >= 2
                        and isinstance(row[0], str)
                        and isinstance(row[1], str)
                        and row[0].strip().lower() == "player"
                        and row[1].strip().lower() == "salary"
                    ):
                        continue
                    name = row[0]
                    salary_val = 0
                    if len(row) > 1:
                        try:
                            salary_val = int(row[1])
                        except ValueError:
                            try:
                                salary_val = int(float(row[1]))
                            except Exception:
                                salary_val = 0
                    new_players.append(name)
                    new_salaries.append(salary_val)

            # Update internal data
            self.players = new_players
            self.last_values = new_salaries.copy()

            # Rebuild table UI with new data
            self.refresh_table(new_salaries)
            log_message = f"Loaded roster from file {file_path}\n"
            self.log_file.write(log_message)
            self.log_file.flush()
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load file:\n{e}")

    def refresh_table(self, salaries):
        """Rebuild the table for the current players list with provided salary values."""
        # Remove old widgets
        for label in self.name_labels:
            label.destroy()
        for entry in self.salary_entries:
            entry.destroy()
        self.name_labels.clear()
        self.salary_entries.clear()

        # Create new rows
        for i, name in enumerate(self.players):
            label = tk.Label(self.frame_table, text=name)
            label.grid(row=i + 1, column=0, sticky="w", padx=5, pady=2)
            self.name_labels.append(label)

            entry = tk.Entry(self.frame_table, width=10)
            entry.grid(row=i + 1, column=1, padx=5, pady=2)
            salary_val = salaries[i] if i < len(salaries) else 0
            entry.insert(0, str(salary_val))
            entry.bind("<KeyRelease>", lambda _e: self.update_total_label())
            entry.bind("<FocusOut>", lambda _e, idx=i: self.on_salary_change(idx))
            self.salary_entries.append(entry)

        self.update_total_label()
        self.cap_label.config(text=f"Cap: ${self.cap}")

    def on_closing(self):
        """Cleanup on window close."""
        try:
            self.log_file.close()
        finally:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = DraftApp(root)
    root.mainloop()
