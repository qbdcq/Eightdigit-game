"""
八数码游戏 - GUI / 棋盘交互 / 计时模块
依赖：项目现有 board.py
运行：python gui.py

职责边界：
1. 展示 3×3 棋盘与游戏信息
2. 处理玩家点击和合法移动
3. 统计玩家移动步数
4. 负责计时、完成状态和基础游戏控制
不包含数据库、排行榜、存档和 A* 算法。
"""
#2026 10/30 hyh第一次修改  添加本文件
import time
import tkinter as tk
from tkinter import messagebox

from board import Board


class PuzzleGUI(tk.Tk):
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

        self.title("NOVA  |  8 PUZZLE")
        self.geometry("920x760")
        self.minsize(820, 700)
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

        self.tile_rects = []
        self._build_interface()
        self._draw_board()
        self._refresh_stats()
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
        frame = tk.Frame(
            parent, bg=bg or self.PANEL,
            padx=padx, pady=pady,
            highlightthickness=1,
            highlightbackground="#263451"
        )
        return frame

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
            font=("Arial", 20, "bold"),
            fg=self.TEXT, bg=self.BG
        ).pack(anchor="w")
        tk.Label(
            title_box, text="THE CLASSIC 8-PUZZLE CHALLENGE",
            font=("Arial", 8, "bold"),
            fg=self.MUTED, bg=self.BG
        ).pack(anchor="w", pady=(3, 0))

        self.status_badge = tk.Label(
            top, text="●  READY TO PLAY",
            font=("Arial", 9, "bold"),
            fg=self.SUCCESS, bg="#142B35",
            padx=13, pady=8
        )
        self.status_badge.pack(side="right", anchor="center")

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
            board_heading, text="PUZZLE BOARD",
            font=("Arial", 11, "bold"),
            fg=self.TEXT, bg=self.BG
        ).pack(side="left")

        tk.Label(
            board_heading, text="3 × 3  GRID",
            font=("Arial", 9),
            fg=self.MUTED, bg=self.BG
        ).pack(side="right")

        # 棋盘 Canvas
        self.board_canvas = tk.Canvas(
            left, width=500, height=500,
            bg=self.PANEL, highlightthickness=1,
            highlightbackground="#263451"
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
        self.hint_label.pack(pady=(14, 0))

        # 右侧：数据卡片
        tk.Label(
            right, text="YOUR SESSION",
            font=("Arial", 10, "bold"),
            fg=self.MUTED, bg=self.BG
        ).pack(anchor="w", pady=(2, 12))

        stats = self._card(right, padx=16, pady=17)
        stats.pack(fill="x")

        self.steps_var = tk.StringVar(value="0")
        self.time_var = tk.StringVar(value="00:00")
        self.progress_var = tk.StringVar(value="0 / 8")

        self._stat_item(stats, "MOVES", self.steps_var, self.ACCENT)
        self._thin_divider(stats)
        self._stat_item(stats, "TIME ELAPSED", self.time_var, self.TEXT)
        self._thin_divider(stats)
        self._stat_item(stats, "TILES IN PLACE", self.progress_var, self.SUCCESS)

        # 右侧：操作区
        tk.Label(
            right, text="GAME CONTROL",
            font=("Arial", 10, "bold"),
            fg=self.MUTED, bg=self.BG
        ).pack(anchor="w", pady=(22, 12))

        self._action_button(
            right, "＋   NEW GAME", self.new_game,
            self.ACCENT, "#102B3B"
        ).pack(fill="x", pady=5)

        self._action_button(
            right, "↺   RESTART", self.restart,
            "#D9DFFF", "#242B4B"
        ).pack(fill="x", pady=5)

        # 右侧：规则说明
        guide = self._card(right, padx=15, pady=15)
        guide.pack(fill="x", pady=(22, 0))

        tk.Label(
            guide, text="HOW TO PLAY",
            font=("Arial", 9, "bold"),
            fg=self.ACCENT, bg=self.PANEL
        ).pack(anchor="w", pady=(0, 9))

        instructions = (
            "01   Move adjacent tiles\n\n"
            "02   Arrange numbers 1–8\n\n"
            "03   Leave the last cell empty"
        )
        tk.Label(
            guide, text=instructions,
            font=("Arial", 9),
            fg=self.MUTED, bg=self.PANEL,
            justify="left", anchor="w"
        ).pack(anchor="w")

        # 底部状态栏
        footer = tk.Frame(outer, bg=self.BG)
        footer.pack(fill="x", pady=(18, 0))

        tk.Label(
            footer, text="NOVA PUZZLE  •  DESKTOP EDITION",
            font=("Arial", 8, "bold"),
            fg="#5F6F8E", bg=self.BG
        ).pack(side="left")

        tk.Label(
            footer, text="MADE WITH PYTHON",
            font=("Arial", 8),
            fg="#5F6F8E", bg=self.BG
        ).pack(side="right")

    def _stat_item(self, parent, label, variable, color):
        block = tk.Frame(parent, bg=self.PANEL)
        block.pack(fill="x", pady=7)

        tk.Label(
            block, text=label,
            font=("Arial", 8, "bold"),
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
            font=("Arial", 10, "bold"),
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
                text="✓  COMPLETED",
                fg=self.SUCCESS, bg="#142F2C"
            )
        elif self.steps == 0:
            self.status_badge.configure(
                text="●  READY TO PLAY",
                fg=self.SUCCESS, bg="#142B35"
            )
        else:
            self.status_badge.configure(
                text="●  IN PROGRESS",
                fg=self.ACCENT, bg="#142B42"
            )

    def new_game(self):
        self.board.shuffle_from_goal(40)
        self.initial_state = self.board.state
        self.steps = 0
        self.finished = False
        self._reset_timer()
        self.hint_label.configure(
            text="新挑战已生成！移动数字方块开始游戏。",
            fg=self.ACCENT
        )
        self._draw_board()
        self._refresh_stats()

    def restart(self):
        self.board.reset(self.initial_state)
        self.steps = 0
        self.finished = False
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
        self._draw_board()
        self._refresh_stats()
        messagebox.showinfo(
            "PUZZLE COMPLETED",
            f"挑战成功！\n\n步数：{self.steps}\n用时：{self.time_var.get()}"
        )


if __name__ == "__main__":
    app = PuzzleGUI()
    app.mainloop()
