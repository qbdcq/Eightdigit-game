"""八数码游戏入口：运行 python main.py。"""

import time
import tkinter as tk
from tkinter import messagebox

from board import Board
from solver import solve


class PuzzleApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("八数码益智游戏")
        self.resizable(False, False)
        self.board = Board()
        self.initial_state = self.board.state
        self.steps = 0
        self.start_time = time.time()
        self.solving = False

        self.info = tk.Label(self, font=("Microsoft YaHei", 12))
        self.info.pack(pady=(12, 5))

        self.board_frame = tk.Frame(self, padx=12, pady=8)
        self.board_frame.pack()
        self.tiles = []
        for index in range(9):
            button = tk.Button(
                self.board_frame, width=5, height=2,
                font=("Microsoft YaHei", 20, "bold"),
                command=lambda i=index: self.move_tile(i),
            )
            button.grid(row=index // 3, column=index % 3, padx=3, pady=3)
            self.tiles.append(button)

        controls = tk.Frame(self, pady=10)
        controls.pack()
        tk.Button(controls, text="新游戏", command=self.new_game).grid(row=0, column=0, padx=4)
        tk.Button(controls, text="重新开始", command=self.restart).grid(row=0, column=1, padx=4)
        tk.Button(controls, text="单步提示", command=self.hint).grid(row=0, column=2, padx=4)
        tk.Button(controls, text="自动求解", command=self.auto_solve).grid(row=0, column=3, padx=4)

        self.refresh()
        self.update_timer()

    def refresh(self):
        for index, value in enumerate(self.board.state):
            movable = index in self.board.movable_indexes()
            if value == 0:
                self.tiles[index].config(text="", state="disabled", bg="#eeeeee")
            else:
                self.tiles[index].config(
                    text=str(value),
                    state="normal" if movable and not self.solving else "disabled",
                    bg="#b9dcff" if movable else "#ffffff",
                )
        elapsed = int(time.time() - self.start_time)
        self.info.config(text=f"步数：{self.steps}    用时：{elapsed} 秒")

    def update_timer(self):
        if not self.solving:
            self.refresh()
        self.after(1000, self.update_timer)

    def move_tile(self, index):
        if self.board.move(index):
            self.steps += 1
            self.refresh()
            if self.board.is_solved():
                messagebox.showinfo("恭喜", f"你完成了游戏！\n步数：{self.steps}")

    def new_game(self):
        self.board.shuffle_from_goal(40)
        self.initial_state = self.board.state
        self.steps = 0
        self.start_time = time.time()
        self.refresh()

    def restart(self):
        self.board.reset(self.initial_state)
        self.steps = 0
        self.start_time = time.time()
        self.refresh()

    def hint(self):
        path, nodes = solve(self.board.state)
        if path is None:
            messagebox.showerror("无法求解", "当前局面无解。")
        elif len(path) == 1:
            messagebox.showinfo("提示", "已经完成！")
        else:
            next_state = path[1]
            moved = next_state[self.board.state.index(0)]
            messagebox.showinfo("单步提示", f"建议移动数字：{moved}\n剩余最短步数：{len(path) - 1}\n搜索节点：{nodes}")

    def auto_solve(self):
        path, nodes = solve(self.board.state)
        if path is None:
            messagebox.showerror("无法求解", "当前局面无解。")
            return
        self.solving = True
        messagebox.showinfo("自动求解", f"最短步数：{len(path) - 1}\n搜索节点：{nodes}")
        self.play_path(path, 0)

    def play_path(self, path, index):
        if index >= len(path):
            self.solving = False
            self.refresh()
            return
        self.board.reset(path[index])
        self.refresh()
        self.after(300, lambda: self.play_path(path, index + 1))


if __name__ == "__main__":
    app = PuzzleApp()
    app.mainloop()
