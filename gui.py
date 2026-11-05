"""
八数码游戏 - GUI / 棋盘交互 / 计时模块
依赖：项目现有 board.py、solver.py、Database-event/databaseevent.py
运行：python gui.py

职责边界：
1. 展示 3×3 棋盘与游戏信息
2. 处理玩家点击和合法移动
3. 统计玩家移动步数
4. 负责计时、完成状态和基础游戏控制
5. 提供登录、难度、存档、排行榜、提示和自动求解的界面入口
具体的数据存取与搜索逻辑由 databaseevent.solve 等模块实现，本文件只负责界面与调用。
"""

#2026 10/30 hyh第一次修改  添加本文件
import os
import sys
import time

# 修本机 Python 3.13 安装 bug：venv 继承的 tcl 路径是硬编码的 "D:/lib/tcl8.6"，
# 但实际 tcl/tk 装在 D:\tcl\tcl8.6 和 D:\tcl\tk8.6。
# 必须在 import tkinter 之前设好，否则 TclError: Can't find a usable init.tcl。
for _key, _candidate in (
    ("TCL_LIBRARY", [r"D:\tcl\tcl8.6", r"D:\lib\tcl8.6", r"D:\tcl"]),
    ("TK_LIBRARY", [r"D:\tcl\tk8.6", r"D:\lib\tk8.6", r"D:\tcl"]),
):
    if not os.environ.get(_key):
        for _c in _candidate:
            if os.path.isdir(_c) and (
                _key == "TCL_LIBRARY" and os.path.isfile(os.path.join(_c, "init.tcl"))
                or _key == "TK_LIBRARY" and os.path.isfile(os.path.join(_c, "tk.tcl"))
            ):
                os.environ[_key] = _c
                break

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from board import Board
from solver import is_solvable, solve


DB_DIRECTORY = Path(__file__).resolve().parent / "Database-event"


def _load_database():
    """让 databaseevent 模块可用。

    本机 Python 3.13 安装有 bug：site.getsitepackages() 返回的路径缺反斜杠，
    导致 pyodbc 所在的 D:\\Lib\\site-packages 默认不在 sys.path 里。
    PyCharm Run 还会清理 PATH 和 DLL 搜索路径，导致 pyodbc 报
    "DLL load failed while importing pyodbc: 参数错误"。

    这里用三层兜底：sys.path 补丁 + os.environ[PATH] 补丁 + 直接 Win32
    AddDllDirectory() 注册 DLL 搜索路径，不管 PyCharm 怎么清都能 import。
    """
    import os as _os

    # 0) Win32 原生 DLL 搜索路径注册（最底层，绕过 PATH）
    try:
        import ctypes as _ctypes
        _dll_dirs = [
            r"C:\Windows\System32",
            r"D:\Lib\site-packages",
            r"D:\DLLs",
            r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn",
        ]
        for d in _dll_dirs:
            if Path(d).exists():
                _ctypes.windll.kernel32.AddDllDirectory(d)
    except Exception:
        pass

    # 1) 确保 PATH 里有 Windows ODBC 相关目录（PyCharm Run 默认会清掉它们）
    _odbc_dirs = [
        r"C:\Windows\System32",
        r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn",
        r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\130\Tools\Binn",
        r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\110\Tools\Binn",
        r"C:\Program Files (x86)\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn",
    ]
    _path = _os.environ.get("PATH", "")
    for d in _odbc_dirs:
        if Path(d).exists() and d not in _path:
            _os.environ["PATH"] = d + ";" + _path
            _path = _os.environ["PATH"]

    # 2) databaseevent 目录（带连字符，Python 默认不会把它当包找）
    db_dir = str(DB_DIRECTORY)
    if db_dir not in sys.path:
        sys.path.insert(0, db_dir)

    # 3) pyodbc 所在的 site-packages（修 Python 安装路径 bug）
    site_pkg = r"D:\Lib\site-packages"
    if Path(site_pkg).exists() and site_pkg not in sys.path:
        sys.path.insert(0, site_pkg)

    # 4) 兜底：site 模块的候选路径里找第一个存在的
    try:
        import site as _site
        for getter in (_site.getsitepackages, _site.getusersitepackages):
            try:
                p = getter()
                candidates = [p] if isinstance(p, str) else list(p)
                for c in candidates:
                    if c and Path(c).exists() and c not in sys.path:
                        sys.path.insert(0, c)
            except Exception:
                pass
    except Exception:
        pass

    try:
        import pyodbc  # noqa: F401
    except Exception as exc:
        print(f"[gui] pyodbc 不可用: {exc}", file=sys.stderr)
        return None

    try:
        import databaseevent
        return databaseevent
    except Exception as exc:
        print(f"[gui] databaseevent 不可用: {exc}", file=sys.stderr)
        return None


database = _load_database()


class PuzzleGUI(tk.Tk):
    # 难度对应的随机移动次数（从终局反向漫步，保证生成的题目可解）
    DIFFICULTY_STEPS = {"简单": 3, "普通": 5, "困难": 7}

    # ---------- 视觉主题 ----------
    BG = "#0B1020"
    PANEL = "#141D33"
    PANEL_LIGHT = "#1B2742"
    TILE = "#243451"
    TILE_HOVER = "#30496F"
    TILE_MOVABLE = "#244D70"
    TILE_EMPTY = "#10192B"
    ACCENT = "#62D6FF"
    ACCENT_2 = "#9B8CFF"
    TEXT = "#F3F6FF"
    MUTED = "#91A0BD"
    SUCCESS = "#55D6A7"
    DANGER = "#FF8294"

    def __init__(self):
        super().__init__()

        self.title("八数码游戏")
        self.geometry("920x800")
        self.minsize(820, 740)
        self.configure(bg=self.BG)
        self.resizable(True, True)

        self.board = Board()
        self.initial_state = self.board.state
        self.steps = 0
        self.finished = self.board.is_solved()

        # 计时状态：首次有效移动时开始。
        self.elapsed_before = 0.0
        self.started_at = None
        self.timer_running = False

        # 数据库与玩家会话状态（数据库不可用时仍可本地游玩）。
        self.db = database
        self.player_id = None
        self.player_nickname = None
        self.puzzle_id = None
        self.difficulty = "普通"
        self.difficulty_var = tk.StringVar(value=self.difficulty)
        self.difficulty_buttons = {}
        self.shuffle_steps = self.DIFFICULTY_STEPS[self.difficulty]
        self.nickname_var = tk.StringVar()

        # 提示 / 自动求解状态。
        self.hint_count = 0
        self.auto_solved = False
        self.solve_path = None
        self.solve_index = 0
        self.auto_playing = False
        self.auto_job = None

        self.tile_rects = []
        self._build_interface()
        self._draw_board()
        self._refresh_stats()
        self.new_game()
        self._tick_clock()

    # ---------- 基础绘图 ----------
    @staticmethod
    def _rounded_rect(canvas, x1, y1, x2, y2, radius=18, **kwargs):
        """使用平滑多边形绘制圆角矩形，避免依赖第三方 GUI 库。"""
        points = [
            x1 + radius, y1, x2 - radius, y1,
            x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2,
            x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius,
            x1, y1 + radius, x1, y1
        ]
        return canvas.create_polygon(
            points, smooth=True, splinesteps=24, **kwargs
        )

    def _card(self, parent, bg=None, padx=18, pady=16):
        return tk.Frame(
            parent, bg=bg or self.PANEL,
            padx=padx, pady=pady
        )

    # ---------- 界面布局 ----------
    def _build_interface(self):
        outer = tk.Frame(self, bg=self.BG)
        outer.pack(fill="both", expand=True, padx=34, pady=25)

        # 顶部品牌区域
        top = tk.Frame(outer, bg=self.BG)
        top.pack(fill="x", pady=(0, 22))

        brand = tk.Frame(top, bg=self.BG)
        brand.pack(side="left")

        logo = tk.Canvas(
            brand, width=48, height=48,
            bg=self.BG, highlightthickness=0
        )
        logo.pack(side="left", padx=(0, 13))
        self._rounded_rect(
            logo, 2, 2, 46, 46, 13,
            fill="#1D3152", outline="#34527B", width=1
        )
        logo.create_text(
            24, 24, text="8",
            fill=self.ACCENT, font=("Arial", 25, "bold")
        )

        title_box = tk.Frame(brand, bg=self.BG)
        title_box.pack(side="left", anchor="center")
        tk.Label(
            title_box, text="八数码游戏",
            font=("Microsoft YaHei", 20, "bold"),
            fg=self.TEXT, bg=self.BG
        ).pack(anchor="w")
        tk.Label(
            title_box, text="经典八数码挑战",
            font=("Microsoft YaHei", 9, "bold"),
            fg=self.MUTED, bg=self.BG
        ).pack(anchor="w", pady=(3, 0))

        self.status_badge = tk.Label(
            top, text="●  未开始",
            font=("Microsoft YaHei", 9, "bold"),
            fg=self.SUCCESS, bg="#142B35",
            padx=13, pady=8
        )
        self.status_badge.pack(side="right", anchor="center")

        # 玩家登录区域（位于状态徽标左侧）
        player_box = tk.Frame(top, bg=self.BG)
        player_box.pack(side="right", anchor="center", padx=(0, 14))

        tk.Label(
            player_box, text="昵称",
            font=("Microsoft YaHei", 9), fg=self.MUTED, bg=self.BG
        ).pack(side="left", padx=(0, 6))

        self.nickname_entry = tk.Entry(
            player_box, textvariable=self.nickname_var, width=11,
            font=("Microsoft YaHei", 10), bg=self.PANEL_LIGHT, fg=self.TEXT,
            insertbackground=self.TEXT, relief="flat", bd=0
        )
        self.nickname_entry.pack(side="left", ipady=6, padx=(0, 8))
        self.nickname_entry.bind("<Return>", lambda _e: self.login())

        tk.Button(
            player_box, text="登录", command=self.login,
            font=("Microsoft YaHei", 9, "bold"), fg=self.ACCENT,
            bg="#102B3B", activeforeground=self.ACCENT,
            activebackground="#102B3B", relief="flat", bd=0,
            padx=12, pady=7, cursor="hand2"
        ).pack(side="left")

        self.player_label = tk.Label(
            player_box, text="当前玩家：未登录",
            font=("Microsoft YaHei", 9), fg=self.MUTED, bg=self.BG
        )
        self.player_label.pack(side="left", padx=(10, 0))

        # 主体左右布局
        body = tk.Frame(outer, bg=self.BG)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=self.BG)
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(body, bg=self.BG, width=245)
        right.pack(side="right", fill="y", padx=(22, 0))
        right.pack_propagate(False)

        # 棋盘标题
        board_heading = tk.Frame(left, bg=self.BG)
        board_heading.pack(fill="x", pady=(0, 13))

        tk.Label(
            board_heading, text="棋盘",
            font=("Microsoft YaHei", 11, "bold"),
            fg=self.TEXT, bg=self.BG
        ).pack(side="left")

        tk.Label(
            board_heading, text="3 × 3  网格",
            font=("Microsoft YaHei", 9),
            fg=self.MUTED, bg=self.BG
        ).pack(side="right")

        # 棋盘 Canvas
        self.board_canvas = tk.Canvas(
            left, width=500, height=500,
            bg=self.PANEL, highlightthickness=0
        )
        self.board_canvas.pack(fill="both", expand=True)
        self.board_canvas.bind("<Configure>", self._on_board_resize)

        # 棋盘下方提示
        self.hint_label = tk.Label(
            left,
            text="选择与空白格相邻的数字方块进行移动",
            font=("Microsoft YaHei", 10),
            fg=self.MUTED, bg=self.BG
        )

        # 棋盘下方操作栏：存档 / 提示 / 求解 / 排行榜 / 手动输入
        actions = tk.Frame(left, bg=self.BG)
        actions.pack(fill="x", pady=(12, 0))

        for text, command, color in (
            ("保存", self.save_progress, self.ACCENT),
            ("读档", self.open_saves, "#D9DFFF"),
            ("提示", self.hint_step, self.SUCCESS),
            ("自动求解", self.auto_solve, self.ACCENT_2),
            ("排行榜", self.show_leaderboard, self.ACCENT),
            ("手动输入", self.open_manual_input, self.MUTED),
        ):
            self._small_button(actions, text, command, color).pack(
                side="left", expand=True, fill="x", padx=3
            )

        self.hint_label.pack(pady=(12, 0))

        # 右侧：数据卡片
        tk.Label(
            right, text="本局数据",
            font=("Microsoft YaHei", 10, "bold"),
            fg=self.MUTED, bg=self.BG
        ).pack(anchor="w", pady=(2, 12))

        stats = self._card(right, padx=16, pady=17)
        stats.pack(fill="x")

        self.steps_var = tk.StringVar(value="0")
        self.time_var = tk.StringVar(value="00:00")
        self.progress_var = tk.StringVar(value="0 / 8")

        self._stat_item(stats, "步数", self.steps_var, self.ACCENT)
        self._thin_divider(stats)
        self._stat_item(stats, "用时", self.time_var, self.TEXT)
        self._thin_divider(stats)
        self._stat_item(stats, "已归位方块", self.progress_var, self.SUCCESS)

        # 右侧：操作区
        tk.Label(
            right, text="游戏控制",
            font=("Microsoft YaHei", 10, "bold"),
            fg=self.MUTED, bg=self.BG
        ).pack(anchor="w", pady=(22, 12))

        # 难度选择：只影响下一局新游戏
        difficulty_row = tk.Frame(right, bg=self.BG)
        difficulty_row.pack(fill="x", pady=(0, 10))

        for name in self.DIFFICULTY_STEPS:
            button = tk.Button(
                difficulty_row, text=name,
                command=lambda n=name: self.set_difficulty(n),
                font=("Microsoft YaHei", 9, "bold"),
                relief="flat", bd=0, pady=8, cursor="hand2"
            )
            button.pack(side="left", expand=True, fill="x", padx=2)
            self.difficulty_buttons[name] = button
        self._refresh_difficulty_buttons()

        self._action_button(
            right, "＋  新游戏", self.new_game,
            self.ACCENT, "#102B3B"
        ).pack(fill="x", pady=5)

        self._action_button(
            right, "↺  重新开始", self.restart,
            "#D9DFFF", "#242B4B"
        ).pack(fill="x", pady=5)

        # 底部状态栏
        footer = tk.Frame(outer, bg=self.BG)
        footer.pack(fill="x", pady=(18, 0))

        tk.Label(
            footer, text="八数码 · 桌面版",
            font=("Microsoft YaHei", 8),
            fg="#5F6F8E", bg=self.BG
        ).pack(side="left")

        tk.Label(
            footer, text="使用 Python 制作",
            font=("Microsoft YaHei", 8),
            fg="#5F6F8E", bg=self.BG
        ).pack(side="right")

    def _stat_item(self, parent, label, variable, color):
        block = tk.Frame(parent, bg=self.PANEL)
        block.pack(fill="x", pady=7)

        tk.Label(
            block, text=label,
            font=("Microsoft YaHei", 9, "bold"),
            fg=self.MUTED, bg=self.PANEL
        ).pack(anchor="w")

        tk.Label(
            block, textvariable=variable,
            font=("Arial", 25, "bold"),
            fg=color, bg=self.PANEL
        ).pack(anchor="w", pady=(3, 0))

    def _thin_divider(self, parent):
        tk.Frame(parent, bg="#293752", height=1).pack(fill="x", pady=8)

    def _action_button(self, parent, text, command, fg, bg):
        button = tk.Button(
            parent, text=text, command=command,
            font=("Microsoft YaHei", 10, "bold"),
            fg=fg, bg=bg,
            activeforeground=fg, activebackground=bg,
            relief="flat", bd=0,
            padx=14, pady=13,
            cursor="hand2"
        )
        button.bind("<Enter>", lambda _e: button.configure(
            highlightthickness=1, highlightbackground=fg
        ))
        button.bind("<Leave>", lambda _e: button.configure(
            highlightthickness=0
        ))
        return button

    def _small_button(self, parent, text, command, fg):
        """棋盘下方操作栏使用的小尺寸按钮。"""
        button = tk.Button(
            parent, text=text, command=command,
            font=("Microsoft YaHei", 9, "bold"),
            fg=fg, bg="#182642",
            activeforeground=fg, activebackground="#22375C",
            relief="flat", bd=0,
            padx=8, pady=9,
            cursor="hand2"
        )
        button.bind("<Enter>", lambda _e: button.configure(
            highlightthickness=1, highlightbackground=fg
        ))
        button.bind("<Leave>", lambda _e: button.configure(
            highlightthickness=0
        ))
        return button

    # ---------- 棋盘绘制 ----------
    def _on_board_resize(self, _event):
        self._draw_board()

    def _draw_board(self):
        if not hasattr(self, "board_canvas"):
            return

        canvas = self.board_canvas
        canvas.delete("all")
        self.tile_rects.clear()

        width = max(canvas.winfo_width(), 300)
        height = max(canvas.winfo_height(), 300)
        size = min(width, height) - 34
        cell = size / 3
        start_x = (width - size) / 2
        start_y = (height - size) / 2

        movable = set(self.board.movable_indexes())

        for index, value in enumerate(self.board.state):
            row, col = divmod(index, 3)
            x1 = start_x + col * cell + 7
            y1 = start_y + row * cell + 7
            x2 = start_x + (col + 1) * cell - 7
            y2 = start_y + (row + 1) * cell - 7

            if value == 0:
                fill = self.TILE_EMPTY
                outline = "#263550"
            elif index in movable and not self.finished:
                fill = self.TILE_MOVABLE
                outline = "#4C91C5"
            else:
                fill = self.TILE
                outline = "#344867"

            # 方块阴影
            if value != 0:
                self._rounded_rect(
                    canvas, x1 + 2, y1 + 5, x2 + 2, y2 + 5, 17,
                    fill="#080D18", outline=""
                )

            tile_tag = f"tile_{index}"
            rect = self._rounded_rect(
                canvas, x1, y1, x2, y2, 17,
                fill=fill, outline=outline, width=2,
                tags=(tile_tag,)
            )

            if value != 0:
                canvas.create_text(
                    (x1 + x2) / 2, (y1 + y2) / 2,
                    text=str(value),
                    fill=self.TEXT,
                    font=("Arial", max(20, int(cell * 0.27)), "bold"),
                    tags=(tile_tag,)
                )
                # 方块背景和数字文字共用同一个点击标签。
                canvas.tag_bind(
                    tile_tag, "<Button-1>",
                    lambda event, i=index: self._on_tile_click(i)
                )
                canvas.tag_bind(
                    tile_tag, "<Enter>",
                    lambda event, i=index: self._hover_tile(i, True)
                )
                canvas.tag_bind(
                    tile_tag, "<Leave>",
                    lambda event, i=index: self._hover_tile(i, False)
                )

            self.tile_rects.append(rect)

    def _hover_tile(self, index, entering):
        if self.finished:
            return
        if index not in self.board.movable_indexes():
            return
        # 只改变当前可移动格的视觉反馈；鼠标离开后统一重绘。
        if entering:
            self.board_canvas.itemconfig(
                self.tile_rects[index], fill=self.TILE_HOVER
            )
        else:
            self._draw_board()

    def _on_tile_click(self, index):
        self.move_tile(index)

    # ---------- 棋盘交互 ----------
    def move_tile(self, index):
        if self.finished:
            return

        # 玩家在自动播放期间手动操作，视为干预：取消旧路径并恢复计时。
        if self.auto_playing:
            self._cancel_auto_play()
            self._start_timer()
            self.hint_label.configure(
                text="已取消自动求解，可继续手动操作", fg=self.MUTED
            )

        if not self.board.move(index):
            self.hint_label.configure(
                text="这一步不能移动：请选择与空白格相邻的数字",
                fg=self.DANGER
            )
            self.after(1300, self._restore_hint)
            return

        self._start_timer()
        self.steps += 1
        self._draw_board()
        self._refresh_stats()

        if self.board.is_solved():
            self._finish_game()

    def _restore_hint(self):
        if not self.finished:
            self.hint_label.configure(
                text="选择与空白格相邻的数字方块进行移动",
                fg=self.MUTED
            )

    # ---------- 计时器 ----------
    def _elapsed(self):
        total = self.elapsed_before
        if self.timer_running and self.started_at is not None:
            total += time.monotonic() - self.started_at
        return max(0, int(total))

    def _start_timer(self):
        if not self.timer_running and not self.finished:
            self.started_at = time.monotonic()
            self.timer_running = True

    def _stop_timer(self):
        if self.timer_running and self.started_at is not None:
            self.elapsed_before += time.monotonic() - self.started_at
        self.timer_running = False
        self.started_at = None

    def _reset_timer(self):
        self.elapsed_before = 0.0
        self.started_at = None
        self.timer_running = False

    def _tick_clock(self):
        self._refresh_time()
        self.after(200, self._tick_clock)

    def _refresh_time(self):
        total = self._elapsed()
        minutes, seconds = divmod(total, 60)
        self.time_var.set(f"{minutes:02d}:{seconds:02d}")

    # ---------- 状态与游戏控制 ----------
    def _refresh_stats(self):
        self.steps_var.set(str(self.steps))
        correct = sum(
            1 for i, value in enumerate(self.board.state)
            if value == i + 1
        )
        self.progress_var.set(f"{correct} / 8")
        self._refresh_time()

        if self.finished:
            self.status_badge.configure(
                text="✓  已完成",
                fg=self.SUCCESS, bg="#142F2C"
            )
        elif self.steps == 0:
            self.status_badge.configure(
                text="●  未开始",
                fg=self.SUCCESS, bg="#142B35"
            )
        else:
            self.status_badge.configure(
                text="●  进行中",
                fg=self.ACCENT, bg="#142B42"
            )

    def new_game(self):
        self._cancel_auto_play()
        self.difficulty = self.difficulty_var.get()
        self.shuffle_steps = self.DIFFICULTY_STEPS[self.difficulty]
        self.board.shuffle_from_goal(self.shuffle_steps)
        self.initial_state = self.board.state
        self.steps = 0
        self.finished = self.board.is_solved()
        self.hint_count = 0
        self.auto_solved = False
        self.puzzle_id = None
        self._reset_timer()
        self.hint_label.configure(
            text=f"新挑战已生成（{self.difficulty} · 随机 {self.shuffle_steps} 步），移动方块开始游戏。",
            fg=self.ACCENT
        )
        self._draw_board()
        self._refresh_stats()

    def restart(self):
        self._cancel_auto_play()
        self.board.reset(self.initial_state)
        self.steps = 0
        self.finished = self.board.is_solved()
        self.hint_count = 0
        self.auto_solved = False
        self._reset_timer()
        self.hint_label.configure(
            text="已恢复本局初始布局，计时和步数已重置。",
            fg=self.MUTED
        )
        self._draw_board()
        self._refresh_stats()

    def _finish_game(self):
        self.finished = True
        self._stop_timer()
        self._cancel_auto_play()
        self._draw_board()
        self._refresh_stats()
        self.hint_label.configure(
            text="挑战完成！", fg=self.SUCCESS
        )

        # 登录且有对应题目记录时，写入完成记录。
        self._ensure_puzzle()
        if self.player_id is not None and self.puzzle_id is not None:
            self._db_call(
                "add_game_record",
                self.player_id,
                self.puzzle_id,
                self.steps,
                self._elapsed(),
                self.hint_count,
                self.auto_solved,
                silent=True,
            )

        messagebox.showinfo(
            "挑战完成",
            f"挑战成功！\n\n步数：{self.steps}\n用时：{self.time_var.get()}"
            f"\n提示次数：{self.hint_count}"
            f"\n自动求解：{'是' if self.auto_solved else '否'}"
        )


    # ---------- 玩家登录与难度 ----------
    def login(self):
        nickname = self.nickname_var.get().strip()
        if not nickname:
            messagebox.showinfo("提示", "请先输入昵称。")
            return
        player_id = self._db_call("login_player", nickname)
        if player_id is None:
            return
        self.player_id = player_id
        self.player_nickname = nickname
        self.player_label.configure(
            text=f"当前玩家：{nickname}", fg=self.SUCCESS
        )
        # 登录后补建当前题目的数据库记录，便于后续保存与成绩上传。
        self._ensure_puzzle()
        self.hint_label.configure(
            text=f"欢迎回来，{nickname}！", fg=self.SUCCESS
        )

    def set_difficulty(self, name):
        if name not in self.DIFFICULTY_STEPS:
            return
        self.difficulty_var.set(name)
        self._refresh_difficulty_buttons()
        self.hint_label.configure(
            text=f"难度已设为「{name}」，将在下一局新游戏中生效。", fg=self.MUTED
        )

    def _refresh_difficulty_buttons(self):
        current = self.difficulty_var.get()
        for name, button in self.difficulty_buttons.items():
            selected = name == current
            button.configure(
                fg=self.ACCENT if selected else self.MUTED,
                bg="#102B3B" if selected else self.PANEL_LIGHT,
                activeforeground=self.ACCENT if selected else self.MUTED,
                activebackground="#102B3B" if selected else self.PANEL_LIGHT,
            )

    # ---------- 数据库调用封装 ----------
    def _db_call(self, function_name, *args, silent=False):
        """统一封装数据库调用：等待光标 + 异常兜底，失败返回 None。"""
        if self.db is None:
            if not silent:
                messagebox.showerror(
                    "数据库不可用",
                    "未能加载数据库模块。\n请确认已安装 pyodbc，"
                    "并配置好 ODBC Driver 18 for SQL Server。"
                )
            return None
        function = getattr(self.db, function_name)
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            return function(*args)
        except Exception as exc:
            if not silent:
                messagebox.showerror(
                    "数据库错误", f"{function_name} 执行失败：\n{exc}"
                )
            return None
        finally:
            self.configure(cursor="")

    def _ensure_puzzle(self):
        """确保当前局面在 Puzzles 表中存在记录，返回 puzzle_id。"""
        if self.puzzle_id is not None:
            return self.puzzle_id
        if self.player_id is None:
            return None
        self.puzzle_id = self._db_call(
            "create_puzzle",
            self.state_to_text(self.initial_state),
            self.difficulty,
            max(1, self.shuffle_steps),
            silent=True,
        )
        return self.puzzle_id

    @staticmethod
    def state_to_text(state):
        return "".join(str(value) for value in state)

    @staticmethod
    def text_to_state(text):
        return tuple(int(ch) for ch in text)

    @staticmethod
    def _format_seconds(total):
        total = int(total)
        return f"{total // 60:02d}:{total % 60:02d}"

    def _make_treeview(self, parent, columns, height=10):
        """创建深色风格的表格，columns 为 (字段名, 表头, 宽度)。"""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Puzzle.Treeview",
            background=self.PANEL, fieldbackground=self.PANEL,
            foreground=self.TEXT, rowheight=26, borderwidth=0
        )
        style.configure(
            "Puzzle.Treeview.Heading",
            background=self.PANEL_LIGHT, foreground=self.ACCENT,
            relief="flat", font=("Microsoft YaHei", 9, "bold")
        )
        style.map("Puzzle.Treeview", background=[("selected", self.TILE_MOVABLE)])

        tree = ttk.Treeview(
            parent, columns=[item[0] for item in columns],
            show="headings", style="Puzzle.Treeview", height=height
        )
        for key, heading, width in columns:
            tree.heading(key, text=heading)
            tree.column(key, width=width, anchor="center", stretch=True)
        return tree

    # ---------- 存档 ----------
    def save_progress(self):
        if self.player_id is None:
            messagebox.showinfo("需要登录", "请先在顶部输入昵称并登录，再保存进度。")
            return
        if self._ensure_puzzle() is None:
            messagebox.showerror(
                "无法保存", "当前局面未能写入题目表，无法建立存档。"
            )
            return

        save_name = simpledialog.askstring(
            "保存存档", "请输入存档名称：",
            initialvalue=f"{self.difficulty}-{self.steps}步", parent=self
        )
        if not save_name:
            return

        save_id = self._db_call(
            "save_game",
            self.player_id,
            self.puzzle_id,
            save_name,
            self.state_to_text(self.initial_state),
            self.state_to_text(self.board.state),
            self.steps,
            self._elapsed(),
            self.hint_count,
        )
        if save_id is not None:
            messagebox.showinfo(
                "保存成功", f"存档「{save_name}」已保存（编号 {save_id}）。"
            )

    def open_saves(self):
        if self.player_id is None:
            messagebox.showinfo("需要登录", "请先在顶部登录，再查看存档。")
            return
        saves = self._db_call("list_saves", self.player_id)
        if saves is None:
            return
        if not saves:
            messagebox.showinfo("暂无存档", "当前玩家还没有存档记录。")
            return

        window = tk.Toplevel(self)
        window.title("我的存档")
        window.geometry("660x400")
        window.configure(bg=self.BG)
        window.transient(self)

        tk.Label(
            window, text=f"{self.player_nickname}  的存档",
            font=("Microsoft YaHei", 11, "bold"), fg=self.TEXT, bg=self.BG
        ).pack(anchor="w", padx=18, pady=(16, 10))

        tree = self._make_treeview(
            window,
            (
                ("name", "存档名称", 160),
                ("steps", "步数", 70),
                ("time", "用时", 80),
                ("hint", "提示次数", 80),
                ("saved", "保存时间", 190),
            ),
        )
        tree.pack(fill="both", expand=True, padx=18)

        for save in saves:
            tree.insert(
                "", "end",
                values=(
                    save["save_name"],
                    save["steps"],
                    self._format_seconds(save["elapsed_seconds"]),
                    save["hint_count"],
                    save["saved_at"],
                ),
            )

        def load_selected(_event=None):
            selection = tree.selection()
            if not selection:
                return
            save_name = tree.item(selection[0], "values")[0]
            window.destroy()
            self.load_save(save_name)

        tree.bind("<Double-1>", load_selected)

        tk.Button(
            window, text="读取选中存档", command=load_selected,
            font=("Microsoft YaHei", 9, "bold"), fg=self.ACCENT, bg="#102B3B",
            activeforeground=self.ACCENT, activebackground="#102B3B",
            relief="flat", bd=0, padx=16, pady=9, cursor="hand2"
        ).pack(pady=(12, 16))

    def load_save(self, save_name):
        record = self._db_call("load_save", self.player_id, save_name)
        if record is None:
            return
        self._apply_loaded_save(record)

    def _apply_loaded_save(self, record):
        self._cancel_auto_play()
        self.board.reset(self.text_to_state(record["current_state"]))
        self.initial_state = self.text_to_state(record["initial_state"])
        self.steps = int(record["steps"])
        self.hint_count = int(record["hint_count"])
        self.elapsed_before = float(record["elapsed_seconds"])
        self.started_at = None
        self.timer_running = False
        self.puzzle_id = int(record["puzzle_id"])
        self.auto_solved = False
        self.finished = self.board.is_solved()
        self.hint_label.configure(
            text=f"已读取存档「{record['save_name']}」，可继续游戏。",
            fg=self.SUCCESS
        )
        self._draw_board()
        self._refresh_stats()

    # ---------- 排行榜 ----------
    def show_leaderboard(self):
        if self.db is None:
            messagebox.showerror(
                "数据库不可用", "未能加载数据库模块，无法查询排行榜。"
            )
            return

        window = tk.Toplevel(self)
        window.title("排行榜")
        window.geometry("700x430")
        window.configure(bg=self.BG)
        window.transient(self)

        header = tk.Frame(window, bg=self.BG)
        header.pack(fill="x", padx=18, pady=(16, 10))

        tk.Label(
            header, text="排行榜",
            font=("Microsoft YaHei", 13, "bold"), fg=self.TEXT, bg=self.BG
        ).pack(side="left")

        filter_var = tk.StringVar(value="全部")
        combo = ttk.Combobox(
            header, textvariable=filter_var,
            values=("全部", "简单", "普通", "困难"),
            state="readonly", width=8, font=("Microsoft YaHei", 9)
        )
        combo.pack(side="right")

        tree = self._make_treeview(
            window,
            (
                ("rank", "排名", 60),
                ("nick", "玩家", 120),
                ("diff", "难度", 80),
                ("steps", "步数", 70),
                ("time", "用时", 80),
                ("hint", "提示", 70),
            ),
        )
        tree.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        def refresh(_event=None):
            difficulty = None if filter_var.get() == "全部" else filter_var.get()
            rows = self._db_call("get_leaderboard", 20, difficulty) or []
            tree.delete(*tree.get_children())
            for rank, row in enumerate(rows, start=1):
                tree.insert(
                    "", "end",
                    values=(
                        rank,
                        row["nickname"],
                        row["difficulty"],
                        row["steps"],
                        self._format_seconds(row["duration_seconds"]),
                        row["hint_count"],
                    ),
                )

        combo.bind("<<ComboboxSelected>>", refresh)
        refresh()

    # ---------- 提示与自动求解 ----------
    def hint_step(self):
        if self.finished:
            return
        self._cancel_auto_play()

        path, expanded = solve(self.board.state)
        if path is None:
            messagebox.showinfo("无法提示", "当前局面不可解。")
            return
        if len(path) <= 1:
            return

        self.hint_count += 1
        self.solve_path = path
        self.solve_index = 0
        target_index = path[1].index(0)
        self._highlight_tile(target_index)
        self.hint_label.configure(
            text=(f"提示：移动 {self.board.state[target_index]} 号方块"
                  f" · 剩余 {len(path) - 1} 步 · 搜索节点 {expanded}"),
            fg=self.SUCCESS
        )

    def auto_solve(self):
        if self.finished or self.auto_playing:
            return

        path, expanded = solve(self.board.state)
        if path is None:
            messagebox.showinfo("无解", "当前局面不可解，无法自动求解。")
            return
        if len(path) <= 1:
            return

        self.auto_solved = True
        self.solve_path = path
        self.solve_index = 0
        self.auto_playing = True
        self._stop_timer()  # 自动播放期间暂停计时
        self.hint_label.configure(
            text=f"自动求解：共 {len(path) - 1} 步 · 搜索节点 {expanded}",
            fg=self.ACCENT_2
        )
        self._auto_step()

    def _auto_step(self):
        self.auto_job = None
        if not self.auto_playing or not self.solve_path:
            return
        if self.solve_index >= len(self.solve_path) - 1:
            self.auto_playing = False
            return

        self.solve_index += 1
        self.board.reset(self.solve_path[self.solve_index])
        self.steps += 1
        self._draw_board()
        self._refresh_stats()

        if self.board.is_solved():
            self._finish_game()
            return
        self.auto_job = self.after(450, self._auto_step)

    def _cancel_auto_play(self):
        if self.auto_job is not None:
            try:
                self.after_cancel(self.auto_job)
            except tk.TclError:
                pass
        self.auto_job = None
        self.auto_playing = False
        self.solve_path = None
        self.solve_index = 0

    def _highlight_tile(self, index):
        if self.finished or index >= len(self.tile_rects):
            return
        self.board_canvas.itemconfig(self.tile_rects[index], fill=self.ACCENT)
        self.after(1300, self._draw_board)

    # ---------- 手动输入局面 ----------
    def open_manual_input(self):
        window = tk.Toplevel(self)
        window.title("手动输入局面")
        window.configure(bg=self.BG)
        window.transient(self)
        window.resizable(False, False)

        tk.Label(
            window, text="按 3×3 顺序填写 0~8（0 表示空格）",
            font=("Microsoft YaHei", 10), fg=self.MUTED, bg=self.BG
        ).grid(row=0, column=0, columnspan=3, pady=(16, 12), padx=18)

        grid = tk.Frame(window, bg=self.BG)
        grid.grid(row=1, column=0, columnspan=3, padx=18)

        entries = []
        for index in range(9):
            entry = tk.Entry(
                grid, width=3, justify="center",
                font=("Arial", 18, "bold"),
                bg=self.PANEL_LIGHT, fg=self.TEXT,
                insertbackground=self.TEXT, relief="flat", bd=0
            )
            entry.grid(row=index // 3, column=index % 3, padx=5, pady=5, ipady=6)
            entries.append(entry)
        entries[0].focus_set()

        message = tk.Label(
            window, text="", font=("Microsoft YaHei", 9),
            fg=self.DANGER, bg=self.BG
        )
        message.grid(row=2, column=0, columnspan=3, pady=(8, 0), padx=18)

        def apply_state():
            try:
                values = [int(entry.get().strip()) for entry in entries]
            except ValueError:
                message.configure(text="每个格子只能填写 0~8 的数字。")
                return
            if sorted(values) != list(range(9)):
                message.configure(text="必须恰好包含 0~8，且每个数字只出现一次。")
                return
            if not is_solvable(tuple(values)):
                message.configure(text="该局面逆序数为奇数，无法还原到目标状态。")
                return
            self._apply_manual_state(tuple(values))
            window.destroy()

        tk.Button(
            window, text="载入局面", command=apply_state,
            font=("Microsoft YaHei", 9, "bold"), fg=self.ACCENT, bg="#102B3B",
            activeforeground=self.ACCENT, activebackground="#102B3B",
            relief="flat", bd=0, padx=16, pady=9, cursor="hand2"
        ).grid(row=3, column=0, columnspan=3, pady=(12, 16))

    def _apply_manual_state(self, state):
        self._cancel_auto_play()
        self.board.reset(state)
        self.initial_state = state
        self.steps = 0
        self.hint_count = 0
        self.auto_solved = False
        self.puzzle_id = None
        self.shuffle_steps = 1
        self.finished = self.board.is_solved()
        self._reset_timer()
        self.hint_label.configure(
            text="已载入手动局面，可开始移动。", fg=self.ACCENT
        )
        self._draw_board()
        self._refresh_stats()


if __name__ == "__main__":
    app = PuzzleGUI()
    app.mainloop()
