Draft Player Salary Cap Editor (Tkinter GUI)

Overview

This is a simple desktop app built with Python + Tkinter to manage football players and their draft salaries. It shows a table of players with editable salary fields and displays the running total alongside a configurable salary cap. If the total exceeds the cap, the total turns red. You can save and load rosters from CSV and all actions are logged to `draft_log.txt`.

Features

- Editable salary fields with instant total recalculation
- Salary cap input and validation
- Total turns red when exceeding cap
- Save roster to CSV (with a header)
- Load roster from CSV (header optional)
- Append-only logging of edits, cap changes, saves, loads

Getting Started

1) Prerequisites
- Python 3.8+ with Tkinter support.
  - On Windows/macOS official installers include Tkinter by default.
  - On some Linux distros, install Tk dependencies (e.g., `sudo apt-get install python3-tk`).

2) Run the app

```
python draft_cap_gui.py
```

Usage Tips

- Edit salaries directly in the table; the total updates as you type.
- Click “Set Cap” to apply a new cap value.
- Use “Save” to export a CSV (includes a `Player,Salary` header).
- Use “Load” to import a CSV. If a header line is present, it’s skipped automatically.
- Changes are logged to `draft_log.txt` in the working directory.

CSV Format

- Rows: `Player,Salary`
- Example:
  ```
  Player,Salary
  Christian McCaffrey,45
  Justin Jefferson,43
  Ja'Marr Chase,41
  Tyreek Hill,40
  Travis Kelce,22
  ```

Notes

- Invalid or empty salary cells are treated as 0.
- The app writes logs in UTF-8 encoding.

Customizing Initial Roster

- Place an initial CSV at `data/initial_roster.csv` to seed the table on startup.
- Supported rows:
  - `Player,Salary` rows for each player
  - Optional cap row: `Cap,200` (or `Salary Cap,200` / `Draft Cap,200`)
- Example `data/initial_roster.csv`:
  ```
  Player,Salary
  Cap,200
  Christian McCaffrey,45
  Justin Jefferson,43
  Ja'Marr Chase,41
  Tyreek Hill,40
  Travis Kelce,22
  ```

Import From PDF (helper script)

- A helper script attempts to parse the PDF: `scripts/extract_roster_from_pdf.py`.
- Command:
  ```
  python scripts/extract_roster_from_pdf.py
  ```
- Outputs:
  - `PDFs/parsed_edit_salary_cap.txt` (raw extracted text for review)
  - `data/initial_roster.csv` (parsed players)
- Note: Some PDFs use fonts that prevent reliable text extraction; if parsing is poor, export the PDF to CSV via Adobe/Preview or OCR, then place the CSV at `data/initial_roster.csv`.

Build Windows Executable

- Build script: `scripts/build_exe.ps1`
- Steps:
  1. Optionally create `data/initial_roster.csv` (bundled automatically if present).
  2. Run in PowerShell:
     ```
     powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
     ```
  3. Find the binary at `dist/DraftSalaryCapEditor.exe`.

