"""八数码棋盘的状态与移动规则。0 代表空格。"""

import random


class Board:
    GOAL = (1, 2, 3, 4, 5, 6, 7, 8, 0)

    def __init__(self, state=None):
        self.state = tuple(state or self.GOAL)

    def reset(self, state=None):
        self.state = tuple(state or self.GOAL)

    def is_solved(self):
        return self.state == self.GOAL

    def movable_indexes(self):
        """返回可移动到空格位置的数字下标。"""
        blank = self.state.index(0)
        row, col = divmod(blank, 3)
        indexes = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = row + dr, col + dc
            if 0 <= nr < 3 and 0 <= nc < 3:
                indexes.append(nr * 3 + nc)
        return indexes

    def move(self, index):
        """移动指定位置的数字；成功返回 True。"""
        if index not in self.movable_indexes():
            return False
        values = list(self.state)
        blank = values.index(0)
        values[blank], values[index] = values[index], values[blank]
        self.state = tuple(values)
        return True

    def shuffle_from_goal(self, moves=40):
        """从终局连续进行合法移动，因此生成的局面一定可解。"""
        self.reset()
        previous_blank = None
        for _ in range(moves):
            choices = self.movable_indexes()
            # 尽量不立即走回上一步，避免题目过于简单。
            if previous_blank in choices and len(choices) > 1:
                choices.remove(previous_blank)
            old_blank = self.state.index(0)
            self.move(random.choice(choices))
            previous_blank = old_blank

