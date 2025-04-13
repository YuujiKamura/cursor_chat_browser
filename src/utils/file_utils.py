#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import platform
from pathlib import Path
import shutil
import re
from datetime import datetime
import json

def ensure_dir_exists(dir_path):
    """
    ディレクトリが存在することを確認し、存在しない場合は作成する
    
    Args:
        dir_path: 作成するディレクトリのパス（文字列またはPathオブジェクト）
        
    Returns:
        Path: 作成されたディレクトリのPathオブジェクト
    """
    path = Path(dir_path) if isinstance(dir_path, str) else dir_path
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_app_data_dir(app_name):
    """
    アプリケーションデータディレクトリを取得する
    
    Args:
        app_name: アプリケーション名
        
    Returns:
        Path: アプリケーションデータディレクトリのパス
    """
    system = platform.system()
    
    if system == "Windows":
        base_dir = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(base_dir) / app_name
    elif system == "Darwin":  # macOS
        return Path(os.path.expanduser("~")) / "Library" / "Application Support" / app_name
    else:  # Linux/Unix
        # XDG_DATA_HOME環境変数があればそれを使用、なければ~/.local/share
        base_dir = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        return Path(base_dir) / app_name

def is_file_locked(filepath):
    """
    ファイルがロックされているかどうかを確認する
    
    Args:
        filepath: チェックするファイルのパス
        
    Returns:
        bool: ファイルがロックされている場合はTrue、そうでない場合はFalse
    """
    filepath = Path(filepath)
    if not filepath.exists():
        return False
        
    # プラットフォームに応じたファイルロックチェック
    try:
        if platform.system() == "Windows":
            # Windowsでは書き込みモードでファイルを開こうとして、エラーならロック中と判断
            try:
                with open(filepath, 'a+b') as f:
                    pass
            except IOError:
                return True
        else:
            # Unix系ではfcntlを使用
            try:
                import fcntl
                with open(filepath, 'a+b') as f:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(f, fcntl.LOCK_UN)
            except (IOError, ImportError):
                return True
        return False
    except Exception:
        # 何らかのエラーが発生した場合は、安全側に倒してロックされていると判断
        return True

def safe_copy_file(src, dst, overwrite=False):
    """
    ファイルを安全にコピーする
    
    Args:
        src: コピー元ファイルのパス
        dst: コピー先ファイルのパス
        overwrite: 既存ファイルを上書きするかどうか（デフォルトはFalse）
        
    Returns:
        bool: コピーが成功した場合はTrue、失敗した場合はFalse
    """
    src_path = Path(src)
    dst_path = Path(dst)
    
    # ソースが存在しない場合
    if not src_path.exists():
        print(f"エラー: コピー元ファイルが存在しません: {src}")
        return False
        
    # 上書きしない設定で、宛先が既に存在する場合
    if not overwrite and dst_path.exists():
        print(f"エラー: コピー先ファイルがすでに存在します: {dst}")
        return False
        
    # ディレクトリが存在することを確認
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # ファイルをコピー
        shutil.copy2(src_path, dst_path)
        return True
    except Exception as e:
        print(f"ファイルコピーエラー: {e}")
        return False

def create_backup(filepath, backup_dir=None, max_backups=5):
    """
    ファイルのバックアップを作成する
    
    Args:
        filepath: バックアップするファイルのパス
        backup_dir: バックアップディレクトリ（指定しない場合は同じディレクトリに作成）
        max_backups: 保持する最大バックアップ数
        
    Returns:
        Path: 作成されたバックアップファイルのパス、または失敗した場合はNone
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        print(f"エラー: バックアップするファイルが存在しません: {filepath}")
        return None
        
    # バックアップディレクトリの設定
    if backup_dir:
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
    else:
        backup_path = filepath.parent
        
    # タイムスタンプを使用してバックアップファイル名を生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_path / f"{filepath.stem}_{timestamp}{filepath.suffix}"
    
    try:
        # ファイルをコピー
        shutil.copy2(filepath, backup_file)
        
        # 古いバックアップを削除（最大数を超える場合）
        if max_backups > 0:
            pattern = f"{filepath.stem}_*{filepath.suffix}"
            backups = sorted(backup_path.glob(pattern))
            if len(backups) > max_backups:
                # 最も古いファイルから削除
                for old_backup in backups[:-max_backups]:
                    old_backup.unlink()
                    
        return backup_file
    except Exception as e:
        print(f"バックアップ作成エラー: {e}")
        return None

def get_workspace_storage_dir():
    """プラットフォームに応じたワークスペースストレージディレクトリを返す"""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Cursor" / "User" / "workspaceStorage"
    elif platform.system() == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
    elif platform.system() == "Linux":
        # Linux用の複数の候補
        candidates = [
            Path.home() / ".config" / "Cursor" / "User" / "workspaceStorage",
            Path.home() / ".cursor" / "User" / "workspaceStorage",
        ]
        for path in candidates:
            if path.exists():
                return path
    return None

def get_global_storage_dir():
    """グローバルストレージディレクトリを返す"""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Cursor" / "User" / "globalStorage"
    elif platform.system() == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage"
    elif platform.system() == "Linux":
        candidates = [
            Path.home() / ".config" / "Cursor" / "User" / "globalStorage",
            Path.home() / ".cursor" / "User" / "globalStorage",
        ]
        for path in candidates:
            if path.exists():
                return path
    return None

def get_workspace_path(workspace_dir: Path) -> str:
    """ワークスペースのパスを取得"""
    workspace_json = workspace_dir / "workspace.json"
    if workspace_json.exists():
        try:
            with open(workspace_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                folder_uri = data.get("folder")
                if folder_uri:
                    # file:///形式のURIをデコード
                    if folder_uri.startswith("file:///"):
                        path = folder_uri[8:]  # "file:///"を除去
                        if platform.system() == "Windows" and path.startswith("/"):
                            path = path[1:]  # Windowsの場合、先頭の/を除去
                        return path
                    return folder_uri
        except Exception as e:
            print(f"⚠️ workspace.jsonの読み込みエラー: {e}")
    return "Unknown"

def format_time(timestamp):
    """タイムスタンプを整形"""
    if not timestamp:
        return "不明"
    try:
        return datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(timestamp)

def save_json_file(data, workspace_id, chat_count, composer_count):
    """JSONファイルを保存"""
    # チャットのcreated_atを使用してタイムスタンプを生成
    timestamp = None
    
    # まずはチャットのcreated_atを試す
    for chat in data.get("chats", []):
        if chat.get("created_at"):
            try:
                # created_atが数値（UNIXタイムスタンプ）の場合
                if isinstance(chat["created_at"], (int, float)):
                    timestamp = datetime.fromtimestamp(chat["created_at"]).strftime("%Y%m%d")
                    break
                # 既に文字列形式の場合（"2021-07-01 12:00:00"など）
                elif isinstance(chat["created_at"], str) and "20" in chat["created_at"]:
                    # 日付文字列からタイムスタンプを抽出 (YYYYMMDDの形式)
                    date_match = re.search(r'20\d{2}[-/]?(\d{2})[-/]?(\d{2})', chat["created_at"])
                    if date_match:
                        year_match = re.search(r'(20\d{2})', chat["created_at"])
                        if year_match:
                            year = year_match.group(1)
                            month = date_match.group(1)
                            day = date_match.group(2)
                            timestamp = f"{year}{month}{day}"
                            break
            except Exception as e:
                print(f"⚠️ タイムスタンプ変換エラー: {e} - 値: {chat['created_at']}")
                continue
    
    # チャットからタイムスタンプを取得できなかった場合、Composerを試す
    if not timestamp:
        for composer in data.get("composers", []):
            created_at = composer.get("created_at")
            if created_at and isinstance(created_at, str) and "20" in created_at:
                try:
                    # "2021-07-01 12:00:00"形式から日付部分を抽出
                    date_match = re.search(r'(20\d{2})[-/]?(\d{2})[-/]?(\d{2})', created_at)
                    if date_match:
                        year = date_match.group(1)
                        month = date_match.group(2)
                        day = date_match.group(3)
                        timestamp = f"{year}{month}{day}"
                        break
                except Exception as e:
                    print(f"⚠️ Composerタイムスタンプ変換エラー: {e} - 値: {created_at}")
                    continue
    
    # それでもタイムスタンプが取得できない場合は現在時刻を使用
    if not timestamp:
        timestamp = datetime.now().strftime('%Y%m%d')
        print(f"⚠️ 有効なcreated_atが見つからないため、現在時刻をタイムスタンプとして使用します: {timestamp}")
    
    # ディレクトリが存在しない場合は作成
    os.makedirs("json", exist_ok=True)

    # ワークスペースパスから有効なファイル名部分を抽出
    workspace_path = data.get("workspace_path", "unknown")
    path_id = ""
    
    if workspace_path and workspace_path != "Unknown":
        # パスから最後のディレクトリ名を取得
        try:
            # Windowsパスの場合はバックスラッシュを考慮
            if "\\" in workspace_path:
                path_parts = workspace_path.split("\\")
            else:
                path_parts = workspace_path.split("/")
                
            # 最後の非空の部分を使用
            for part in reversed(path_parts):
                if part and part not in [".", ".."]:
                    # 非ASCII文字や特殊文字を削除し、長さを制限
                    # 英数字、アンダースコア、ハイフンのみ許可
                    safe_part = re.sub(r'[^\w\-]', '', part)
                    # 長さを最大20文字に制限
                    path_id = "_" + safe_part[:20]
                    break
        except Exception as e:
            print(f"⚠️ パス解析エラー: {e}")
            path_id = "_unknown"
    
    # 安全なファイル名を作成
    try:
        # タイムスタンプがなければ現在時刻を使用
        if not timestamp:
            timestamp = datetime.now().strftime('%Y%m%d')
            
        # 基本ファイル名を作成
        filename = f"ws_{timestamp}{path_id}.json"
        # ファイル名の最大長を制限（Windowsの場合、パスの最大長は260文字）
        # jsonディレクトリとパス区切り文字の長さを考慮して、ファイル名は200文字以内に
        if len(filename) > 200:
            # 長すぎる場合は切り詰める
            filename = f"ws_{timestamp}.json"
            print(f"⚠️ ファイル名が長すぎるため、簡略化します: {filename}")
            
        workspace_file = os.path.join("json", filename)
        
        # ファイルパスが有効か確認
        if os.path.exists(os.path.dirname(workspace_file)):
            # ワークスペース固有のJSONファイルを保存
            with open(workspace_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            print(f"⚠️ 保存先ディレクトリが存在しません: {os.path.dirname(workspace_file)}")
            # 代替パスを使用
            alt_file = f"ws_{timestamp}.json"
            with open(alt_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            workspace_file = alt_file
            print(f"✅ 代替パスにファイルを保存しました: {workspace_file}")
    
    except Exception as e:
        print(f"⚠️ JSONファイル保存エラー: {e}")
        # 最小限のファイル名で再試行
        try:
            fallback_file = f"ws_{timestamp}.json"
            with open(fallback_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            workspace_file = fallback_file
            print(f"✅ フォールバックファイルとして保存しました: {workspace_file}")
        except Exception as e2:
            print(f"❌ ファイル保存に完全に失敗しました: {e2}")
            return None, None
            
    return workspace_file, None

def remove_duplicates(data):
    """重複したデータを削除"""
    unique_chats = []
    seen_chat_ids = set()
    for chat in data.get("chats", []):
        chat_id = chat.get("id")
        if chat_id and chat_id not in seen_chat_ids:
            unique_chats.append(chat)
            seen_chat_ids.add(chat_id)
    data["chats"] = unique_chats

    unique_composers = []
    seen_composer_ids = set()
    for composer in data.get("composers", []):
        composer_id = composer.get("id")
        if composer_id and composer_id not in seen_composer_ids:
            unique_composers.append(composer)
            seen_composer_ids.add(composer_id)
    data["composers"] = unique_composers
    return data 