#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import platform
from pathlib import Path
from datetime import datetime
import subprocess
import traceback
import time
import sqlite3
import io

# Windows環境での文字化けを防ぐためにUTF-8出力に設定
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.utils.file_utils import get_workspace_storage_dir, get_global_storage_dir, get_workspace_path
from src.utils.file_utils import format_time, save_json_file, remove_duplicates
from src.utils.json_utils import safe_parse_json
from src.core.db_utils import get_db_connection, safe_db_connection

# 環境変数からセーフモードの状態を取得
SAFE_MODE = os.environ.get("CURSOR_CHAT_SAFE_MODE") == "1"
SKIP_ACTIVE = os.environ.get("CURSOR_CHAT_SKIP_ACTIVE") == "1"
USE_REAL_DATA = os.environ.get("CURSOR_ACTUAL_STORAGE") is not None

def get_workspace_storage_dir_override():
    """使用するワークスペースストレージディレクトリを決定"""
    # 実際のCursorストレージを使用する場合
    if USE_REAL_DATA:
        real_storage = os.environ.get("CURSOR_ACTUAL_STORAGE")
        if real_storage:
            return Path(real_storage)
    
    # 通常のワークスペースストレージディレクトリを取得
    return get_workspace_storage_dir()

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
    try:
        # 複数回試行するロジック
        max_retries = 5 if SAFE_MODE else 3
        retry_delay = 0.5  # 秒
        
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"⚠️ リトライ {attempt}/{max_retries}...")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # 指数バックオフ
                
            # safe_db_connectionを使用して接続
            with safe_db_connection(db_path) as conn:
                if not conn:
                    if attempt < max_retries - 1:
                        continue  # 再試行
                    else:
                        print(f"❌ データベース接続に失敗しました（{max_retries}回試行後）: {db_path}")
                        return result
                
                try:
                    cursor = conn.cursor()
                    
                    # AIチャットデータを取得
                    try:
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
                                        "created_at": tab.get('created_at', ''),
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
                    except sqlite3.OperationalError as e:
                        print(f"⚠️ チャットデータクエリエラー: {e}")
                        if "database is locked" in str(e) and attempt < max_retries - 1:
                            continue  # 再試行
                    except Exception as e:
                        print(f"⚠️ チャットデータ処理エラー: {e}")
                    
                    # セーフモードの場合、必要最小限のComposerデータのみ取得
                    if SAFE_MODE:
                        print("ℹ️ セーフモード: 最小限のComposerデータのみ取得します")
                    
                    # Composerデータを取得
                    try:
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
                                
                                # グローバルDBからComposerデータを取得（必要な場合のみ）
                                # Composerデータに必要最小限の情報が揃っているか確認
                                missing_data = False
                                for composer in composer_data['allComposers']:
                                    if not composer.get('text') and not composer.get('name'):
                                        missing_data = True
                                        break
                                
                                # セーフモードでなく、かつデータが不足している場合のみグローバルDBにアクセス
                                if not SAFE_MODE and missing_data and global_db_path and global_db_path.exists():
                                    # 安全な接続を使用
                                    with safe_db_connection(global_db_path) as global_conn:
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
                                                # まずcursorDiskKVテーブルを試行
                                                try:
                                                    placeholders = ','.join(['?'] * len(composer_keys))
                                                    query = f"SELECT key, value FROM cursorDiskKV WHERE key IN ({placeholders})"
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
                                                except sqlite3.OperationalError:
                                                    # テーブルが存在しない場合
                                                    try:
                                                        tables = global_cursor.execute(
                                                            "SELECT name FROM sqlite_master WHERE type='table'"
                                                        ).fetchall()
                                                        print(f"利用可能なテーブル: {tables}")
                                                        
                                                        # ItemTableを試行
                                                        for key in composer_keys:
                                                            try:
                                                                result = global_cursor.execute(
                                                                    "SELECT value FROM ItemTable WHERE key = ?", 
                                                                    (key,)
                                                                ).fetchone()
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
                                                except Exception as e:
                                                    print(f"⚠️ グローバルDBからの読み込みエラー: {e}")
                                
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
                                    
                                    # セーフモードの場合は会話履歴のローディングをスキップ
                                    if SAFE_MODE:
                                        # 最小限の情報だけ保存してスキップ
                                        result["composers"].append(composer_info)
                                        continue
                                    
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
                    except sqlite3.OperationalError as e:
                        print(f"⚠️ Composerデータクエリエラー: {e}")
                        if "database is locked" in str(e) and attempt < max_retries - 1:
                            continue  # 再試行
                    except Exception as e:
                        print(f"⚠️ Composerデータ処理エラー: {e}")
                    
                    # データ取得が完了したのでループから抜ける
                    return result
                    
                except Exception as e:
                    print(f"❌ データ抽出中にエラー: {e}")
                    traceback.print_exc()
                    if attempt < max_retries - 1:
                        continue  # 再試行
    
    except Exception as e:
        print(f"❌ 予期せぬエラー: {e}")
        traceback.print_exc()
    
    return result

def main():
    # ワークスペースストレージディレクトリを取得（オーバーライド対応）
    storage_dir = get_workspace_storage_dir_override()
    if not storage_dir or not storage_dir.exists():
        print(f"❌ ワークスペースストレージディレクトリが見つかりません: {storage_dir}")
        return
    
    print(f"✅ ワークスペースストレージディレクトリ: {storage_dir}")
    
    if SAFE_MODE:
        print("🔒 セーフモードが有効です: より保守的なデータベースアクセスを行い、ロック回避を強化します")
    
    if USE_REAL_DATA:
        print("🔍 実際のCursorデータを使用: " + os.environ.get("CURSOR_ACTUAL_STORAGE", "不明"))
    
    # 現在のディレクトリ名（現在のワークスペースのIDを含む可能性がある）
    current_dir = os.path.basename(os.getcwd())
    
    # 現在実行中のCursorプロセスを検出（プラットフォームによって異なる）
    active_workspace_markers = []
    active_workspace_markers.append(current_dir)
    
    cursor_running = False
    
    # SKIP_ACTIVEが無効の場合のみチェック
    if not SKIP_ACTIVE:
        try:
            # プロセスリストからCursorを検索するプラットフォーム固有のコード
            if platform.system() == "Windows":
                result = subprocess.run(["tasklist", "/fi", "imagename eq Cursor.exe"], capture_output=True, text=True)
                if "Cursor.exe" in result.stdout:
                    print("⚠️ Cursorが実行中です。実行中のワークスペースはスキップします。")
                    cursor_running = True
            elif platform.system() in ["Darwin", "Linux"]:
                result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
                if "Cursor" in result.stdout:
                    print("⚠️ Cursorが実行中です。実行中のワークスペースはスキップします。")
                    cursor_running = True
        except Exception as e:
            print(f"⚠️ アクティブプロセスの検出中にエラー: {e}")
    else:
        print("ℹ️ アクティブなワークスペースのスキップが無効化されています")
        cursor_running = False
    
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
        if cursor_running:
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
                
        except Exception as e:
            print(f"⚠️ ファイルチェック中にエラーが発生したためスキップします: {workspace_id} - {e}")
            skipped_workspaces.append(workspace_id)
            continue
        
        try:
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
                    msg_count = len(composer.get('conversation', []))
                    print(f"    ✏️ {composer['title']} ({msg_count}件の会話)")
                    if msg_count > 0 and not SAFE_MODE:
                        first_msg = composer['conversation'][0]
                        preview = first_msg['text'][:50] + "..." if len(first_msg['text']) > 50 else first_msg['text']
                        print(f"       {first_msg['type']}: {preview}")
            
            all_results.append(result)
        except Exception as e:
            print(f"❌ ワークスペース処理中にエラー: {workspace_id} - {e}")
            traceback.print_exc()
            skipped_workspaces.append(workspace_id)
    
    # スキップされたワークスペースについて表示
    if skipped_workspaces:
        print(f"\n⚠️ 次のワークスペースはスキップされました（使用中/ロック中）:")
        for ws in skipped_workspaces:
            print(f"  - {ws}")
    
    # 結果が無い場合
    if not all_results:
        print("\n❌ 読み込めたワークスペースがありません。Cursorを閉じてから再実行してください。")
        if not SKIP_ACTIVE:
            print("   または --skip-active オプションを使用して、アクティブなワークスペースのスキップを無効化してください。")
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