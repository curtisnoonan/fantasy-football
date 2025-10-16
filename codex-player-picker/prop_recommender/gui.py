from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List

from .config import Settings, ensure_dirs, load_settings
from .models import Recommendation
from .projections import load_projections_csv
from .recommender import make_recommendations
from .underdog import get_lines


class RecommenderGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Prop Pick Recommender (MVP)")
        self.geometry("980x640")

        # State
        self.settings_path = tk.StringVar(value="config/settings.json")
        self.projections_path = tk.StringVar(value="data/my_projections.csv")
        self.offline_lines_path = tk.StringVar(value="data/lines_sample.json")
        self.out_path = tk.StringVar(value="out/recommended_picks.csv")

        # API inputs (optional)
        self.api_endpoint = tk.StringVar(value="")
        self.api_headers = tk.StringVar(value="{}")
        self.api_preset = tk.StringVar(value="Underdog v3 over_under_lines")
        self.raw_save_path = tk.StringVar(value="data/underdog_raw.json")

        # Projection column mapping (optional)
        self.player_col = tk.StringVar(value="")
        self.team_col = tk.StringVar(value="")
        self.pos_col = tk.StringVar(value="")
        self.proj_col = tk.StringVar(value="")

        self.stat_category = tk.StringVar(value="rushing_yards")
        self.min_diff_abs = tk.DoubleVar(value=10.0)
        self.min_diff_pct = tk.DoubleVar(value=0.10)
        self.rule = tk.StringVar(value="abs_or_pct")
        self.team_required = tk.BooleanVar(value=False)
        self.position_required = tk.BooleanVar(value=False)

        self.status_var = tk.StringVar(value="Ready")
        self.recs: List[Recommendation] = []

        self._build_ui()
        self._load_settings_into_ui(self.settings_path.get())

    def _build_ui(self) -> None:
        # Top controls frame
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=8)

        # Settings file
        ttk.Label(top, text="Config:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.settings_path, width=50).grid(row=0, column=1, sticky=tk.W)
        ttk.Button(top, text="Browse", command=self._browse_settings).grid(row=0, column=2, padx=5)
        ttk.Button(top, text="Load Config", command=self._load_config_clicked).grid(row=0, column=3)
        ttk.Button(top, text="Save Config", command=self._save_config_clicked).grid(row=0, column=4, padx=(6,0))

        # Projections
        ttk.Label(top, text="Projections:").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Entry(top, textvariable=self.projections_path, width=50).grid(row=1, column=1, sticky=tk.W, pady=(6, 0))
        ttk.Button(top, text="Browse", command=self._browse_projections).grid(row=1, column=2, padx=5, pady=(6, 0))

        # Offline lines
        ttk.Label(top, text="Lines JSON:").grid(row=2, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Entry(top, textvariable=self.offline_lines_path, width=50).grid(row=2, column=1, sticky=tk.W, pady=(6, 0))
        ttk.Button(top, text="Browse", command=self._browse_lines).grid(row=2, column=2, padx=5, pady=(6, 0))

        # API endpoint & headers
        ttk.Label(top, text="Preset:").grid(row=4, column=0, sticky=tk.W, pady=(6, 0))
        presets = [
            "Underdog v3 over_under_lines",
            "Underdog v1 over_under_lines",
        ]
        preset_box = ttk.Combobox(top, textvariable=self.api_preset, values=presets, state="readonly", width=32)
        preset_box.grid(row=4, column=1, sticky=tk.W, pady=(6, 0))
        preset_box.bind("<<ComboboxSelected>>", self._apply_preset)

        ttk.Label(top, text="API Endpoint:").grid(row=4, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Entry(top, textvariable=self.api_endpoint, width=50).grid(row=4, column=1, sticky=tk.W, pady=(6, 0))
        ttk.Button(top, text="Fetch Live Lines", command=self._fetch_lines_clicked).grid(row=4, column=2, padx=5, pady=(6, 0))

        ttk.Label(top, text="API Headers (JSON):").grid(row=5, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.api_headers, width=50).grid(row=5, column=1, sticky=tk.W)
        ttk.Label(top, text="Save Raw To:").grid(row=5, column=2, sticky=tk.W)
        ttk.Entry(top, textvariable=self.raw_save_path, width=28).grid(row=5, column=3, sticky=tk.W)

        # Output path
        ttk.Label(top, text="Output CSV:").grid(row=3, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Entry(top, textvariable=self.out_path, width=50).grid(row=3, column=1, sticky=tk.W, pady=(6, 0))
        ttk.Button(top, text="Browse", command=self._browse_out).grid(row=3, column=2, padx=5, pady=(6, 0))

        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=8)

        # Config controls
        cfg = ttk.Frame(self)
        cfg.pack(fill=tk.X, padx=10)

        ttk.Label(cfg, text="Stat Category:").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(cfg, textvariable=self.stat_category, values=[
            "rushing_yards", "receiving_yards", "passing_yards"
        ], state="readonly", width=20).grid(row=0, column=1, padx=5, sticky=tk.W)

        ttk.Label(cfg, text="Min Diff (Abs):").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(cfg, textvariable=self.min_diff_abs, width=10).grid(row=0, column=3, padx=5, sticky=tk.W)

        ttk.Label(cfg, text="Min Diff (Pct):").grid(row=0, column=4, sticky=tk.W)
        ttk.Entry(cfg, textvariable=self.min_diff_pct, width=10).grid(row=0, column=5, padx=5, sticky=tk.W)

        ttk.Label(cfg, text="Rule:").grid(row=0, column=6, sticky=tk.W)
        ttk.Combobox(cfg, textvariable=self.rule, values=[
            "abs_only", "pct_only", "abs_or_pct"
        ], state="readonly", width=12).grid(row=0, column=7, padx=5, sticky=tk.W)

        ttk.Checkbutton(cfg, text="Require Team Match", variable=self.team_required).grid(row=1, column=0, columnspan=2, pady=(6, 0), sticky=tk.W)
        ttk.Checkbutton(cfg, text="Require Position Match", variable=self.position_required).grid(row=1, column=2, columnspan=2, pady=(6, 0), sticky=tk.W)

        # Projection column mapping
        mapf = ttk.Labelframe(self, text="Projections Column Mapping (optional)")
        mapf.pack(fill=tk.X, padx=10, pady=8)
        ttk.Label(mapf, text="Player Col:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(mapf, textvariable=self.player_col, width=20).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(mapf, text="Team Col:").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(mapf, textvariable=self.team_col, width=20).grid(row=0, column=3, sticky=tk.W)
        ttk.Label(mapf, text="Pos Col:").grid(row=0, column=4, sticky=tk.W)
        ttk.Entry(mapf, textvariable=self.pos_col, width=20).grid(row=0, column=5, sticky=tk.W)
        ttk.Label(mapf, text="Projection Col:").grid(row=0, column=6, sticky=tk.W)
        ttk.Entry(mapf, textvariable=self.proj_col, width=20).grid(row=0, column=7, sticky=tk.W)

        # Buttons
        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btns, text="Run", command=self._run_clicked).pack(side=tk.LEFT)
        ttk.Button(btns, text="Save CSV", command=self._save_csv_clicked).pack(side=tk.LEFT, padx=8)
        ttk.Button(btns, text="Prepare Folders & Samples", command=self._prepare_clicked).pack(side=tk.LEFT)

        # Results table
        columns = ("player", "team", "pos", "stat", "line", "proj", "diff", "diffpct", "rec", "source")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=18)
        headers = [
            ("player", "Player"), ("team", "Team"), ("pos", "Pos"), ("stat", "Stat"),
            ("line", "Line"), ("proj", "MyProj"), ("diff", "Diff"), ("diffpct", "Diff%"), ("rec", "Pick"), ("source", "Source")
        ]
        for key, text in headers:
            self.tree.heading(key, text=text)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        # Status bar
        status = ttk.Label(self, textvariable=self.status_var, anchor=tk.W)
        status.pack(fill=tk.X, padx=10, pady=(0, 10))

    def _browse_settings(self) -> None:
        path = filedialog.askopenfilename(title="Select Config", filetypes=[("Config", "*.yaml *.yml *.json"), ("All", "*.*")])
        if path:
            self.settings_path.set(path)

    def _browse_projections(self) -> None:
        path = filedialog.askopenfilename(title="Select Projections CSV", filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if path:
            self.projections_path.set(path)

    def _browse_lines(self) -> None:
        path = filedialog.askopenfilename(title="Select Lines JSON", filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            self.offline_lines_path.set(path)

    def _browse_out(self) -> None:
        path = filedialog.asksaveasfilename(title="Save CSV As", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            self.out_path.set(path)

    def _load_config_clicked(self) -> None:
        self._load_settings_into_ui(self.settings_path.get())

    def _load_settings_into_ui(self, path: str) -> None:
        try:
            settings: Settings = load_settings(path)
            # Mirror into GUI state
            self.stat_category.set(settings.stat_category)
            self.min_diff_abs.set(settings.recommend.min_diff_abs)
            self.min_diff_pct.set(settings.recommend.min_diff_pct)
            self.rule.set(settings.recommend.rule)
            self.team_required.set(settings.matching.team_required)
            self.position_required.set(settings.matching.position_required)
            if settings.api.offline_lines_path:
                self.offline_lines_path.set(settings.api.offline_lines_path)
            if settings.api.endpoint_url:
                self.api_endpoint.set(settings.api.endpoint_url)
            if settings.api.headers:
                try:
                    import json

                    self.api_headers.set(json.dumps(settings.api.headers))
                except Exception:
                    pass
            if settings.output.out_path:
                self.out_path.set(settings.output.out_path)
            # projections column mapping
            pc = getattr(settings, "projections_columns", None)
            if pc:
                if pc.player_col:
                    self.player_col.set(pc.player_col)
                if pc.team_col:
                    self.team_col.set(pc.team_col)
                if pc.pos_col:
                    self.pos_col.set(pc.pos_col)
                if pc.proj_col:
                    self.proj_col.set(pc.proj_col)
            self.status_var.set(f"Loaded config: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Config Error", f"Failed to load config: {e}")

    def _run_clicked(self) -> None:
        # Run heavy work in a thread to keep UI responsive
        threading.Thread(target=self._run_logic, daemon=True).start()

    def _run_logic(self) -> None:
        try:
            self.status_var.set("Running...")
            # Build a Settings instance using the GUI state
            settings: Settings = load_settings(self.settings_path.get())
            settings.stat_category = self.stat_category.get()
            settings.recommend.min_diff_abs = float(self.min_diff_abs.get())
            settings.recommend.min_diff_pct = float(self.min_diff_pct.get())
            settings.recommend.rule = self.rule.get()
            settings.matching.team_required = bool(self.team_required.get())
            settings.matching.position_required = bool(self.position_required.get())
            settings.api.offline_lines_path = self.offline_lines_path.get()
            settings.output.out_path = self.out_path.get()

            ensure_dirs(settings)

            # Load projections
            # Build mapping kwargs
            kwargs = {}
            if self.player_col.get().strip():
                kwargs["player_col"] = self.player_col.get().strip()
            if self.team_col.get().strip():
                kwargs["team_col"] = self.team_col.get().strip()
            if self.pos_col.get().strip():
                kwargs["pos_col"] = self.pos_col.get().strip()
            if self.proj_col.get().strip():
                kwargs["proj_col"] = self.proj_col.get().strip()

            projections = load_projections_csv(
                self.projections_path.get(),
                stat_category=settings.stat_category,
                filter_positions=settings.stat_position_filter,
                **kwargs,
            )

            # Load lines
            lines = get_lines(
                enabled=settings.api.enabled,
                endpoint_url=settings.api.endpoint_url,
                headers=settings.api.headers,
                cache_path=settings.api.cache_path,
                cache_ttl_minutes=settings.api.cache_ttl_minutes,
                offline_lines_path=settings.api.offline_lines_path,
            )

            # Compute recs
            self.recs = make_recommendations(
                lines=lines,
                projections=projections,
                stat_category=settings.stat_category,
                team_required=settings.matching.team_required,
                position_required=settings.matching.position_required,
                min_diff_abs=settings.recommend.min_diff_abs,
                min_diff_pct=settings.recommend.min_diff_pct,
                rule=settings.recommend.rule,
            )

            # Update table
            self._populate_table(self.recs)

            # Status
            if not self.recs:
                self.status_var.set("No strong value edges found - no picks recommended today.")
            else:
                over = sum(1 for r in self.recs if r.recommendation == "OVER")
                under = sum(1 for r in self.recs if r.recommendation == "UNDER")
                self.status_var.set(f"Found {len(self.recs)} props ({over} Over, {under} Under)")
        except Exception as e:
            messagebox.showerror("Run Error", f"Failed to run: {e}")
            self.status_var.set("Error")

    def _populate_table(self, recs: List[Recommendation]) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        for r in recs:
            self.tree.insert("", tk.END, values=(
                r.player,
                r.team or "",
                r.pos or "",
                r.stat_category,
                f"{r.line_value:.1f}",
                f"{r.projection:.1f}",
                f"{r.diff:.1f}",
                f"{r.diff_pct:.3f}",
                r.recommendation,
                (r.meta or {}).get("source", ""),
            ))

    def _save_csv_clicked(self) -> None:
        try:
            if not self.recs:
                messagebox.showinfo("Save CSV", "No recommendations to save.")
                return
            # Write CSV using the same format as CLI
            import csv

            path = self.out_path.get() or "out/recommended_picks.csv"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Player", "Team", "Pos", "StatCategory", "Line", "MyProjection", "Diff", "DiffPct", "Recommendation", "Source"])
                for r in self.recs:
                    writer.writerow([
                        r.player,
                        r.team or "",
                        r.pos or "",
                        r.stat_category,
                        f"{r.line_value:.1f}",
                        f"{r.projection:.1f}",
                        f"{r.diff:.1f}",
                        f"{r.diff_pct:.3f}",
                        r.recommendation,
                        (r.meta or {}).get("source", ""),
                    ])
            messagebox.showinfo("Save CSV", f"Saved to {path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save CSV: {e}")

    def _save_config_clicked(self) -> None:
        try:
            # Compose a config dict from current UI state
            cfg = {
                "stat_category": self.stat_category.get(),
                # default position filter based on stat
                "stat_position_filter": self._default_positions_for_stat_gui(self.stat_category.get()),
                "recommend": {
                    "min_diff_abs": float(self.min_diff_abs.get()),
                    "min_diff_pct": float(self.min_diff_pct.get()),
                    "rule": self.rule.get(),
                },
                "api": {
                    "enabled": bool(self.api_endpoint.get().strip()),
                    "endpoint_url": self.api_endpoint.get(),
                    "headers": self._parse_headers_safely(self.api_headers.get()),
                    "cache_path": "data/cache/underdog_lines.json",
                    "cache_ttl_minutes": 60,
                    "offline_lines_path": self.offline_lines_path.get(),
                },
                "matching": {
                    "name_strategy": "case_insensitive",
                    "team_required": bool(self.team_required.get()),
                    "position_required": bool(self.position_required.get()),
                },
                "output": {
                    "out_path": self.out_path.get(),
                    "include_no_bet": False,
                },
                "projections_columns": {
                    "player_col": self.player_col.get().strip() or None,
                    "team_col": self.team_col.get().strip() or None,
                    "pos_col": self.pos_col.get().strip() or None,
                    "proj_col": self.proj_col.get().strip() or None,
                },
            }

            dest = self.settings_path.get()
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)

            if dest.lower().endswith((".yaml", ".yml")):
                try:
                    import yaml  # type: ignore

                    with open(dest, "w", encoding="utf-8") as f:
                        yaml.safe_dump(cfg, f, sort_keys=False)
                except Exception:
                    # Fallback to JSON if YAML not available
                    import json

                    with open(dest, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=2)
            else:
                import json

                with open(dest, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)

            self.status_var.set(f"Saved config: {dest}")
            messagebox.showinfo("Save Config", f"Saved config to {dest}")
        except Exception as e:
            messagebox.showerror("Save Config Error", f"Failed to save config: {e}")

    def _prepare_clicked(self) -> None:
        try:
            # Ensure dirs
            for p in [self.out_path.get(), self.offline_lines_path.get(), self.projections_path.get(), self.settings_path.get()]:
                d = os.path.dirname(p) or "."
                os.makedirs(d, exist_ok=True)

            # Copy sample projections/lines if target files missing
            here = os.path.dirname(os.path.abspath(__file__))
            sample_proj = os.path.normpath(os.path.join(here, "..", "data", "my_projections.csv"))
            sample_lines = os.path.normpath(os.path.join(here, "..", "data", "lines_sample.json"))

            self._copy_if_missing(sample_proj, self.projections_path.get())
            self._copy_if_missing(sample_lines, self.offline_lines_path.get())

            # Save config as part of preparation
            self._save_config_clicked()

            self.status_var.set("Prepared folders and sample data.")
        except Exception as e:
            messagebox.showerror("Prepare Error", f"Failed to prepare: {e}")

    @staticmethod
    def _copy_if_missing(src: str, dst: str) -> None:
        try:
            if not os.path.exists(dst) and os.path.exists(src):
                os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
                    fdst.write(fsrc.read())
        except Exception:
            # Non-fatal
            pass

    @staticmethod
    def _default_positions_for_stat_gui(stat_category: str):
        s = stat_category.strip().lower()
        if s == "rushing_yards":
            return ["RB"]
        if s == "receiving_yards":
            return ["WR", "TE"]
        if s == "passing_yards":
            return ["QB"]
        return []

    @staticmethod
    def _parse_headers_safely(text: str):
        try:
            import json

            obj = json.loads(text) if text and text.strip() else {}
            if isinstance(obj, dict):
                # ensure str->str
                return {str(k): str(v) for k, v in obj.items()}
            return {}
        except Exception:
            return {}

    def _fetch_lines_clicked(self) -> None:
        # Run in background
        threading.Thread(target=self._fetch_lines_logic, daemon=True).start()

    def _fetch_lines_logic(self) -> None:
        try:
            self.status_var.set("Fetching live lines...")
            endpoint = self.api_endpoint.get().strip()
            if not endpoint:
                messagebox.showwarning("Missing Endpoint", "Please enter API Endpoint URL.")
                self.status_var.set("Ready")
                return

            headers = self._parse_headers_safely(self.api_headers.get())

            from .underdog import fetch_underdog_lines, normalize_payload, lines_to_normalized_json

            raw = fetch_underdog_lines(endpoint, headers)
            lines = normalize_payload(raw)
            if not lines:
                messagebox.showwarning("No Lines", "Fetched data but could not normalize any lines. Save raw JSON and share a sample to add support.")
                self.status_var.set("No lines normalized")
                return

            # Save normalized lines to offline path
            dest = self.offline_lines_path.get() or "data/lines_sample.json"
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            import json

            with open(dest, "w", encoding="utf-8") as f:
                json.dump(lines_to_normalized_json(lines), f, indent=2)

            # Save raw if path provided
            rawp = self.raw_save_path.get().strip()
            if rawp:
                try:
                    os.makedirs(os.path.dirname(rawp) or ".", exist_ok=True)
                    with open(rawp, "w", encoding="utf-8") as rf:
                        import json as _json
                        rf.write(_json.dumps(raw, indent=2))
                except Exception:
                    pass

            self.status_var.set(f"Fetched {len(lines)} lines -> {dest}")
            messagebox.showinfo("Fetch Complete", f"Fetched {len(lines)} lines and saved to:\n{dest}")
        except Exception as e:
            messagebox.showerror("Fetch Error", f"Failed to fetch lines: {e}")
            self.status_var.set("Fetch error")

    def _apply_preset(self, *_):
        sel = self.api_preset.get()
        if sel == "Underdog v3 over_under_lines":
            self.api_endpoint.set("https://api.underdogfantasy.com/beta/v3/over_under_lines")
        elif sel == "Underdog v1 over_under_lines":
            self.api_endpoint.set("https://api.underdogfantasy.com/v1/over_under_lines")


def main() -> int:
    app = RecommenderGUI()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
