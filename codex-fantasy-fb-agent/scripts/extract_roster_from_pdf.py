import re
import csv
from pathlib import Path

import pdfplumber


PDF_PATH = Path("PDFs/Edit Salary Cap Draft List Draft Strategy 2025.pdf")
OUT_TEXT_PATH = Path("PDFs/parsed_edit_salary_cap.txt")
OUT_CSV_PATH = Path("data/initial_roster.csv")


def extract_text(pdf_path: Path) -> str:
    text_parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def parse_players_and_salaries(text: str):
    """
    Attempt to parse lines containing a player name and a salary value.

    Heuristics:
    - Accept lines like: "Player Name, 45" or "Player Name - $45" or "Player Name $45"
    - Accept floats but coerce to int
    - Ignore lines without a plausible name + number pattern
    """
    players = []

    # Normalize spacing
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]

    # Patterns capturing name and salary number
    patterns = [
        re.compile(r"^(?P<name>[A-Za-z'.\- ]{3,}?)\s*[-,:]?\s*\$?(?P<salary>\d{1,4})(?:\.\d+)?\b"),
        re.compile(r"^(?P<name>[A-Za-z'.\- ]{3,}?)\s+\$?(?P<salary>\d{1,4})(?:\.\d+)?\b"),
    ]

    for raw in lines:
        if not raw or raw.isdigit():
            continue
        # Skip obvious headers
        if raw.lower().startswith(("player", "rank", "salary", "team", "bye", "pos")):
            continue
        m = None
        for pat in patterns:
            m = pat.search(raw)
            if m:
                break
        if not m:
            continue
        name = m.group("name").strip(" -,:$")
        # Filter out too-short or non-namey strings
        if len(name.split()) < 2:
            continue
        try:
            salary = int(float(m.group("salary")))
        except Exception:
            continue
        players.append((name, salary))

    # Deduplicate preserving first occurrence
    seen = set()
    unique_players = []
    for name, sal in players:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_players.append((name, sal))

    return unique_players


def write_csv(pairs, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Player", "Salary"])
        for name, sal in pairs:
            w.writerow([name, sal])


def main():
    if not PDF_PATH.exists():
        raise SystemExit(f"PDF not found: {PDF_PATH}")

    text = extract_text(PDF_PATH)
    OUT_TEXT_PATH.write_text(text, encoding="utf-8")

    pairs = parse_players_and_salaries(text)
    if not pairs:
        print("Warning: No players parsed. Check parsed text at:", OUT_TEXT_PATH)
    write_csv(pairs, OUT_CSV_PATH)
    print(f"Wrote {len(pairs)} players to {OUT_CSV_PATH}")
    print(f"Raw extracted text saved to {OUT_TEXT_PATH}")


if __name__ == "__main__":
    main()

