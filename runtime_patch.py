"""本机 Python、Tkinter 与 SQL Server ODBC 环境的兼容补丁。

此文件只处理运行环境，不应包含游戏或 GUI 业务逻辑。若其他电脑环境正常，
函数会静默跳过不存在的本机路径。
"""

import ctypes
import os
import site
import sys
from pathlib import Path


def _set_tcl_paths() -> None:
    """修复部分 Python 安装中 Tcl/Tk 路径错误的问题。"""
    candidates = (
        ("TCL_LIBRARY", (r"D:\tcl\tcl8.6", r"D:\lib\tcl8.6", r"D:\tcl"), "init.tcl"),
        ("TK_LIBRARY", (r"D:\tcl\tk8.6", r"D:\lib\tk8.6", r"D:\tcl"), "tk.tcl"),
    )
    for key, directories, required_file in candidates:
        if os.environ.get(key):
            continue
        for directory in directories:
            if (Path(directory) / required_file).is_file():
                os.environ[key] = directory
                break


def _add_dll_and_odbc_paths() -> None:
    """补充 Windows DLL、ODBC 客户端搜索路径。"""
    paths = (
        r"C:\Windows\System32",
        r"D:\Lib\site-packages",
        r"D:\DLLs",
        r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn",
        r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\130\Tools\Binn",
        r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\110\Tools\Binn",
        r"C:\Program Files (x86)\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn",
    )
    path_value = os.environ.get("PATH", "")
    for directory in paths:
        if not Path(directory).exists():
            continue
        if directory not in path_value:
            path_value = directory + ";" + path_value
        try:
            ctypes.windll.kernel32.AddDllDirectory(directory)
        except (AttributeError, OSError):
            pass
    os.environ["PATH"] = path_value


def _add_site_packages() -> None:
    """补充异常 Python 安装遗漏的 site-packages 路径。"""
    candidates = [r"D:\Lib\site-packages"]
    for getter in (site.getsitepackages, site.getusersitepackages):
        try:
            found = getter()
            candidates.extend([found] if isinstance(found, str) else found)
        except Exception:
            continue
    for directory in candidates:
        if directory and Path(directory).exists() and directory not in sys.path:
            sys.path.insert(0, directory)


def apply_runtime_patches() -> None:
    """在导入 tkinter、pyodbc 前调用一次。"""
    _set_tcl_paths()
    _add_dll_and_odbc_paths()
    _add_site_packages()
