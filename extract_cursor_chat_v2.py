#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sqlite3
import os
import sys
from pathlib import Path
import platform
from datetime import datetime
import re
import shutil

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

def get_db_connection(db_path):
    """データベースへの接続を取得"""
    # 1. ファイルが存在して読み取り可能かどうかを確認
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが存在しません: {db_path}")
        return None
        
    if not os.access(db_path, os.R_OK):
        print(f"❌ データベースファイルが読み取り不可です: {db_path}")
        return None
        
    # 2. ファイルサイズが0なら無効
    if os.path.getsize(db_path) == 0:
        print(f"❌ データベースファイルが空です: {db_path}")
        return None
    
    # 3. 安全な接続テスト - ファイル使用状況を確認
    try:
        # プラットフォームに応じたファイルロックチェック
        if platform.system() == "Windows":
            # Windowsでは書き込みモードでファイルを開こうとして、エラーならロック中と判断
            try:
                # 0.5秒でタイムアウトする書き込みテスト
                import msvcrt
                file_handle = open(db_path, 'ab+')
                try:
                    # 明示的なロックの確認
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                except IOError:
                    file_handle.close()
                    print(f"⚠️ データベースファイルがロックされています: {db_path}")
                    return None
                file_handle.close()
            except IOError:
                print(f"⚠️ データベースがロック/使用中です: {db_path}")
                return None
        else:
            # macOS/Linuxではfcntlを使用してロックをチェック
            try:
                import fcntl
                with open(db_path, 'r') as f:
                    try:
                        # 非排他的ロックを試みる (読み取り専用)
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                        # ロックを解除
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except IOError:
                        print(f"⚠️ データベースがロック/使用中です: {db_path}")
                        return None
            except ImportError:
                # fcntlが使用できない場合はスキップ
                pass
    except Exception as e:
        print(f"⚠️ データベースのロックチェック中にエラー: {e}")
        # 安全のためここでリターン
        return None
        
    # 4. 実際の接続試行 (安全なチェック後)
    try:
        # まずread-onlyモードで試行 (タイムアウト短め)
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1)
        # 接続のテスト
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        return conn
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print(f"⚠️ データベースがロックされています: {db_path}")
            return None
        elif "no such table" in str(e).lower():
            # テーブルがない場合は接続自体は成功しているので問題なし
            return conn
        elif "unable to open database file" in str(e).lower():
            print(f"⚠️ データベースが開けません: {db_path}")
            return None
        else:
            print(f"⚠️ データベース接続エラー: {e}")
            return None
    except Exception as e:
        print(f"❌ DBへの接続に失敗しました: {e}")
        return None

def safe_parse_json(json_str):
    """JSONを安全にパースする"""
    if not json_str:
        return None, "空のJSONデータ"
        
    try:
        return json.loads(json_str), None
    except json.JSONDecodeError as e:
        print(f"⚠️ JSONパースエラー: {e}")
        
        # 修復を試みる (末尾のカンマを削除)
        cleaned_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        try:
            return json.loads(cleaned_str), None
        except Exception as e2:
            # 後方互換性のため部分的なJSONパースを試みる
            try:
                # 文字列の先頭と末尾を修正
                if not cleaned_str.startswith('{'):
                    cleaned_str = '{' + cleaned_str
                if not cleaned_str.endswith('}'):
                    cleaned_str = cleaned_str + '}'
                return json.loads(cleaned_str), None
            except:
                return None, f"JSONパースエラー: {e}"

def format_time(timestamp):
    """タイムスタンプを整形"""
    if not timestamp:
        return "不明"
    try:
        return datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(timestamp)

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

def get_chat_data(workspace_id: str, db_path: Path) -> dict:
    """指定されたワークスペースのチャットデータを取得"""
    workspace_dir = db_path.parent
    workspace_path = get_workspace_path(workspace_dir)
    
    result = {
        "workspace_id": workspace_id,
        "workspace_path": workspace_path,
        "chats": [],
        "composers": []
    }
    
    # データベースへの接続を試行
    conn = get_db_connection(db_path)
    if not conn:
        return result

    try:
        cursor = conn.cursor()
        
        # AIチャットデータを取得
        chat_result = cursor.execute(
            "SELECT value FROM ItemTable WHERE key = 'workbench.panel.aichat.view.aichat.chatdata'"
        ).fetchone()
        
        if chat_result and chat_result[0]:
            chat_data, error = safe_parse_json(chat_result[0])
            if error:
                print(f"⚠️ チャットデータ取得エラー: {error}")
            
            if chat_data and 'tabs' in chat_data and isinstance(chat_data['tabs'], list):
                for tab in chat_data['tabs']:
                    chat_info = {
                        "id": tab.get('tabId', ''),
                        "title": tab.get('chatTitle', f"Chat {tab.get('tabId', '')[:8]}"),
                        "timestamp": format_time(tab.get('lastSendTime', '')),
                        "created_at": tab.get('created_at', ''),  # created_atを追加
                        "messages": []
                    }
                    
                    # メッセージを取得
                    bubbles = tab.get('bubbles', []) or []  # Noneの場合は空リスト
                    for bubble in bubbles:
                        if not bubble:  # Noneや空オブジェクトの場合はスキップ
                            continue
                            
                        message = {
                            "type": bubble.get('type', 'unknown'),
                            "text": bubble.get('text', ''),
                            "timestamp": format_time(bubble.get('timestamp', ''))
                        }
                        if message["text"]:  # 空のメッセージは追加しない
                            chat_info["messages"].append(message)
                    
                    result["chats"].append(chat_info)
        
        # Composerデータを取得
        composer_result = cursor.execute(
            "SELECT value FROM ItemTable WHERE key = 'composer.composerData'"
        ).fetchone()
        
        if composer_result and composer_result[0]:
            composer_data, error = safe_parse_json(composer_result[0])
            if error:
                print(f"⚠️ Composerデータ取得エラー: {error}")
                
            if composer_data and 'allComposers' in composer_data and isinstance(composer_data['allComposers'], list):
                # グローバルストレージからComposerの詳細データを取得
                global_storage_dir = get_global_storage_dir()
                global_db_path = global_storage_dir / "state.vscdb" if global_storage_dir else None
                
                composer_details = {}
                
                # グローバルDBからComposerデータを取得
                if global_db_path and global_db_path.exists():
                    global_conn = get_db_connection(global_db_path)
                    if global_conn:
                        global_cursor = global_conn.cursor()
                        composer_keys = []
                        
                        # 全composerIDのリストを作成
                        for composer in composer_data['allComposers']:
                            composer_id = composer.get('composerId', '')
                            if composer_id:
                                composer_keys.append(f"composerData:{composer_id}")
                        
                        # composerデータを取得
                        if composer_keys:
                            placeholders = ','.join(['?'] * len(composer_keys))
                            query = f"SELECT key, value FROM cursorDiskKV WHERE key IN ({placeholders})"
                            try:
                                results = global_cursor.execute(query, composer_keys).fetchall()
                                for key, value in results:
                                    if not value:
                                        continue
                                    composer_id = key.replace('composerData:', '')
                                    details, parse_error = safe_parse_json(value)
                                    if parse_error:
                                        print(f"⚠️ Composer詳細のパースエラー [{composer_id}]: {parse_error}")
                                    if details:
                                        composer_details[composer_id] = details
                            except Exception as e:
                                print(f"⚠️ グローバルDBからの読み込みエラー: {e}")
                                
                                # cursorDiskKVテーブルがない場合は別の方法を試す
                                try:
                                    tables = global_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                                    print(f"利用可能なテーブル: {tables}")
                                    
                                    for key in composer_keys:
                                        try:
                                            result = global_cursor.execute("SELECT value FROM ItemTable WHERE key = ?", (key,)).fetchone()
                                            if result and result[0]:
                                                composer_id = key.replace('composerData:', '')
                                                details, parse_error = safe_parse_json(result[0])
                                                if parse_error:
                                                    print(f"⚠️ ItemTableからのComposer詳細のパースエラー [{composer_id}]: {parse_error}")
                                                if details:
                                                    composer_details[composer_id] = details
                                        except Exception as e3:
                                            print(f"⚠️ ItemTable単一キー読み込みエラー: {e3}")
                                except Exception as e2:
                                    print(f"⚠️ 代替方法での読み込みエラー: {e2}")
                        
                        global_conn.close()
                                            
                # 各Composerの情報を構築
                for composer in composer_data['allComposers']:
                    composer_id = composer.get('composerId', '')
                    if not composer_id:  # IDが無い場合はスキップ
                        continue
                    
                    # 詳細情報をマージ
                    detail = composer_details.get(composer_id, {})
                    if detail:
                        # 詳細データが見つかった場合は上書き
                        for key, value in detail.items():
                            composer[key] = value
                    
                    # タイトル整形ロジック改善
                    title = composer.get('name', '')
                    if not title:
                        title = composer.get('text', '')
                        if title:
                            title = title[:30]  # 長すぎる場合は切り詰め
                        else:
                            title = f"Composer {composer_id[:8]}"
                    
                    composer_info = {
                        "id": composer_id,
                        "title": title,
                        "text": composer.get('text', ''),
                        "created_at": format_time(composer.get('createdAt')),
                        "updated_at": format_time(composer.get('lastUpdatedAt')),
                        "conversation": []
                    }
                    
                    # 会話履歴を取得 (複数の可能性のあるキーを試す)
                    conversation = None  # 初期値をNoneに設定
                    # 主要な候補キーをチェック
                    for key in ['conversation', 'history', 'messages', 'interactions']:
                        if isinstance(composer.get(key), list):
                            conversation = composer.get(key)
                            break
                    
                    # 会話データが見つからなかった場合、空リストをデフォルト値として使用
                    if conversation is None:
                        conversation = []
                    
                    for msg in conversation:
                        if not msg:  # Noneや空オブジェクトの場合はスキップ
                            continue
                            
                        # メッセージタイプの取得 (複数の可能性のあるキーを試す)
                        msg_type = "unknown"
                        if 'type' in msg:
                            msg_type = "user" if msg.get('type') == 1 else "assistant"
                        elif 'role' in msg:
                            msg_type = msg.get('role')
                        
                        # メッセージテキストの取得 (複数の可能性のあるキーを試す)
                        text = ""
                        for key in ['text', 'content', 'message']:
                            if key in msg and msg[key]:
                                text = msg[key]
                                break
                        
                        message = {
                            "type": msg_type,
                            "text": text,
                            "timestamp": format_time(msg.get('timestamp'))
                        }
                        composer_info["conversation"].append(message)
                    
                    result["composers"].append(composer_info)
    
    except Exception as e:
        print(f"❌ データ抽出中にエラー: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        if conn:
            conn.close()
    
    return result

import os

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

def main():
    # ワークスペースストレージディレクトリを取得
    storage_dir = get_workspace_storage_dir()
    if not storage_dir or not storage_dir.exists():
        print(f"❌ ワークスペースストレージディレクトリが見つかりません: {storage_dir}")
        return
    
    print(f"✅ ワークスペースストレージディレクトリ: {storage_dir}")
    
    # 現在のディレクトリ名（現在のワークスペースのIDを含む可能性がある）
    current_dir = os.path.basename(os.getcwd())
    
    # 現在実行中のCursorプロセスを検出（プラットフォームによって異なる）
    active_workspace_markers = []
    active_workspace_markers.append(current_dir)
    
    try:
        # プロセスリストからCursorを検索するプラットフォーム固有のコード
        if platform.system() == "Windows":
            import subprocess
            result = subprocess.run(["tasklist", "/fi", "imagename eq Cursor.exe"], capture_output=True, text=True)
            if "Cursor.exe" in result.stdout:
                print("⚠️ Cursorが実行中です。実行中のワークスペースはスキップします。")
        elif platform.system() in ["Darwin", "Linux"]:
            import subprocess
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            if "Cursor" in result.stdout:
                print("⚠️ Cursorが実行中です。実行中のワークスペースはスキップします。")
    except Exception as e:
        print(f"⚠️ アクティブプロセスの検出中にエラー: {e}")
    
    # ワークスペースを取得
    workspaces = []
    for workspace_dir in storage_dir.iterdir():
        if workspace_dir.is_dir():
            db_path = workspace_dir / "state.vscdb"
            if db_path.exists():
                workspaces.append((workspace_dir.name, db_path))
    
    if not workspaces:
        print("❌ ワークスペースが見つかりません")
        return
    
    print(f"🔍 {len(workspaces)}個のワークスペースが見つかりました")
    
    # 各ワークスペースのデータを取得
    all_results = []
    skipped_workspaces = []
    
    for i, (workspace_id, db_path) in enumerate(workspaces):
        # 現在のワークスペースに関連する可能性があるかチェック
        skip = False
        for marker in active_workspace_markers:
            if marker in workspace_id:
                print(f"\n⚠️ 現在アクティブな可能性があるワークスペース: {workspace_id} - スキップします")
                skipped_workspaces.append(workspace_id)
                skip = True
                break
        
        if skip:
            continue
            
        print(f"\n🔍 ワークスペース #{i+1}: {workspace_id}")
        
        # ロックされている可能性があるのでまずファイルの状態をチェック
        try:
            # ファイルが存在して読み取り可能かどうかを確認
            if not os.access(db_path, os.R_OK):
                print(f"⚠️ データベースファイルが読み取り不可のためスキップします: {db_path}")
                skipped_workspaces.append(workspace_id)
                continue
                
            # ファイルサイズが0なら無効
            if os.path.getsize(db_path) == 0:
                print(f"⚠️ データベースファイルが空のためスキップします: {db_path}")
                skipped_workspaces.append(workspace_id)
                continue
                
            # Cursorプロセスチェックを削除 - 代わりにデータベースのロックチェックのみを使用
        except Exception as e:
            print(f"⚠️ ファイルチェック中にエラーが発生したためスキップします: {workspace_id} - {e}")
            skipped_workspaces.append(workspace_id)
            continue
        
        # 実際のデータ抽出（直接extract_chat_dataを呼び出し、内部でエラー処理）
        result = get_chat_data(workspace_id, db_path)

        # 重複を削除
        result = remove_duplicates(result)
        
        # データが少ない場合はスキップされた可能性がある
        if len(result['chats']) == 0 and len(result['composers']) == 0:
            print(f"⚠️ データが取得できませんでした（ロックされている可能性あり）: {workspace_id}")
            skipped_workspaces.append(workspace_id)
            continue

        # 結果を表示
        print(f"  - チャット数: {len(result['chats'])}")
        print(f"  - Composer数: {len(result['composers'])}")
        
        if result['chats']:
            print("\n  📑 チャット:")
            for chat in result['chats']:  # すべて表示
                print(f"    🗨️ {chat['title']} ({len(chat['messages'])}件のメッセージ)")
        
        if result['composers']:
            print("\n  📝 Composer:")
            for composer in result['composers']:  # すべて表示
                print(f"    ✏️ {composer['title']} ({len(composer['conversation'])}件の会話)")
                if composer['conversation']:
                    first_msg = composer['conversation'][0]
                    preview = first_msg['text'][:50] + "..." if len(first_msg['text']) > 50 else first_msg['text']
                    print(f"       {first_msg['type']}: {preview}")
        
        all_results.append(result)
    
    # スキップされたワークスペースについて表示
    if skipped_workspaces:
        print(f"\n⚠️ 次のワークスペースはスキップされました（使用中/ロック中）:")
        for ws in skipped_workspaces:
            print(f"  - {ws}")
    
    # 結果が無い場合
    if not all_results:
        print("\n❌ 読み込めたワークスペースがありません。Cursorを閉じてから再実行してください。")
        return
    
    # 自動的に保存 (確認をスキップ)
    print("\n✅ JSONファイルに保存します...")
    
    # タイムスタンプを生成（すべてのファイルで共通のタイムスタンプを使用）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 各ワークスペースを個別のファイルとして保存
    saved_files = []
    for result in all_results:
        workspace_id = result["workspace_id"]
        # ワークスペース名を短くする (先頭の数文字だけ使用)
        short_id = workspace_id[:8]
        
        # チャットとコンポーザー数を取得
        chat_count = len(result.get("chats", []))
        composer_count = len(result.get("composers", []))
        
        # 合計メッセージ数を計算
        message_count = sum(len(chat.get("messages", [])) for chat in result.get("chats", []))
        message_count += sum(len(comp.get("conversation", [])) for comp in result.get("composers", []))
        
        # save_json_file関数を使用してJSONファイルを保存
        workspace_file, integrated_file = save_json_file(result, workspace_id, chat_count, composer_count)
        
        print(f"✅ ワークスペース '{short_id}' のデータを保存: {workspace_file} (メッセージ数: {message_count})")
        saved_files.append(workspace_file)
    
    # 保存したファイルのリスト
    print(f"\n保存したファイル ({len(saved_files)}件):")
    for file in saved_files:
        print(f"  - {file}")
    
    print("\n💡 ヒント: cursor_chat_viewer.pyを実行してJSONファイルを表示できます。")

if __name__ == "__main__":
    main()
