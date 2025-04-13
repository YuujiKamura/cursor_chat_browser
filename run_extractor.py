#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cursor Chat Data Extractor - ランナースクリプト
"""

import sys
from pathlib import Path

# 現在のディレクトリをPythonパスに追加
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# モジュールのインポート
try:
    from src.extractor.cursor_data_extractor import main
    print("モジュールをインポートしました。実行を開始します...")
    main()
except ImportError as e:
    print(f"モジュールのインポートに失敗しました: {e}")
    sys.exit(1)
except Exception as e:
    print(f"実行中にエラーが発生しました: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 