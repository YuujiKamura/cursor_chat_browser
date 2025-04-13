#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cursor Chat データ抽出ツール v2

このスクリプトはCursorのチャット履歴をJSON形式で抽出します。
チャットはjsonディレクトリに保存されます。
"""

import os
import sys
import json
import time
import glob
import hashlib
import shutil
import argparse
from pathlib import Path
import platform
import io

# Windows環境での文字化けを防ぐためのUTF-8設定
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# クリップボードモジュールを利用可能な場合のみインポート
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False

# 重要な定数
VERSION = "2.0.2"
DEFAULT_CONFIG = {
    "active_workspaces": [],
    "excluded_paths": [],
    "excluded_patterns": [],
    "last_run": "",
    "extraction_count": 0
}

# 設定ファイルパス
CONFIG_FILE = Path.home() / ".cursor_chat_extractor.json"

# オプションフラグの取得
def parse_args():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(description="Cursor Chat データ抽出ツール")
    parser.add_argument("--safe-mode", action="store_true", help="セーフモード: 既知の問題を回避するための安全な実行")
    parser.add_argument("--skip-active", action="store_true", help="アクティブワークスペースのスキップを無効化")
    parser.add_argument("--test-mode", action="store_true", help="テストモード: テストデータを使用して実行")
    return parser.parse_args()

# 設定の読み込み/保存
def load_config():
    """設定ファイルを読み込む。存在しない場合はデフォルト設定を返す"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return DEFAULT_CONFIG.copy()
    except Exception as e:
        print(f"設定読み込みエラー: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """設定ファイルを保存する"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"設定保存エラー: {e}")

# ユーティリティ関数
def get_cursor_app_dir():
    """プラットフォームに応じたCursorアプリケーションディレクトリを取得する"""
    # テストモードの場合はテスト用のストレージディレクトリを使用
    if is_test_mode():
        test_path = os.environ.get("CURSOR_STORAGE_PATH")
        if test_path:
            return Path(test_path)
        
    system = platform.system()
    
    if system == "Windows":
        app_data = os.getenv("APPDATA")
        return Path(app_data) / "Cursor" if app_data else None
        
    elif system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Cursor"
        
    elif system == "Linux":
        return Path.home() / ".config" / "Cursor"
        
    return None

def is_safe_mode():
    """セーフモードかどうかを確認する"""
    args = parse_args()
    env_safe_mode = os.environ.get("CURSOR_CHAT_SAFE_MODE") == "1"
    return args.safe_mode or env_safe_mode

def skip_active_workspace():
    """アクティブワークスペースをスキップするかどうかを確認する"""
    args = parse_args()
    env_skip_active = os.environ.get("CURSOR_CHAT_SKIP_ACTIVE") != "1"  # デフォルトはスキップ
    return env_skip_active and not args.skip_active

def is_test_mode():
    """テストモードかどうかを確認する"""
    args = parse_args()
    return args.test_mode

def get_cursor_chat_dirs():
    """Cursorチャットディレクトリのリストを取得する"""
    cursor_dir = get_cursor_app_dir()
    if not cursor_dir:
        return []
    
    # テストモードの場合は直接そのディレクトリを使用
    if is_test_mode():
        chat_dirs = []
        # WorkspaceStateディレクトリを検索
        for workspace_dir in cursor_dir.glob("**/WorkspaceState"):
            if workspace_dir.is_dir():
                chat_dirs.append(workspace_dir)
        return chat_dirs
        
    # セーフモードではCursorStorageのみを使用
    if is_safe_mode():
        # CursorStorage内のWorkspaceStateを検索
        storage_dir = cursor_dir / "CursorStorage"
        workspace_dirs = []
        
        if storage_dir.exists():
            # WorkspaceStateサブディレクトリを検索
            for workspace_dir in storage_dir.glob("**/WorkspaceState"):
                if workspace_dir.is_dir():
                    workspace_dirs.append(workspace_dir)
                    
        return workspace_dirs
    
    # 通常モード: Local StorageとCursorStorageの両方を検索
    chat_dirs = []
    
    # 1. Local Storage / leveldb内のチャットファイル
    leveldb_dir = cursor_dir / "Local Storage" / "leveldb"
    if leveldb_dir.exists():
        chat_dirs.append(leveldb_dir)
    
    # 2. CursorStorage内のWorkspaceState
    storage_dir = cursor_dir / "CursorStorage"
    if storage_dir.exists():
        for workspace_dir in storage_dir.glob("**/WorkspaceState"):
            if workspace_dir.is_dir():
                chat_dirs.append(workspace_dir)
    
    return chat_dirs

def get_workspace_from_path(chat_path):
    """チャットパスからワークスペース名を抽出する"""
    # WorkspaceState形式のパスから抽出
    if "WorkspaceState" in str(chat_path):
        # 形式: .../CursorStorage/file__PATH/WorkspaceState
        parts = str(chat_path).split(os.sep)
        try:
            # file__PATH からパスを抽出
            for part in parts:
                if part.startswith("file__"):
                    # file__C:_Users_username_project を C:/Users/username/project に変換
                    path = part[6:].replace("_", os.sep if os.name == "nt" else "/")
                    if os.name == "nt" and path[1:3] != ":\\":
                        # Windows形式に修正 (例: C_Users → C:\Users)
                        path = f"{path[0]}:{path[1:]}"
                    return path
        except:
            pass
    
    # leveldb形式のパスの場合
    if "leveldb" in str(chat_path):
        # leveldbからの抽出は困難なため、一般名を返す
        return "Cursor共通ストレージ"
    
    return "不明なワークスペース"

def extract_chat_from_file(file_path, output_dir):
    """ファイルからチャットデータを抽出する"""
    try:
        if not file_path.exists():
            return False
            
        # ファイルサイズチェック (極端に大きいファイルはスキップ)
        if file_path.stat().st_size > 50 * 1024 * 1024:  # 50MB以上
            print(f"スキップ: {file_path.name} (サイズ過大)")
            return False
        
        with open(file_path, "rb") as f:
            content = f.read().decode("utf-8", errors="ignore")
            
        # .ldb/.log ファイルの場合、バイナリデータなのでJSON部分を探す
        chats_found = 0
        
        if file_path.suffix in [".ldb", ".log"]:
            # ChatTurn文字列を探してJSONとして解析
            json_pattern = r'"chatTurns":\s*\[.*?\]'
            import re
            matches = re.finditer(r'{"chatTurns":\s*\[.*?\]}', content, re.DOTALL)
            
            for match in matches:
                try:
                    json_str = match.group(0)
                    chat_data = json.loads(json_str)
                    
                    if "chatTurns" in chat_data and chat_data["chatTurns"]:
                        # 有効なチャットデータがある場合のみ保存
                        if len(chat_data["chatTurns"]) > 0:
                            # チャットIDを生成 (内容のハッシュ)
                            chat_id = hashlib.md5(json_str.encode()).hexdigest()[:10]
                            chat_title = get_chat_title(chat_data)
                            
                            # ファイル名を作成
                            filename = f"chat_{chat_id}_{chat_title}.json"
                            out_path = output_dir / filename
                            
                            # 整形して保存
                            with open(out_path, "w", encoding="utf-8") as out_file:
                                json.dump(chat_data, out_file, ensure_ascii=False, indent=2)
                                
                            chats_found += 1
                except:
                    # 解析エラーは無視して次へ
                    continue
        
        else:
            # 通常のJSONファイルの場合
            try:
                chat_data = json.loads(content)
                if "chatTurns" in chat_data and chat_data["chatTurns"]:
                    # 有効なチャットデータがある場合のみ保存
                    if len(chat_data["chatTurns"]) > 0:
                        # チャットIDを生成 (内容のハッシュ)
                        chat_id = hashlib.md5(content.encode()).hexdigest()[:10]
                        chat_title = get_chat_title(chat_data)
                        
                        # ファイル名を作成
                        filename = f"chat_{chat_id}_{chat_title}.json"
                        out_path = output_dir / filename
                        
                        # 整形して保存
                        with open(out_path, "w", encoding="utf-8") as out_file:
                            json.dump(chat_data, out_file, ensure_ascii=False, indent=2)
                            
                        chats_found += 1
            except:
                # 解析エラーは無視
                pass
        
        return chats_found > 0
    
    except Exception as e:
        print(f"ファイル処理エラー ({file_path.name}): {e}")
        return False

def get_chat_title(chat_data):
    """チャットデータからタイトルを抽出する"""
    # チャットのタイトルを抽出 (最初のユーザーメッセージを使用)
    title = "無題"
    
    try:
        if "chatTurns" in chat_data and chat_data["chatTurns"]:
            for turn in chat_data["chatTurns"]:
                if turn.get("role") == "user" and turn.get("message"):
                    # 最初の行を取得し、長さを制限
                    first_line = turn["message"].split("\n")[0].strip()
                    if first_line:
                        title = first_line[:30]
                        break
    except:
        pass
    
    # ファイル名に使用できない文字を置換
    for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
        title = title.replace(char, '_')
    
    return title

def process_chat_directory(chat_dir, output_dir, config):
    """チャットディレクトリを処理して、チャットデータを抽出する"""
    workspace_name = get_workspace_from_path(chat_dir)
    
    # アクティブワークスペースのスキップ (オプション)
    if skip_active_workspace() and workspace_name in config.get("active_workspaces", []):
        print(f"スキップ: {workspace_name} (アクティブワークスペース)")
        return 0
    
    total_chats = 0
    
    print(f"検索中: {workspace_name}")
    
    # WorkspaceStateディレクトリの場合
    if chat_dir.name == "WorkspaceState":
        # チャットファイルを検索
        chat_files = list(chat_dir.glob("*.json"))
        for file in chat_files:
            if extract_chat_from_file(file, output_dir):
                total_chats += 1
    
    # leveldbディレクトリの場合
    elif chat_dir.name == "leveldb":
        # .ldb および .log ファイルを検索
        ldb_files = list(chat_dir.glob("*.ldb"))
        log_files = list(chat_dir.glob("*.log"))
        
        for file in ldb_files + log_files:
            if extract_chat_from_file(file, output_dir):
                total_chats += 1
    
    if total_chats > 0:
        print(f"抽出: {workspace_name} から {total_chats} 件のチャット")
    
    return total_chats

def main():
    """メイン処理"""
    # 出力ディレクトリの準備
    output_dir = Path("json")
    output_dir.mkdir(exist_ok=True)
    
    # 設定の読み込み
    config = load_config()
    
    # オプションの設定
    args = parse_args()
    
    # セーフモードの確認
    safe_mode = is_safe_mode()
    if safe_mode:
        print("セーフモードが有効です")
    
    # アクティブワークスペーススキップの確認
    if not skip_active_workspace():
        print("アクティブワークスペーススキップが無効になっています")
    
    # テストモードの確認
    if is_test_mode():
        print("テストモードが有効です")
    
    # Cursorのチャットディレクトリを取得
    chat_dirs = get_cursor_chat_dirs()
    
    if not chat_dirs:
        print("Cursor のデータディレクトリが見つかりませんでした")
        return
    
    print(f"Cursor Chat 抽出ツール v{VERSION}")
    print(f"プラットフォーム: {platform.system()} {platform.release()}")
    print(f"{len(chat_dirs)} 個のデータディレクトリを検索します...")
    
    # 各ディレクトリを処理
    total_extracted = 0
    
    for chat_dir in chat_dirs:
        extracted = process_chat_directory(chat_dir, output_dir, config)
        total_extracted += extracted
    
    # 結果表示
    if total_extracted > 0:
        print(f"\n処理完了: {total_extracted} 件のチャットを抽出しました")
        print(f"チャットデータは {output_dir} に保存されています")
        
        # 新しい抽出数を記録
        config["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
        config["extraction_count"] += total_extracted
        save_config(config)
        
        # クリップボードにコピー
        if CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(f"{output_dir}")
                print("出力パスをクリップボードにコピーしました")
            except:
                pass
    else:
        print("\n抽出可能なチャットが見つかりませんでした")
    
    # 終了前に一時停止（Windows）
    if platform.system() == "Windows" and not sys.stdin.isatty():
        print("\n何かキーを押すと終了します...")
        input()

if __name__ == "__main__":
    main()
