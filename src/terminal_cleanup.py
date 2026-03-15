#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ctypes
from dataclasses import dataclass
import os
import subprocess
import sys
import textwrap

if os.name == "nt":
    from ctypes import wintypes

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * wintypes.MAX_PATH),
        ]

    _KERNEL32 = ctypes.windll.kernel32
    _KERNEL32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _KERNEL32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _KERNEL32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _KERNEL32.Process32FirstW.restype = wintypes.BOOL
    _KERNEL32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _KERNEL32.Process32NextW.restype = wintypes.BOOL
    _KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
    _KERNEL32.CloseHandle.restype = wintypes.BOOL
else:
    PROCESSENTRY32W = None
    _KERNEL32 = None
    TH32CS_SNAPPROCESS = 0
    INVALID_HANDLE_VALUE = None


_SHELL_PROCESS_NAMES = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "pwsh-preview.exe",
}
_TERMINAL_HOST_NAMES = {
    "windowsterminal.exe",
    "wt.exe",
}
_HELPER_TIMEOUT_MS = 30000
_HELPER_SCRIPT = textwrap.dedent(
    f"""
    import ctypes
    import subprocess
    import sys

    SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0

    def wait_for_exit(pid):
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return True
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(handle, {_HELPER_TIMEOUT_MS}) == WAIT_OBJECT_0
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    if wait_for_exit(int(sys.argv[1])):
        subprocess.run(
            ["taskkill", "/PID", sys.argv[2], "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    """
).strip()


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    parent_pid: int
    name: str


def _normalize_process_name(name):
    return os.path.basename(name or "").lower()


def _snapshot_process_map():
    """Windows のプロセス一覧を pid -> ProcessInfo で返す"""
    if os.name != "nt":
        return {}

    snapshot = _KERNEL32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot in (0, INVALID_HANDLE_VALUE):
        return {}

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    process_map = {}

    try:
        has_entry = _KERNEL32.Process32FirstW(snapshot, ctypes.byref(entry))
        while has_entry:
            process_map[int(entry.th32ProcessID)] = ProcessInfo(
                pid=int(entry.th32ProcessID),
                parent_pid=int(entry.th32ParentProcessID),
                name=entry.szExeFile,
            )
            has_entry = _KERNEL32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        _KERNEL32.CloseHandle(snapshot)

    return process_map


def _collect_ancestor_chain(process_map, current_pid):
    """現在プロセスの親チェーンを近い順で返す"""
    chain = []
    seen = {current_pid}
    next_pid = current_pid

    while True:
        current = process_map.get(next_pid)
        if current is None or current.parent_pid <= 0 or current.parent_pid in seen:
            return chain

        parent = process_map.get(current.parent_pid)
        if parent is None:
            return chain

        chain.append(parent)
        seen.add(parent.pid)
        next_pid = parent.pid


def _select_launch_terminal_shell_pid(process_map, current_pid):
    """起動元として閉じるべき最も外側のシェル pid を返す"""
    shell_pid = None

    for ancestor in _collect_ancestor_chain(process_map, current_pid):
        normalized_name = _normalize_process_name(ancestor.name)
        if normalized_name in _TERMINAL_HOST_NAMES:
            break
        if normalized_name in _SHELL_PROCESS_NAMES:
            shell_pid = ancestor.pid

    return shell_pid


def find_launch_terminal_shell_pid(current_pid=None, process_map=None):
    """現在プロセスを起動したターミナルシェル pid を返す"""
    if os.name != "nt":
        return None

    current_pid = current_pid or os.getpid()
    process_map = process_map if process_map is not None else _snapshot_process_map()
    return _select_launch_terminal_shell_pid(process_map, current_pid)


def _build_helper_command(current_pid, shell_pid):
    return [sys.executable, "-c", _HELPER_SCRIPT, str(current_pid), str(shell_pid)]


def _build_creation_flags():
    flags = 0
    flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return flags


def schedule_launch_terminal_close(current_pid=None, shell_pid=None, process_map=None):
    """アプリ終了後に起動元ターミナルを閉じる helper を起動する"""
    if os.name != "nt":
        return False

    current_pid = current_pid or os.getpid()
    shell_pid = shell_pid or find_launch_terminal_shell_pid(
        current_pid=current_pid,
        process_map=process_map,
    )
    if not shell_pid or shell_pid == current_pid:
        return False

    subprocess.Popen(
        _build_helper_command(current_pid, shell_pid),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=_build_creation_flags(),
    )
    return True
