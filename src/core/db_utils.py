#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import os
from pathlib import Path
import json
from contextlib import contextmanager
import platform

def get_db_path(workspace_path):
    """
    指定されたワークスペースパスからデータベースファイルのパスを取得する
    
    Args:
        workspace_path: Cursorワークスペースのパス
        
    Returns:
        Path: データベースファイルのパス
    """
    workspace = Path(workspace_path)
    # データベースは通常ワークスペース内の.cursor/cursor.dbに存在する
    db_path = workspace / ".cursor" / "cursor.db"
    
    if not db_path.exists():
        raise FileNotFoundError(f"データベースファイルが見つかりません: {db_path}")
        
    return db_path

@contextmanager
def db_connect(db_path):
    """
    データベースへの接続を提供するコンテキストマネージャー
    
    Args:
        db_path: データベースファイルのパス
        
    Yields:
        sqlite3.Connection: データベース接続オブジェクト
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # 列名でアクセスできるようにする
        yield conn
    except sqlite3.Error as e:
        print(f"データベース接続エラー: {e}")
        raise
    finally:
        if conn:
            conn.close()

def execute_query(conn, query, params=()):
    """
    SQLクエリを実行し、結果を取得する
    
    Args:
        conn: データベース接続オブジェクト
        query: 実行するSQLクエリ
        params: クエリパラメータ (デフォルトは空タプル)
        
    Returns:
        list: クエリの結果行のリスト
    """
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"クエリ実行エラー: {e}")
        print(f"クエリ: {query}")
        print(f"パラメータ: {params}")
        return []

def execute_query_one(conn, query, params=()):
    """
    SQLクエリを実行し、最初の結果行を取得する
    
    Args:
        conn: データベース接続オブジェクト
        query: 実行するSQLクエリ
        params: クエリパラメータ (デフォルトは空タプル)
        
    Returns:
        sqlite3.Row: 最初の結果行、または結果がない場合はNone
    """
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"クエリ実行エラー: {e}")
        print(f"クエリ: {query}")
        print(f"パラメータ: {params}")
        return None

def get_chat_data(workspace_path):
    """
    指定されたワークスペースからチャットデータを取得する
    
    Args:
        workspace_path: Cursorワークスペースのパス
        
    Returns:
        dict: チャットとコンポーザーデータを含む辞書
    """
    try:
        db_path = get_db_path(workspace_path)
        
        chats = []
        composers = []
        
        with db_connect(db_path) as conn:
            # チャットを取得
            chat_rows = execute_query(conn, "SELECT * FROM chats ORDER BY created_at DESC")
            for row in chat_rows:
                chat_data = dict(row)
                # バイナリJSONデータを解析
                if 'data' in chat_data and chat_data['data']:
                    try:
                        chat_data['data'] = json.loads(chat_data['data'])
                    except:
                        chat_data['data'] = None
                chats.append(chat_data)
            
            # コンポーザーを取得
            composer_rows = execute_query(conn, "SELECT * FROM composers ORDER BY created_at DESC")
            for row in composer_rows:
                composer_data = dict(row)
                # バイナリJSONデータを解析
                if 'data' in composer_data and composer_data['data']:
                    try:
                        composer_data['data'] = json.loads(composer_data['data'])
                    except:
                        composer_data['data'] = None
                composers.append(composer_data)
        
        return {
            "chats": chats,
            "composers": composers
        }
    except Exception as e:
        print(f"チャットデータ取得エラー: {e}")
        return {"chats": [], "composers": []}

def get_chat_by_id(workspace_path, chat_id):
    """
    指定されたチャットIDのチャットデータを取得する
    
    Args:
        workspace_path: Cursorワークスペースのパス
        chat_id: 取得するチャットのID
        
    Returns:
        dict: チャットデータの辞書、見つからない場合はNone
    """
    try:
        db_path = get_db_path(workspace_path)
        
        with db_connect(db_path) as conn:
            chat_row = execute_query_one(conn, "SELECT * FROM chats WHERE id = ?", (chat_id,))
            if not chat_row:
                return None
                
            chat_data = dict(chat_row)
            # バイナリJSONデータを解析
            if 'data' in chat_data and chat_data['data']:
                try:
                    chat_data['data'] = json.loads(chat_data['data'])
                except:
                    chat_data['data'] = None
            
            return chat_data
    except Exception as e:
        print(f"チャットデータ取得エラー: {e}")
        return None

def get_composer_by_id(workspace_path, composer_id):
    """
    指定されたコンポーザーIDのデータを取得する
    
    Args:
        workspace_path: Cursorワークスペースのパス
        composer_id: 取得するコンポーザーのID
        
    Returns:
        dict: コンポーザーデータの辞書、見つからない場合はNone
    """
    try:
        db_path = get_db_path(workspace_path)
        
        with db_connect(db_path) as conn:
            composer_row = execute_query_one(conn, "SELECT * FROM composers WHERE id = ?", (composer_id,))
            if not composer_row:
                return None
                
            composer_data = dict(composer_row)
            # バイナリJSONデータを解析
            if 'data' in composer_data and composer_data['data']:
                try:
                    composer_data['data'] = json.loads(composer_data['data'])
                except:
                    composer_data['data'] = None
            
            return composer_data
    except Exception as e:
        print(f"コンポーザーデータ取得エラー: {e}")
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
                try:
                    # まず読み取り専用テスト
                    with open(db_path, 'rb') as f:
                        pass
                    
                    # 次に書き込みテスト - ロックされていたらここで例外が発生する
                    file_handle = open(db_path, 'ab+')
                    try:
                        # 明示的なロックの確認 - 0バイト目から1バイト分をロック試行
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except (IOError, OSError) as e:
                        file_handle.close()
                        print(f"⚠️ データベースファイルがロックされています: {db_path} - {e}")
                        return None
                    file_handle.close()
                except (IOError, OSError, PermissionError) as e:
                    print(f"⚠️ データベースがロック/使用中です: {db_path} - {e}")
                    return None
            except Exception as e:
                print(f"⚠️ ファイルロックチェック中にエラー: {db_path} - {e}")
                return None
        else:
            # macOS/Linuxではfcntlを使用してロックをチェック
            try:
                import fcntl
                try:
                    with open(db_path, 'r') as f:
                        try:
                            # 非排他的ロックを試みる (読み取り専用)
                            fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                            # ロックを解除
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except (IOError, OSError) as e:
                            print(f"⚠️ データベースがロック/使用中です: {db_path} - {e}")
                            return None
                except (IOError, OSError, PermissionError) as e:
                    print(f"⚠️ データベースファイルが開けません: {db_path} - {e}")
                    return None
            except ImportError:
                # fcntlが使用できない場合は別の方法を試す
                try:
                    # 読み取り専用モードで開いてみる
                    with open(db_path, 'rb') as f:
                        pass
                except (IOError, OSError, PermissionError) as e:
                    print(f"⚠️ データベースファイルが開けません: {db_path} - {e}")
                    return None
    except Exception as e:
        print(f"⚠️ データベースのロックチェック中にエラー: {e}")
        # 安全のためここでリターン
        return None
        
    # 4. SQLiteの実行時チェック - エラーハンドリング強化
    try:
        # まずread-onlyモードで試行 (タイムアウト短め)
        try:
            # URIパラメータを使用して読み取り専用モードで開く
            conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True, timeout=1.0)
            
            # 接続のテスト
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()  # 実際にデータを取得
            cursor.close()
            return conn
        except sqlite3.OperationalError as e:
            # ロックされている場合
            if "database is locked" in str(e):
                print(f"⚠️ データベースがロックされています: {db_path} - {e}")
                return None
            # テーブルがない場合は接続自体は成功しているので問題なし
            elif "no such table" in str(e).lower():
                return conn
            # データベースが開けない
            elif "unable to open database file" in str(e).lower():
                print(f"⚠️ データベースが開けません: {db_path} - {e}")
                return None
            # その他のエラー
            else:
                print(f"⚠️ データベース接続エラー: {e}")
                return None
                
        # 代替方法: 文字列の直接パスでの接続を試行
        except Exception as e1:
            try:
                # URIなしで直接接続を試行
                print(f"⚠️ URI接続に失敗、直接接続を試行します: {e1}")
                conn = sqlite3.connect(str(db_path), timeout=0.5)
                cursor = conn.cursor()
                cursor.execute("PRAGMA query_only = true")  # 読み取り専用モードを設定
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return conn
            except Exception as e2:
                print(f"❌ 両方の接続方法に失敗しました: {e1}, {e2}")
                return None
                
    except Exception as e:
        print(f"❌ DBへの接続に失敗しました: {e}")
        return None

@contextmanager
def safe_db_connection(db_path):
    """安全なデータベース接続のコンテキストマネージャ"""
    conn = None
    try:
        conn = get_db_connection(db_path)
        if conn:
            yield conn
        else:
            yield None
    except Exception as e:
        print(f"❌ データベース操作中にエラー: {e}")
        yield None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass 