#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cursor Chat データ抽出ツール

このスクリプトはCursorのチャットデータとComposerデータを抽出し、
JSONファイルとして保存します。
"""

import os
import sys
from pathlib import Path

# モジュールへのパスを追加
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    from src.extractor.cursor_data_extractor import main
    main()
except ImportError as e:
    print(f"モジュールのインポートに失敗しました: {e}")
    sys.exit(1)
except Exception as e:
    print(f"実行中にエラーが発生しました: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 