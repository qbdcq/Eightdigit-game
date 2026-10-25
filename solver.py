"""使用曼哈顿距离启发函数的 A* 八数码求解器。"""

import heapq
import itertools


GOAL = (1, 2, 3, 4, 5, 6, 7, 8, 0)
GOAL_POSITIONS = {value: divmod(index, 3) for index, value in enumerate(GOAL)}


def manhattan_distance(state):
    total = 0
    for index, value in enumerate(state):
        if value == 0:
            continue
        row, col = divmod(index, 3)
        goal_row, goal_col = GOAL_POSITIONS[value]
        total += abs(row - goal_row) + abs(col - goal_col)
    return total


def neighbors(state):
    blank = state.index(0)
    row, col = divmod(blank, 3)
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = row + dr, col + dc
        if 0 <= nr < 3 and 0 <= nc < 3:
            target = nr * 3 + nc
            values = list(state)
            values[blank], values[target] = values[target], values[blank]
            yield tuple(values)


def solve(start):
    """返回 (状态路径, 扩展节点数)。无解时返回 (None, 0)。"""
    if not is_solvable(start):
        return None, 0

    counter = itertools.count()
    queue = [(manhattan_distance(start), 0, next(counter), start)]
    costs = {start: 0}
    parent = {start: None}
    expanded = 0

    while queue:
        _, cost, _, state = heapq.heappop(queue)
        if cost != costs.get(state):
            continue
        expanded += 1
        if state == GOAL:
            path = []
            while state is not None:
                path.append(state)
                state = parent[state]
            return list(reversed(path)), expanded

        for next_state in neighbors(state):
            next_cost = cost + 1
            if next_cost < costs.get(next_state, float("inf")):
                costs[next_state] = next_cost
                parent[next_state] = state
                priority = next_cost + manhattan_distance(next_state)
                heapq.heappush(queue, (priority, next_cost, next(counter), next_state))

    return None, expanded


def is_solvable(state):
    """3×3 八数码：逆序数为偶数时可解。"""
    numbers = [value for value in state if value != 0]
    inversions = sum(
        1
        for i in range(len(numbers))
        for j in range(i + 1, len(numbers))
        if numbers[i] > numbers[j]
    )
    return inversions % 2 == 0

