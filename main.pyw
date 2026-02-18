#!/usr/bin/env pythonw
# -*- coding: utf-8 -*-
"""
コンソールウィンドウなしでアプリケーションを起動するランチャー。
ダブルクリックで起動すると、GUIのみが表示されます。
"""

import os
import sys

# pythonw.exe では stdout/stderr が None になるため、devnull にリダイレクト
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from main import main

main()
