#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cursor Chat Browser - エントリーポイント

このスクリプトは以下の機能を提供します:
1. チャットデータの抽出
2. ビューアの起動
"""

import sys
import os
import argparse

# Windows環境での文字化けを防ぐためにUTF-8出力に設定
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Cursor Chat Browser - Cursorのチャットデータを抽出・閲覧するツール")
    parser.add_argument("--extract", "-e", action="store_true", help="チャットデータを抽出する")
    parser.add_argument("--view", "-v", action="store_true", help="ビューアを起動する")
    parser.add_argument("--safe-mode", "-s", action="store_true", 
                        help="セーフモード：より保守的なデータベースアクセスを行い、ロック回避を強化します")
    parser.add_argument("--skip-active", "-a", action="store_true", 
                        help="アクティブなワークスペースのスキップを無効化します")
    
    args = parser.parse_args()
    
    # 環境変数を設定（他のモジュールで参照できるようにする）
    if args.safe_mode:
        os.environ["CURSOR_CHAT_SAFE_MODE"] = "1"
        print("🔒 セーフモードが有効です：データベースアクセスをより慎重に行います")
    
    if args.skip_active:
        os.environ["CURSOR_CHAT_SKIP_ACTIVE"] = "1"
        print("ℹ️ アクティブワークスペースのスキップが無効化されています")
    
    if args.extract:
        # 抽出モジュールをインポートして実行
        from src.extractor.cursor_data_extractor import main as extract_main
        extract_main()
    elif args.view:
        # ビューアモジュールをインポートして実行
        import cursor_chat_viewer_new
        cursor_chat_viewer_new.main()
    else:
        # デフォルトではビューアを起動
        print("💡 パラメータが指定されていません。ビューアを起動します。")
        print("   データを抽出するには --extract または -e オプションを指定してください。")
        import cursor_chat_viewer_new
        cursor_chat_viewer_new.main()

if __name__ == "__main__":
    main() 