from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Any, List, Tuple, Optional
import threading

from .config import load_config, Config
from .logging_config import setup_logging
from .espn_client import get_league
from .exporters import (
    export_rosters,
    export_standings,
    export_matchups,
    export_player_stats,
    export_free_agents,
)

try:
    from analyze_players import (
        load_rosters as ap_load_rosters,
        load_player_games as ap_load_player_games,
        compute_metrics as ap_compute_metrics,
        tag_categories as ap_tag_categories,
    )
except Exception:  # pragma: no cover
    ap_load_rosters = None  # type: ignore
    ap_load_player_games = None  # type: ignore
    ap_compute_metrics = None  # type: ignore
    ap_tag_categories = None  # type: ignore


def _write_yaml(path: str, cfg: Config) -> None:
    import yaml  # lazy import

    data = {
        "league_id": cfg.league_id,
        "season": cfg.season,
        "espn_s2": cfg.espn_s2,
        "swid": cfg.swid,
        "output_dir": cfg.output_dir,
        "log_dir": cfg.log_dir,
        "log_level": cfg.log_level,
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _write_env(path: str, values: Dict[str, Any]) -> None:
    lines = []
    for k in ["ESPN_S2", "SWID", "LEAGUE_ID", "SEASON", "OUTPUT_DIR", "LOG_DIR", "LOG_LEVEL"]:
        v = values.get(k)
        if v is None:
            continue
        v_str = str(v)
        if any(ch in v_str for ch in [" ", "#", "="]):
            v_str = f'"{v_str}"'
        lines.append(f"{k}={v_str}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


class ConfigGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Fantasy Football Config")
        self.geometry("560x420")
        self.resizable(False, False)

        # Paths for saving
        self.yaml_path = tk.StringVar(value="config.yaml")
        self.env_path = tk.StringVar(value=".env")

        # Form variables
        self.league_id = tk.StringVar()
        self.season = tk.StringVar()
        self.week = tk.StringVar()
        self.espn_s2 = tk.StringVar()
        self.swid = tk.StringVar()
        self.output_dir = tk.StringVar(value="data/exports")
        self.log_dir = tk.StringVar(value="logs")
        self.log_level = tk.StringVar(value="INFO")

        # Last export paths for analysis convenience
        self._last_paths: Dict[str, Optional[str]] = {
            "rosters": None,
            "player_stats": None,
            "standings": None,
            "matchups": None,
            "free_agents": None,
        }

        self._build_ui()
        self._load_current()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        row = 0
        # Config file paths
        ttk.Label(self, text="YAML Config").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.yaml_path, width=44).grid(row=row, column=1, **pad)
        ttk.Button(self, text="Browse", command=self._browse_yaml).grid(row=row, column=2, **pad)
        row += 1
        ttk.Label(self, text=".env File").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.env_path, width=44).grid(row=row, column=1, **pad)
        ttk.Button(self, text="Browse", command=self._browse_env).grid(row=row, column=2, **pad)

        # Separator
        row += 1
        ttk.Separator(self, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", padx=10, pady=8)

        # Config fields
        row += 1
        ttk.Label(self, text="League ID").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.league_id, width=22).grid(row=row, column=1, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Season").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.season, width=22).grid(row=row, column=1, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Week (for matchups)").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.week, width=22).grid(row=row, column=1, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="ESPN_S2").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.espn_s2, width=44).grid(row=row, column=1, columnspan=2, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="SWID").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.swid, width=44).grid(row=row, column=1, columnspan=2, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Output Dir").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.output_dir, width=44).grid(row=row, column=1, **pad)
        ttk.Button(self, text="Browse", command=self._browse_output).grid(row=row, column=2, **pad)
        row += 1
        ttk.Label(self, text="Log Dir").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.log_dir, width=44).grid(row=row, column=1, **pad)
        ttk.Button(self, text="Browse", command=self._browse_logdir).grid(row=row, column=2, **pad)
        row += 1
        ttk.Label(self, text="Log Level").grid(row=row, column=0, sticky="e", **pad)
        cb = ttk.Combobox(self, textvariable=self.log_level, values=["DEBUG", "INFO", "WARNING", "ERROR"], width=20, state="readonly")
        cb.grid(row=row, column=1, sticky="w", **pad)

        # Buttons
        row += 1
        ttk.Separator(self, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", padx=10, pady=8)
        row += 1
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=10)
        self._btn_reload = ttk.Button(btn_frame, text="Reload", command=self._load_current)
        self._btn_reload.grid(row=0, column=0, padx=6)
        self._btn_save_yaml = ttk.Button(btn_frame, text="Save YAML", command=self._save_yaml)
        self._btn_save_yaml.grid(row=0, column=1, padx=6)
        self._btn_save_env = ttk.Button(btn_frame, text="Save .env", command=self._save_env)
        self._btn_save_env.grid(row=0, column=2, padx=6)
        self._btn_save_all = ttk.Button(btn_frame, text="Save All", command=self._save_all)
        self._btn_save_all.grid(row=0, column=3, padx=6)
        self._btn_export = ttk.Button(btn_frame, text="Export CSV (All)", command=self._export_all_bg)
        self._btn_export.grid(row=0, column=4, padx=6)
        self._btn_analyze = ttk.Button(btn_frame, text="Analyze Players", command=self._analyze_players_bg)
        self._btn_analyze.grid(row=0, column=5, padx=6)
        self._btn_close = ttk.Button(btn_frame, text="Close", command=self.destroy)
        self._btn_close.grid(row=0, column=6, padx=6)

        # Status + Progress
        row += 1
        status_frame = ttk.Frame(self)
        status_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=10)
        self.columnconfigure(0, weight=1)
        status_frame.columnconfigure(0, weight=1)
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self._status_var, anchor="w").grid(row=0, column=0, sticky="w")
        self._progress = ttk.Progressbar(status_frame, mode="determinate", maximum=3, value=0)
        self._progress.grid(row=1, column=0, sticky="ew", pady=(4, 0))

    def _browse_yaml(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".yaml", filetypes=[("YAML", "*.yaml;*.yml"), ("All", "*.*")], initialfile=self.yaml_path.get())
        if path:
            self.yaml_path.set(path)

    def _browse_env(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".env", filetypes=[("Env", "*.env"), ("All", "*.*")], initialfile=self.env_path.get())
        if path:
            self.env_path.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(initialdir=self.output_dir.get() or os.getcwd())
        if path:
            self.output_dir.set(path)

    def _browse_logdir(self) -> None:
        path = filedialog.askdirectory(initialdir=self.log_dir.get() or os.getcwd())
        if path:
            self.log_dir.set(path)

    def _load_current(self) -> None:
        try:
            cfg = load_config(config_path=self.yaml_path.get(), dotenv_path=self.env_path.get())
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load config: {e}")
            return

        if cfg.league_id is not None:
            self.league_id.set(str(cfg.league_id))
        if cfg.season is not None:
            self.season.set(str(cfg.season))
        if cfg.espn_s2 is not None:
            self.espn_s2.set(cfg.espn_s2)
        if cfg.swid is not None:
            self.swid.set(cfg.swid)
        self.output_dir.set(cfg.output_dir or "data/exports")
        self.log_dir.set(cfg.log_dir or "logs")
        self.log_level.set((cfg.log_level or "INFO").upper())
        # Don't auto-fill week; user can specify or we infer later

    def _collect_values(self) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        # Validate integer fields
        lid = self.league_id.get().strip()
        season = self.season.get().strip()
        if lid:
            if not lid.isdigit():
                raise ValueError("League ID must be an integer")
            values["LEAGUE_ID"] = int(lid)
        if season:
            if not season.isdigit():
                raise ValueError("Season must be an integer")
            values["SEASON"] = int(season)

        values["ESPN_S2"] = self.espn_s2.get().strip() or None
        values["SWID"] = self.swid.get().strip() or None
        values["OUTPUT_DIR"] = self.output_dir.get().strip() or "data/exports"
        values["LOG_DIR"] = self.log_dir.get().strip() or "logs"
        values["LOG_LEVEL"] = (self.log_level.get().strip() or "INFO").upper()
        return values

    def _save_yaml(self) -> None:
        try:
            vals = self._collect_values()
            cfg = Config(
                league_id=vals.get("LEAGUE_ID"),
                season=vals.get("SEASON"),
                espn_s2=vals.get("ESPN_S2"),
                swid=vals.get("SWID"),
                output_dir=vals.get("OUTPUT_DIR", "data/exports"),
                log_dir=vals.get("LOG_DIR", "logs"),
                log_level=vals.get("LOG_LEVEL", "INFO"),
            )
            _write_yaml(self.yaml_path.get(), cfg)
            messagebox.showinfo("Saved", f"Wrote {self.yaml_path.get()}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save YAML: {e}")

    def _save_env(self) -> None:
        try:
            vals = self._collect_values()
            _write_env(self.env_path.get(), vals)
            messagebox.showinfo("Saved", f"Wrote {self.env_path.get()}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save .env: {e}")

    def _save_all(self) -> None:
        self._save_yaml()
        self._save_env()

    # ---- Background export with progress ----
    def _set_busy(self, busy: bool) -> None:
        try:
            if busy:
                self.config(cursor="watch")
                self._btn_export.state(["disabled"])
                try:
                    self._btn_analyze.state(["disabled"])
                except Exception:
                    pass
            else:
                self.config(cursor="")
                self._btn_export.state(["!disabled"])
                try:
                    self._btn_analyze.state(["!disabled"])
                except Exception:
                    pass
            self.update_idletasks()
        except Exception:
            pass

    def _progress_start(self, max_steps: int) -> None:
        self._progress.configure(maximum=max_steps, value=0, mode="determinate")
        self._status_var.set("Starting export...")
        self._set_busy(True)

    def _progress_step(self, message: str = "") -> None:
        val = int(self._progress["value"]) + 1
        self._progress.configure(value=val)
        if message:
            self._status_var.set(message)

    def _progress_finish(self, message: str = "Done") -> None:
        self._progress.configure(value=self._progress["maximum"]) 
        self._status_var.set(message)
        self._set_busy(False)

    def _perform_export(self, cfg: Config, week_val: Optional[int]) -> Tuple[bool, List[Tuple[str, str]], Optional[str]]:
        outputs: List[Tuple[str, str]] = []
        try:
            # Determine steps count: rosters, standings, player stats, free agents, + matchups if week
            max_steps = 4 + (1 if week_val is not None else 0)
            self.after(0, lambda: self._progress_start(max_steps))
            # Connect
            self.after(0, lambda: self._status_var.set("Connecting to league..."))
            league = get_league(cfg)
            # Rosters
            self.after(0, lambda: self._progress_step("Exporting rosters..."))
            r_path = export_rosters(league, cfg.output_dir, cfg.season or 0)
            outputs.append(("Rosters", r_path))
            self._last_paths["rosters"] = r_path
            # Standings
            self.after(0, lambda: self._progress_step("Exporting standings..."))
            s_path = export_standings(league, cfg.output_dir, cfg.season or 0)
            outputs.append(("Standings", s_path))
            self._last_paths["standings"] = s_path
            # Player stats (all weeks if week_val is None)
            self.after(0, lambda: self._progress_step("Exporting player stats..."))
            p_path = export_player_stats(league, cfg.output_dir, cfg.season or 0, weeks=[week_val] if week_val is not None else None)
            outputs.append(("Player Stats", p_path))
            self._last_paths["player_stats"] = p_path

            # Free agents (use specified week if provided for a snapshot)
            self.after(0, lambda: self._progress_step("Exporting free agents..."))
            fa_path = export_free_agents(league, cfg.output_dir, cfg.season or 0, week=week_val)
            outputs.append(("Free Agents", fa_path))
            self._last_paths["free_agents"] = fa_path

            # Matchups
            if week_val is not None:
                self.after(0, lambda: self._progress_step(f"Exporting matchups (week {week_val})..."))
                m_path = export_matchups(league, cfg.output_dir, cfg.season or 0, week_val)
                outputs.append((f"Matchups (week {week_val})", m_path))
                self._last_paths["matchups"] = m_path
            else:
                outputs.append(("Matchups", "Skipped (no week specified or inferred)"))
            return True, outputs, None
        except Exception as e:
            return False, outputs, str(e)
        finally:
            self.after(0, lambda: self._progress_finish("Export complete"))

    def _export_all_bg(self) -> None:
        try:
            vals = self._collect_values()
            if "LEAGUE_ID" not in vals or "SEASON" not in vals:
                messagebox.showerror("Export Error", "League ID and Season are required to export")
                return
            cfg = Config(
                league_id=vals.get("LEAGUE_ID"),
                season=vals.get("SEASON"),
                espn_s2=vals.get("ESPN_S2"),
                swid=vals.get("SWID"),
                output_dir=vals.get("OUTPUT_DIR", "data/exports"),
                log_dir=vals.get("LOG_DIR", "logs"),
                log_level=vals.get("LOG_LEVEL", "INFO"),
            )
            setup_logging(cfg.log_dir, cfg.log_level)

            week_str = self.week.get().strip()
            week_val = int(week_str) if week_str.isdigit() else None
            # If no week provided, try to infer after connecting (handled in worker)

            def worker():
                nonlocal week_val
                # If week is None, attempt inference (requires a league), handled inside _perform_export via get_league
                # But we need league to infer; we handle inference before exporters here for simplicity only if possible.
                # Leave inference to exporter stage using league.current_week.
                if week_val is None:
                    # We'll let _perform_export infer via league, see logic there (sets skipped if still None)
                    pass
                success, outputs, err = self._perform_export(cfg, week_val)
                def show_result():
                    if success:
                        msg_lines = ["Export complete:"] + [f"- {name}: {path}" for name, path in outputs]
                        messagebox.showinfo("Export", "\n".join(msg_lines))
                    else:
                        messagebox.showerror("Export Error", err or "Unknown error")
                self.after(0, show_result)

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to start export: {e}")

    def _export_all(self) -> None:
        # Perform export of rosters, standings, and matchups (if week is available)
        try:
            vals = self._collect_values()
            # Require league and season
            if "LEAGUE_ID" not in vals or "SEASON" not in vals:
                raise ValueError("League ID and Season are required to export")

            cfg = Config(
                league_id=vals.get("LEAGUE_ID"),
                season=vals.get("SEASON"),
                espn_s2=vals.get("ESPN_S2"),
                swid=vals.get("SWID"),
                output_dir=vals.get("OUTPUT_DIR", "data/exports"),
                log_dir=vals.get("LOG_DIR", "logs"),
                log_level=vals.get("LOG_LEVEL", "INFO"),
            )

            # Setup logging minimally; GUI is primary UX but logs still helpful
            setup_logging(cfg.log_dir, cfg.log_level)

            # Long-ish operation: indicate busy cursor
            self.config(cursor="watch")
            self.update_idletasks()

            league = get_league(cfg)

            outputs = []
            r_path = export_rosters(league, cfg.output_dir, cfg.season or 0)
            outputs.append(("Rosters", r_path))
            s_path = export_standings(league, cfg.output_dir, cfg.season or 0)
            outputs.append(("Standings", s_path))

            week_str = self.week.get().strip()
            week_val = int(week_str) if week_str.isdigit() else None
            if week_val is None:
                cw = getattr(league, "current_week", None)
                if isinstance(cw, int):
                    week_val = cw

            if week_val is not None:
                m_path = export_matchups(league, cfg.output_dir, cfg.season or 0, week_val)
                outputs.append((f"Matchups (week {week_val})", m_path))
            else:
                outputs.append(("Matchups", "Skipped (no week specified or inferred)"))

            msg_lines = ["Export complete:"] + [f"- {name}: {path}" for name, path in outputs]
            messagebox.showinfo("Export", "\n".join(msg_lines))
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}")
        finally:
            self.config(cursor="")
            self.update_idletasks()

    # ---- Analysis ----
    def _analyze_players_bg(self) -> None:
        """Analyze players using last exported CSVs or prompt to select files."""
        if ap_load_rosters is None or ap_load_player_games is None or ap_compute_metrics is None or ap_tag_categories is None:
            messagebox.showerror("Analyze Error", "Analysis module not available. Ensure analyze_players.py exists.")
            return

        players_csv = self._last_paths.get("player_stats") or ""
        rosters_csv = self._last_paths.get("rosters") or ""

        if not players_csv or not os.path.exists(players_csv):
            players_csv = filedialog.askopenfilename(
                title="Select Players CSV",
                initialdir=self.output_dir.get() or os.getcwd(),
                filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            )
            if not players_csv:
                return
        if not rosters_csv or not os.path.exists(rosters_csv):
            rosters_csv = filedialog.askopenfilename(
                title="Select Rosters CSV",
                initialdir=self.output_dir.get() or os.getcwd(),
                filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            )
            if not rosters_csv:
                return

        def worker() -> None:
            try:
                self.after(0, lambda: self._status_var.set("Analyzing players..."))
                self.after(0, lambda: self._set_busy(True))
                ownership = ap_load_rosters(rosters_csv)
                games = ap_load_player_games(players_csv)
                metrics: List[Any] = []  # type: ignore[name-defined]
                for name, glist in games.items():
                    team = ownership.get(name.lower(), "Free Agent")
                    m = ap_compute_metrics(name, team, glist)
                    metrics.append(m)
                annotated, cats = ap_tag_categories(metrics)
                self.after(0, lambda: self._show_analysis_window(annotated, cats, players_csv, rosters_csv))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Analyze Error", f"Failed to analyze: {e}"))
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _show_analysis_window(self, metrics: List[Any], cats: Dict[str, List[Any]], players_csv: str, rosters_csv: str) -> None:
        """Display analyzed player metrics in a new window with a table and summaries."""
        win = tk.Toplevel(self)
        win.title("Analysis Results")
        win.geometry("980x560")
        win.minsize(860, 460)

        # Header
        info = ttk.Frame(win)
        info.pack(fill="x", padx=10, pady=(10, 6))
        ttk.Label(info, text=f"Players: {len(metrics)}").pack(side="left")
        ttk.Label(info, text=f"  |  Players CSV: {os.path.basename(players_csv)}").pack(side="left", padx=(10, 0))
        ttk.Label(info, text=f"  |  Rosters CSV: {os.path.basename(rosters_csv)}").pack(side="left", padx=(10, 0))

        # Table area
        table_frame = ttk.Frame(win)
        table_frame.pack(fill="both", expand=True, padx=10, pady=6)
        columns = (
            "player_name",
            "team",
            "games",
            "total_points",
            "expected_points",
            "avg_points",
            "recent_avg",
            "stdev",
            "ratio",
            "delta",
            "category",
        )
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        headers = {
            "player_name": "Player",
            "team": "Team",
            "games": "Games",
            "total_points": "Total",
            "expected_points": "Expected",
            "avg_points": "Avg",
            "recent_avg": "Recent Avg",
            "stdev": "Stdev",
            "ratio": "Ratio",
            "delta": "Delta",
            "category": "Category",
        }
        widths = {
            "player_name": 200,
            "team": 170,
            "games": 60,
            "total_points": 90,
            "expected_points": 100,
            "avg_points": 80,
            "recent_avg": 90,
            "stdev": 80,
            "ratio": 70,
            "delta": 80,
            "category": 110,
        }
        for key in columns:
            tree.heading(key, text=headers[key])
            tree.column(key, width=widths[key], anchor="w")

        def cat_order(cat: str) -> int:
            if not cat:
                return 3
            c = cat.lower()
            if "waiver" in c:
                return 0
            if "buy-low" in c:
                return 1
            if "sell-high" in c:
                return 2
            return 3

        disp = sorted(metrics, key=lambda m: (cat_order(m.category), -float(m.ratio or 0)))
        for m in disp:
            ratio_val = round(m.ratio, 3) if m.total_expected > 0 else ""
            tree.insert(
                "",
                "end",
                values=(
                    m.name,
                    m.team or "Free Agent",
                    m.games,
                    round(m.total_actual, 3),
                    round(m.total_expected, 3),
                    round(m.avg_actual, 3),
                    round(m.recent_avg, 3),
                    round(m.stdev_actual, 3),
                    ratio_val,
                    round(m.delta, 3),
                    m.category,
                ),
            )

        # Top categories summary
        cats_frame = ttk.LabelFrame(win, text="Top Targets")
        cats_frame.pack(fill="x", padx=10, pady=(0, 10))

        def list_cat(label: str, key: str) -> None:
            items = cats.get(key, []) or []
            if key == "waiver":
                text = ", ".join([f"{m.name} ({round(m.recent_avg,1)} ppg)" for m in items]) or "(none)"
            else:
                # show ratio %
                text = ", ".join([f"{m.name} ({round(m.ratio*100,1)}%)" for m in items]) or "(none)"
            row = ttk.Frame(cats_frame)
            row.pack(fill="x", padx=8, pady=2)
            ttk.Label(row, text=f"{label}:", width=20).pack(side="left")
            ttk.Label(row, text=text).pack(side="left")

        list_cat("Waiver Targets", "waiver")
        list_cat("Buy-Low Targets", "buy_low")
        list_cat("Sell-High Targets", "sell_high")


def main() -> None:
    app = ConfigGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
