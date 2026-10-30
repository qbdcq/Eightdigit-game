"""八数码项目的 SQL Server 数据访问函数。

本模块只负责数据库读写，不依赖 Tkinter、棋盘或 A* 模块。

运行前安装驱动：pip install pyodbc
默认使用 Windows 身份验证连接本机 SQL Server。若连接参数不同，请设置
环境变量 DB_CONNECTION_STRING，例如：
DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=EightPuzzleDB;
UID=sa;PWD=你的密码;TrustServerCertificate=yes;
"""

import os
from typing import Any

import pyodbc


DEFAULT_CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=EightPuzzleDB;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def get_connection() -> pyodbc.Connection:
    """创建一个 SQL Server 连接。"""
    connection_string = os.getenv("DB_CONNECTION_STRING", DEFAULT_CONNECTION_STRING)
    return pyodbc.connect(connection_string)


def _row_to_dict(cursor: pyodbc.Cursor, row: Any) -> dict[str, Any]:
    """将 pyodbc 行对象转换成普通字典。"""
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def _check_state(state: str) -> None:
    """校验 3×3 棋盘字符串，例如 '123456780'。"""
    if len(state) != 9 or set(state) != set("012345678"):
        raise ValueError("棋盘状态必须是恰好包含 0~8 的 9 位字符串，例如 '123456780'。")


# -------------------- Players --------------------

def create_player(nickname: str) -> int:
    """创建玩家，返回新玩家 id；昵称重复时由 SQL Server 抛出异常。"""
    nickname = nickname.strip()
    if not nickname:
        raise ValueError("昵称不能为空。")

    sql = "INSERT INTO dbo.Players (nickname) OUTPUT INSERTED.id VALUES (?);"
    connection = get_connection()
    try:
        cursor = connection.cursor()
        player_id = cursor.execute(sql, nickname).fetchone()[0]
        connection.commit()
        return player_id
    finally:
        connection.close()


def get_player_by_nickname(nickname: str) -> dict[str, Any] | None:
    """按昵称查询玩家；不存在时返回 None。"""
    sql = "SELECT id, nickname FROM dbo.Players WHERE nickname = ?;"
    connection = get_connection()
    try:
        cursor = connection.cursor()
        row = cursor.execute(sql, nickname.strip()).fetchone()
        return _row_to_dict(cursor, row) if row else None
    finally:
        connection.close()


def get_or_create_player(nickname: str) -> int:
    """获取已有玩家 id；不存在时创建。"""
    player = get_player_by_nickname(nickname)
    return player["id"] if player else create_player(nickname)


def login_player(nickname: str) -> int:
    """登录或注册玩家，返回后续游戏流程所需的 player_id。"""
    return get_or_create_player(nickname)


def list_players() -> list[dict[str, Any]]:
    """按 id 返回全部玩家。"""
    sql = "SELECT id, nickname FROM dbo.Players ORDER BY id;"
    connection = get_connection()
    try:
        cursor = connection.cursor()
        rows = cursor.execute(sql).fetchall()
        return [_row_to_dict(cursor, row) for row in rows]
    finally:
        connection.close()


# -------------------- Puzzles --------------------

def create_puzzle(initial_state: str, difficulty: str, shuffle_steps: int) -> int:
    """保存新生成的题目，返回 puzzle id。"""
    _check_state(initial_state)
    if difficulty not in ("简单", "普通", "困难"):
        raise ValueError("难度只能是：简单、普通、困难。")
    if shuffle_steps <= 0:
        raise ValueError("随机移动次数必须大于 0。")

    sql = """
        INSERT INTO dbo.Puzzles (initial_state, difficulty, shuffle_steps)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?);
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        puzzle_id = cursor.execute(sql, initial_state, difficulty, shuffle_steps).fetchone()[0]
        connection.commit()
        return puzzle_id
    finally:
        connection.close()


def get_puzzle(puzzle_id: int) -> dict[str, Any] | None:
    """按编号查询一个题目。"""
    sql = "SELECT * FROM dbo.Puzzles WHERE id = ?;"
    connection = get_connection()
    try:
        cursor = connection.cursor()
        row = cursor.execute(sql, puzzle_id).fetchone()
        return _row_to_dict(cursor, row) if row else None
    finally:
        connection.close()


# -------------------- GameSaves --------------------

def save_game(
    player_id: int,
    puzzle_id: int,
    save_name: str,
    initial_state: str,
    current_state: str,
    steps: int,
    elapsed_seconds: int,
    hint_count: int = 0,
) -> int:
    """新建或覆盖同一玩家的同名存档，返回存档 id。"""
    save_name = save_name.strip()
    if not save_name:
        raise ValueError("存档名称不能为空。")
    _check_state(initial_state)
    _check_state(current_state)
    if steps < 0 or elapsed_seconds < 0 or hint_count < 0:
        raise ValueError("步数、用时和提示次数不能小于 0。")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        # 先更新，若同名存档不存在再插入，避免同名存档重复。
        update_sql = """
            UPDATE dbo.GameSaves
            SET puzzle_id = ?, initial_state = ?, current_state = ?, steps = ?,
                elapsed_seconds = ?, hint_count = ?, saved_at = SYSDATETIME()
            WHERE player_id = ? AND save_name = ?;
        """
        cursor.execute(
            update_sql,
            puzzle_id, initial_state, current_state, steps,
            elapsed_seconds, hint_count, player_id, save_name,
        )
        if cursor.rowcount == 0:
            insert_sql = """
                INSERT INTO dbo.GameSaves
                    (player_id, puzzle_id, save_name, initial_state, current_state,
                     steps, elapsed_seconds, hint_count)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """
            save_id = cursor.execute(
                insert_sql,
                player_id, puzzle_id, save_name, initial_state, current_state,
                steps, elapsed_seconds, hint_count,
            ).fetchone()[0]
        else:
            save_id = cursor.execute(
                "SELECT id FROM dbo.GameSaves WHERE player_id = ? AND save_name = ?;",
                player_id, save_name,
            ).fetchone()[0]
        connection.commit()
        return save_id
    finally:
        connection.close()


def load_save(player_id: int, save_name: str = "默认存档") -> dict[str, Any] | None:
    """读取一个存档；没有该存档时返回 None。"""
    sql = """
        SELECT id, player_id, puzzle_id, save_name, initial_state, current_state,
               steps, elapsed_seconds, hint_count, saved_at
        FROM dbo.GameSaves
        WHERE player_id = ? AND save_name = ?;
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        row = cursor.execute(sql, player_id, save_name).fetchone()
        return _row_to_dict(cursor, row) if row else None
    finally:
        connection.close()


def list_saves(player_id: int) -> list[dict[str, Any]]:
    """查询某位玩家的全部存档摘要，按最近保存时间排序。"""
    sql = """
        SELECT id, puzzle_id, save_name, current_state, steps,
               elapsed_seconds, hint_count, saved_at
        FROM dbo.GameSaves
        WHERE player_id = ?
        ORDER BY saved_at DESC, id DESC;
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        rows = cursor.execute(sql, player_id).fetchall()
        return [_row_to_dict(cursor, row) for row in rows]
    finally:
        connection.close()


# -------------------- GameRecords / 排行榜 --------------------

def add_game_record(
    player_id: int,
    puzzle_id: int,
    steps: int,
    duration_seconds: int,
    hint_count: int = 0,
    auto_solved: bool = False,
) -> int:
    """新增一条已完成的游戏记录，返回记录 id。"""
    if steps < 0 or duration_seconds < 0 or hint_count < 0:
        raise ValueError("步数、用时和提示次数不能小于 0。")
    sql = """
        INSERT INTO dbo.GameRecords
            (player_id, puzzle_id, steps, duration_seconds, hint_count,
             auto_solved)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?);
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        record_id = cursor.execute(
            sql, player_id, puzzle_id, steps, duration_seconds,
            hint_count, auto_solved,
        ).fetchone()[0]
        connection.commit()
        return record_id
    finally:
        connection.close()


def get_leaderboard(
    limit: int = 10,
    difficulty: str | None = None,
) -> list[dict[str, Any]]:
    """查询手动通关排行榜，可按难度筛选。"""
    if limit <= 0:
        raise ValueError("排行榜数量必须大于 0。")
    if difficulty is not None and difficulty not in ("简单", "普通", "困难"):
        raise ValueError("难度只能是：简单、普通、困难。")

    sql = """
        SELECT TOP (?)
            p.nickname, pu.difficulty, r.steps, r.duration_seconds,
            r.hint_count, r.completed_at
        FROM dbo.GameRecords AS r
        INNER JOIN dbo.Players AS p ON p.id = r.player_id
        INNER JOIN dbo.Puzzles AS pu ON pu.id = r.puzzle_id
        WHERE r.auto_solved = 0
    """
    parameters: list[Any] = [limit]
    if difficulty is not None:
        sql += " AND pu.difficulty = ?"
        parameters.append(difficulty)
    sql += " ORDER BY r.steps, r.duration_seconds, r.hint_count, r.completed_at;"

    connection = get_connection()
    try:
        cursor = connection.cursor()
        rows = cursor.execute(sql, *parameters).fetchall()
        return [_row_to_dict(cursor, row) for row in rows]
    finally:
        connection.close()
