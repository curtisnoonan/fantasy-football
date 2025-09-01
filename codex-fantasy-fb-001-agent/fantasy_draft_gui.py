"""
Fantasy Football Salary Cap Draft Manager (Tkinter)

MVP desktop GUI for managing a personal fantasy football salary cap draft list.
- Editable table for Player and Salary
- Preloaded with 5 sample players
- Live total and cap tracking (total turns red when over cap)
- Save/Load to CSV via file dialogs
- Simple action logging to draft_log.txt

Uses only Python standard libraries.
"""

import csv
import re
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# ----------------------------- Constants & Samples -----------------------------
DEFAULT_CAP = 200
SAMPLE_PLAYERS = [
    "Christian McCaffrey",
    "Justin Jefferson",
    "Ja'Marr Chase",
    "Tyreek Hill",
    "Travis Kelce",
]


class DraftApp(tk.Tk):
    """Main Tkinter application class."""

    def __init__(self):
        super().__init__()
        self.title("Fantasy Draft - Salary Cap Manager")
        # Initial size chosen to comfortably fit table and controls
        self.geometry("720x480")
        self.minsize(640, 400)

        # Data structure to hold row widgets and variables
        # Each row: { 'player_var': StringVar, 'salary_var': StringVar,
        #             'player_entry': Entry, 'salary_entry': Entry,
        #             'salary_prev': str }
        self.rows = []

        # Track last known cap value for change logging
        self._cap_last_value = str(DEFAULT_CAP)

        # Build UI
        self._build_ui()

        # Load initial sample players
        self._load_sample_rows()

        # Initial totals update
        self._update_totals()

    # ------------------------------- UI Builders -------------------------------
    def _build_ui(self):
        """Create the main UI layout."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        # Table frame (with headers + rows)
        table_container = ttk.Frame(self, padding=(10, 10, 10, 5))
        table_container.grid(row=0, column=0, sticky="nsew")
        table_container.columnconfigure(0, weight=1)
        table_container.columnconfigure(1, weight=0)

        # Headers
        header_frame = ttk.Frame(table_container)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(0, weight=2)
        header_frame.columnconfigure(1, weight=1)
        header_frame.columnconfigure(2, weight=0)

        ttk.Label(header_frame, text="Player", anchor="w", padding=(4, 4)).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Label(header_frame, text="Salary", anchor="w", padding=(4, 4)).grid(
            row=0, column=1, sticky="ew"
        )
        ttk.Label(header_frame, text="Actions", anchor="w", padding=(4, 4)).grid(
            row=0, column=2, sticky="ew"
        )

        # Scrollable rows area: Canvas + Frame + Vertical Scrollbar
        rows_container = ttk.Frame(table_container)
        rows_container.grid(row=1, column=0, sticky="nsew")
        table_container.rowconfigure(1, weight=1)
        rows_container.columnconfigure(0, weight=1)
        rows_container.rowconfigure(0, weight=1)

        self._rows_canvas = tk.Canvas(rows_container, highlightthickness=0)
        self._rows_canvas.grid(row=0, column=0, sticky="nsew")
        self._rows_scrollbar = ttk.Scrollbar(
            rows_container, orient="vertical", command=self._rows_canvas.yview
        )
        self._rows_scrollbar.grid(row=0, column=1, sticky="ns")
        self._rows_canvas.configure(yscrollcommand=self._rows_scrollbar.set)

        self.rows_frame = ttk.Frame(self._rows_canvas)
        self.rows_frame.columnconfigure(0, weight=2)
        self.rows_frame.columnconfigure(1, weight=1)
        self.rows_frame.columnconfigure(2, weight=0)
        self._rows_frame_id = self._rows_canvas.create_window(
            (0, 0), window=self.rows_frame, anchor="nw"
        )

        # Keep canvas sized to rows frame and update scrollregion
        self.rows_frame.bind("<Configure>", self._configure_rows_canvas)
        self._rows_canvas.bind("<Configure>", self._configure_rows_canvas)

        # Controls frame (totals, cap, save/load)
        controls = ttk.Frame(self, padding=(10, 5, 10, 10))
        controls.grid(row=1, column=0, sticky="ew")
        for i in range(7):
            controls.columnconfigure(i, weight=1)

        # Total label (value updated by _update_totals)
        ttk.Label(controls, text="Total:").grid(row=0, column=0, sticky="w")
        self.total_label = tk.Label(controls, text="$0", anchor="w")
        self.total_label.grid(row=0, column=1, sticky="w")

        # Cap label and entry
        ttk.Label(controls, text="Cap:").grid(row=0, column=2, sticky="e")
        self.cap_var = tk.StringVar(value=str(DEFAULT_CAP))
        cap_vcmd = (self.register(self._validate_money), "%P")
        self.cap_entry = ttk.Entry(
            controls, textvariable=self.cap_var, validate="key", validatecommand=cap_vcmd, width=8
        )
        self.cap_entry.grid(row=0, column=3, sticky="w")
        self.cap_entry.bind("<FocusIn>", self._on_cap_focus_in)
        self.cap_entry.bind("<FocusOut>", self._on_cap_commit)
        self.cap_entry.bind("<Return>", self._on_cap_commit)

        # Row management + Save / Load buttons
        self.add_btn = ttk.Button(controls, text="Add Player", command=self._add_player_row)
        self.add_btn.grid(row=0, column=4, sticky="e", padx=(10, 4))
        self.save_btn = ttk.Button(controls, text="Save", command=self._save_to_csv)
        self.save_btn.grid(row=0, column=5, sticky="e", padx=(4, 4))
        self.load_btn = ttk.Button(controls, text="Load", command=self._load_from_csv)
        self.load_btn.grid(row=0, column=6, sticky="w")

    def _load_sample_rows(self):
        """Preload the table with sample players and blank salaries."""
        for player in SAMPLE_PLAYERS:
            self._add_row(player_name=player, salary_text="")

    def _add_row(self, player_name: str = "", salary_text: str = ""):
        """Add a single editable row to the table."""
        row_index = len(self.rows)

        player_var = tk.StringVar(value=player_name)
        salary_var = tk.StringVar(value=salary_text)

        # Player entry (editable to allow custom names later)
        player_entry = ttk.Entry(self.rows_frame, textvariable=player_var)
        player_entry.grid(row=row_index, column=0, sticky="ew", padx=(0, 8), pady=(2, 2))

        # Salary entry with validation and event hooks
        salary_vcmd = (self.register(self._validate_money), "%P")
        salary_entry = ttk.Entry(
            self.rows_frame,
            textvariable=salary_var,
            validate="key",
            validatecommand=salary_vcmd,
            width=12,
        )
        salary_entry.grid(row=row_index, column=1, sticky="ew", pady=(2, 2))

        # Remove button for this row
        remove_btn = ttk.Button(
            self.rows_frame, text="Remove", width=8, command=lambda idx=row_index: self._remove_row(idx)
        )
        remove_btn.grid(row=row_index, column=2, sticky="e", padx=(8, 0))

        # Keep previous value to log changes on commit
        salary_prev = salary_var.get()

        # Bindings: track edits and commit on focus-out/Enter; recalc on each key
        salary_entry.bind("<FocusIn>", lambda e, sv=salary_var: self._on_salary_focus_in(sv))
        salary_entry.bind(
            "<FocusOut>",
            lambda e, pv=player_var, sv=salary_var: self._on_salary_commit(pv, sv),
        )
        salary_entry.bind(
            "<Return>",
            lambda e, pv=player_var, sv=salary_var: self._on_salary_commit(pv, sv),
        )
        salary_entry.bind("<KeyRelease>", lambda e: self._update_totals())

        # Store row
        self.rows.append(
            {
                "player_var": player_var,
                "salary_var": salary_var,
                "player_entry": player_entry,
                "salary_entry": salary_entry,
                "remove_btn": remove_btn,
                "salary_prev": salary_prev,
            }
        )
        # Update scrollregion after adding a row
        self._configure_rows_canvas()

    # ------------------------ Scrollable Canvas Management -----------------------
    def _configure_rows_canvas(self, _event=None):
        """Keep the inner frame width equal to canvas and update scrollregion."""
        try:
            self._rows_canvas.configure(scrollregion=self._rows_canvas.bbox("all"))
            self._rows_canvas.itemconfig(self._rows_frame_id, width=self._rows_canvas.winfo_width())
        except Exception:
            pass

    # ----------------------------- Validation & Utils -----------------------------
    def _validate_money(self, proposed: str) -> bool:
        """Allow only numbers with optional single decimal point (max 2 decimals)."""
        if proposed == "":
            return True
        # Match '', '123', '123.', '123.4', '123.45'
        return bool(re.fullmatch(r"\d*(?:\.\d{0,2})?", proposed))

    @staticmethod
    def _parse_money(value: str) -> float:
        """Parse a string to float; return 0.0 on failure or empty."""
        if not value:
            return 0.0
        try:
            return float(value)
        except ValueError:
            return 0.0

    @staticmethod
    def _fmt_money(value: float) -> str:
        """Format money: show as integer if whole dollars, else 2 decimals."""
        if value.is_integer():
            return f"${int(value)}"
        return f"${value:.2f}"

    # --------------------------------- Logging ---------------------------------
    def _log_action(self, message: str):
        """Append a timestamped message to draft_log.txt in script directory."""
        try:
            log_path = Path(__file__).resolve().parent / "draft_log.txt"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with log_path.open("a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            # Logging must not break the app; ignore errors silently
            pass

    # --------------------------- Event Handlers (Rows) ---------------------------
    def _on_salary_focus_in(self, salary_var: tk.StringVar):
        """Capture current value before edit to compare on commit."""
        for row in self.rows:
            if row["salary_var"] is salary_var:
                row["salary_prev"] = salary_var.get()
                break

    def _on_salary_commit(self, player_var: tk.StringVar, salary_var: tk.StringVar):
        """On focus-out or Enter: normalize value, log change if any, update totals."""
        new_text = salary_var.get().strip()
        # Normalize invalid to numeric form (empty -> empty kept; otherwise to number)
        if new_text:
            normalized = f"{self._parse_money(new_text):g}"
            salary_var.set(normalized)
        # Log if changed
        for row in self.rows:
            if row["salary_var"] is salary_var:
                prev = row.get("salary_prev", "")
                curr = salary_var.get()
                if prev != curr:
                    self._log_action(
                        f"Salary changed for '{player_var.get()}': {prev or '""'} -> {curr or '""'}"
                    )
                row["salary_prev"] = curr
                break
        self._update_totals()

    # ------------------------- Event Handlers (Cap Entry) ------------------------
    def _on_cap_focus_in(self, _event=None):
        self._cap_last_value = self.cap_var.get()

    def _on_cap_commit(self, _event=None):
        text = self.cap_var.get().strip()
        if text:
            normalized = f"{self._parse_money(text):g}"
            self.cap_var.set(normalized)
        curr = self.cap_var.get()
        if curr != self._cap_last_value:
            self._log_action(f"Cap changed: {self._cap_last_value or '""'} -> {curr or '""'}")
            self._cap_last_value = curr
        self._update_totals()

    # ------------------------------- Totals Logic -------------------------------
    def _update_totals(self):
        total = 0.0
        for row in self.rows:
            total += self._parse_money(row["salary_var"].get())

        cap = self._parse_money(self.cap_var.get())
        self.total_label.configure(text=self._fmt_money(total))

        # Turn total red if exceeding cap; else default foreground
        if total > cap > 0:
            self.total_label.configure(fg="red")
        else:
            # Use system default color by setting empty string
            self.total_label.configure(fg="")

    # ------------------------------ Save / Load CSV ------------------------------
    def _save_to_csv(self):
        """Prompt for a filename and save the current table to CSV."""
        try:
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Save Draft List",
            )
            if not path:
                return

            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Player", "Salary"])  # header
                for row in self.rows:
                    player = row["player_var"].get()
                    salary = row["salary_var"].get()
                    writer.writerow([player, salary])

            self._log_action(f"Saved CSV: {path}")
            messagebox.showinfo("Saved", f"Draft list saved to:\n{path}")
        except Exception as e:
            self._log_action(f"Save failed: {e}")
            messagebox.showerror("Error", f"Failed to save file:\n{e}")

    def _load_from_csv(self):
        """Prompt for a CSV file and load it into the table (replacing rows)."""
        try:
            path = filedialog.askopenfilename(
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Load Draft List",
            )
            if not path:
                return

            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                messagebox.showwarning("Empty File", "The selected CSV file is empty.")
                return

            # Determine if first row is a header
            header = [c.strip().lower() for c in rows[0]]
            has_header = ("player" in header and "salary" in header) or header == ["player", "salary"]

            # Figure column positions if header present
            player_idx, salary_idx = 0, 1
            start_idx = 0
            if has_header:
                start_idx = 1
                try:
                    player_idx = header.index("player")
                    salary_idx = header.index("salary")
                except Exception:
                    player_idx, salary_idx = 0, 1

            data = []
            for r in rows[start_idx:]:
                if len(r) < 2:
                    continue
                player = r[player_idx].strip()
                salary = r[salary_idx].strip()
                data.append((player, salary))

            if not data:
                messagebox.showwarning(
                    "No Rows", "No valid rows with Player and Salary found in the CSV."
                )
                return

            # Clear existing rows from UI
            self._clear_rows()

            # Add loaded rows
            for player, salary in data:
                self._add_row(player_name=player, salary_text=salary)

            self._update_totals()
            self._log_action(f"Loaded CSV: {path}")
            messagebox.showinfo("Loaded", f"Draft list loaded from:\n{path}")
        except Exception as e:
            self._log_action(f"Load failed: {e}")
            messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def _clear_rows(self):
        """Remove all existing rows from the table UI and reset storage."""
        for row in self.rows:
            try:
                row["player_entry"].destroy()
                row["salary_entry"].destroy()
                if row.get("remove_btn"):
                    row["remove_btn"].destroy()
            except Exception:
                pass
        self.rows.clear()
        self._configure_rows_canvas()

    # ---------------------------- Row Management API ----------------------------
    def _add_player_row(self):
        """Add a new blank player row and log the action."""
        self._add_row(player_name="", salary_text="")
        self._log_action("Added player row")
        self._update_totals()

    def _remove_row(self, index: int):
        """Remove a specific row by index, reflow remaining rows, and log."""
        if index < 0 or index >= len(self.rows):
            return
        row = self.rows.pop(index)
        player_name = row["player_var"].get()
        try:
            row["player_entry"].destroy()
            row["salary_entry"].destroy()
            if row.get("remove_btn"):
                row["remove_btn"].destroy()
        except Exception:
            pass

        # Re-grid remaining rows to fill the gap and update remove commands
        for i, r in enumerate(self.rows):
            try:
                r["player_entry"].grid_configure(row=i)
                r["salary_entry"].grid_configure(row=i)
                if r.get("remove_btn"):
                    r["remove_btn"].grid_configure(row=i)
                    r["remove_btn"].configure(command=lambda idx=i: self._remove_row(idx))
            except Exception:
                pass

        self._log_action(f"Removed player row '{player_name}'")
        self._update_totals()
        self._configure_rows_canvas()


if __name__ == "__main__":
    # Run the application
    app = DraftApp()
    app.mainloop()
