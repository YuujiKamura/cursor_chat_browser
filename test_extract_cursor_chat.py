#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
import sqlite3
import shutil
from pathlib import Path
import tempfile
import json
from unittest.mock import patch, MagicMock
import platform
import time
import re

# テスト対象のモジュールをインポート
import extract_cursor_chat_v2

class TestExtractCursorChat(unittest.TestCase):
    
    def setUp(self):
        """テスト前の準備"""
        # 一時ディレクトリを作成
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_db.vscdb"
        
        # テスト用のデータベースを作成
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        cursor.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        
        # AIチャット用のテストデータ
        chat_data = {
            "tabs": [
                {
                    "tabId": "test_tab_1",
                    "chatTitle": "Test Chat 1",
                    "lastSendTime": 1616161616161,
                    "bubbles": [
                        {"type": "user", "text": "こんにちは"},
                        {"type": "assistant", "text": "Hello!"}
                    ]
                }
            ]
        }
        
        # Composer用のテストデータ
        composer_data = {
            "allComposers": [
                {
                    "composerId": "test_composer_1",
                    "name": "Test Composer",
                    "text": "Test composer content",
                    "createdAt": 1616161616161,
                    "lastUpdatedAt": 1616161616161,
                    "conversation": [
                        {"type": 1, "text": "ユーザーメッセージ", "timestamp": 1616161616161},
                        {"type": 2, "text": "アシスタントの回答", "timestamp": 1616161616162}
                    ]
                }
            ]
        }
        
        # データをデータベースに挿入
        cursor.execute(
            "INSERT INTO ItemTable VALUES (?, ?)",
            ('workbench.panel.aichat.view.aichat.chatdata', json.dumps(chat_data))
        )
        cursor.execute(
            "INSERT INTO ItemTable VALUES (?, ?)",
            ('composer.composerData', json.dumps(composer_data))
        )
        
        self.conn.commit()
        cursor.close()
        
        # jsonディレクトリを作成
        self.json_dir = Path(self.temp_dir) / "json"
        self.json_dir.mkdir(exist_ok=True)
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        # データベース接続を確実に閉じる
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
            except:
                pass
        
        # 少し待って、ファイルロックが解除されるようにする
        time.sleep(0.1)
        
        # 一時ディレクトリを削除（複数回試行）
        for _ in range(3):
            try:
                shutil.rmtree(self.temp_dir)
                break
            except PermissionError:
                # ファイルがロックされている場合は少し待って再試行
                time.sleep(0.5)
            except Exception as e:
                print(f"クリーンアップ中のエラー: {e}")
                break
    
    def test_get_db_connection_success(self):
        """DB接続成功のテスト"""
        conn = extract_cursor_chat_v2.get_db_connection(self.db_path)
        self.assertIsNotNone(conn)
        conn.close()
    
    def test_get_db_connection_nonexistent(self):
        """存在しないDBへの接続テスト"""
        nonexistent_path = Path(self.temp_dir) / "nonexistent.db"
        conn = extract_cursor_chat_v2.get_db_connection(nonexistent_path)
        self.assertIsNone(conn)
    
    def test_get_db_connection_locked(self):
        """ロックされたDBへの接続テスト"""
        # 別のテスト用DBファイルを作成（メインのテストDBは他のテストで使用）
        lock_db_path = Path(self.temp_dir) / "lock_test.db"
        
        # 新しい接続を作成
        lock_conn = sqlite3.connect(str(lock_db_path))
        try:
            # ロックを取得
            cursor = lock_conn.cursor()
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
            
            # ロックされた状態でテスト対象の関数を呼び出す
            conn = extract_cursor_chat_v2.get_db_connection(lock_db_path)
            
            # ロックされたDBには接続できないはず
            self.assertIsNone(conn)
        finally:
            # 確実にロックを解除して接続を閉じる
            try:
                cursor.close()
                lock_conn.rollback()
                lock_conn.close()
            except:
                pass  # エラーは無視
    
    def test_safe_parse_json_valid(self):
        """有効なJSONのパースのテスト"""
        valid_json = '{"key": "value"}'
        result, error = extract_cursor_chat_v2.safe_parse_json(valid_json)
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")
        self.assertIsNone(error)
    
    def test_safe_parse_json_broken(self):
        """壊れたJSONのパースのテスト (末尾にカンマ)"""
        broken_json = '{"key": "value",}'
        result, error = extract_cursor_chat_v2.safe_parse_json(broken_json)
        self.assertIsNotNone(result)  # 修復されるはず
        self.assertEqual(result["key"], "value")
        self.assertIsNone(error)
    
    def test_safe_parse_json_invalid(self):
        """無効なJSONのパースのテスト"""
        invalid_json = '{"key": value"}'  # 引用符が不足
        result, error = extract_cursor_chat_v2.safe_parse_json(invalid_json)
        self.assertIsNone(result)
        self.assertIsNotNone(error)
    
    def test_extract_chat_data(self):
        """チャットデータの抽出テスト"""
        result = extract_cursor_chat_v2.get_chat_data("test_workspace", self.db_path)
        self.assertIsNotNone(result)
        self.assertEqual(result["workspace_id"], "test_workspace")
        self.assertEqual(len(result["chats"]), 1)
        self.assertEqual(len(result["composers"]), 1)
    
    @patch('platform.system')
    def test_get_workspace_storage_dir(self, mock_system):
        """ワークスペースストレージディレクトリの取得テスト"""
        # Windowsの場合
        mock_system.return_value = "Windows"
        with patch.dict('os.environ', {'APPDATA': self.temp_dir}):
            result = extract_cursor_chat_v2.get_workspace_storage_dir()
            expected = Path(self.temp_dir) / "Cursor" / "User" / "workspaceStorage"
            self.assertEqual(result, expected)
        
        # macOSの場合
        mock_system.return_value = "Darwin"
        with patch('pathlib.Path.home', return_value=Path('/Users/testuser')):
            result = extract_cursor_chat_v2.get_workspace_storage_dir()
            expected = Path('/Users/testuser/Library/Application Support/Cursor/User/workspaceStorage')
            self.assertEqual(result, expected)
    
    def test_save_json_file(self):
        """JSONファイルの保存テスト"""
        with patch('extract_cursor_chat_v2.get_workspace_storage_dir') as mock_get_dir:
            # ワークスペースディレクトリのモック
            mock_workspace_dir = Path(self.temp_dir) / "workspaceStorage"
            mock_workspace_dir.mkdir(parents=True, exist_ok=True)
            mock_get_dir.return_value = mock_workspace_dir
            
            # テスト用のデータベースをコピー
            workspace_path = mock_workspace_dir / "test_workspace"
            workspace_path.mkdir(exist_ok=True)
            test_db_path = workspace_path / "state.vscdb"
            shutil.copy(self.db_path, test_db_path)
            
            # プロセスチェックをモック - Cursorが実行されていないようにする
            with patch('extract_cursor_chat_v2.platform.system', return_value="Windows"):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(stdout="")  # Cursorが実行されていないと仮定
                    
                    # Cursorプロセスチェックの結果をモック
                    with patch('os.popen') as mock_popen:
                        mock_popen.return_value = MagicMock(read=lambda: "")  # 空の結果を返す
                        
                        # 自動的に保存するよう修正
                        with patch('builtins.input', return_value='y'):  # 保存確認の「y」を自動入力
                            
                            # 出力をキャプチャしてエラーメッセージを検出
                            import io
                            from contextlib import redirect_stdout
                            
                            captured_output = io.StringIO()
                            with redirect_stdout(captured_output):
                                # main関数を実行
                                extract_cursor_chat_v2.main()
                            
                            # 出力を取得
                            output = captured_output.getvalue()
                            # エラーメッセージがあるかチェック
                            self.assertNotIn("ファイル削除エラー", output, "JSONファイル削除中にエラーが発生しました")
                            self.assertNotIn("ディレクトリ削除エラー", output, "JSONディレクトリ削除中にエラーが発生しました")
                            
                            # jsonディレクトリの作成を確認
                            json_dir = Path("./json")
                            self.assertTrue(json_dir.exists(), "JSONディレクトリが作成されていません")
                            
                            # ワークスペース別JSONファイルの存在も確認
                            workspace_json_files = list(json_dir.glob("ws_*.json"))
                            self.assertTrue(len(workspace_json_files) > 0, "ワークスペース別JSONファイルが作成されていません")
                            
                            # JSONファイルの内容を確認
                            if workspace_json_files:
                                with open(workspace_json_files[0], 'r', encoding='utf-8') as f:
                                    try:
                                        json_data = json.load(f)
                                        self.assertIn("workspace_id", json_data, "JSONファイルに必要なデータがありません")
                                    except json.JSONDecodeError:
                                        self.fail("生成されたJSONファイルが有効なJSON形式ではありません")
                            
                            # 後始末: 生成されたJSONファイルをすべて削除
                            errors = []
                            # ワークスペース別JSONファイルの削除
                            for f in workspace_json_files:
                                try:
                                    f.unlink()
                                except Exception as e:
                                    errors.append(f"ワークスペースJSONファイル削除エラー: {e}")
                            
                            # エラーがあれば失敗
                            if errors:
                                self.fail(f"ファイル削除中にエラーが発生しました: {', '.join(errors)}")
                            
                            # 空になったjsonディレクトリも削除
                            try:
                                if json_dir.exists():
                                    remaining_files = list(json_dir.glob("*"))
                                    if not remaining_files:  # ディレクトリが空の場合のみ削除
                                        json_dir.rmdir()
                            except Exception as e:
                                self.fail(f"jsonディレクトリ削除エラー: {e}")

    def test_created_at_extraction(self):
        """created_atが正しく取得できるかをテスト"""
        # テスト用の一時ディレクトリを作成
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test.db"
        
        try:
            # テスト用のデータベースを作成
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # テーブルを作成
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ItemTable (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # テストデータを挿入
            test_data = {
                "tabs": [
                    {
                        "tabId": "test-tab-1",
                        "chatTitle": "Test Chat 1",
                        "created_at": 1625097600,  # 2021-07-01 12:00:00
                        "lastSendTime": 1625097600000,
                        "bubbles": [
                            {
                                "type": "user",
                                "text": "Hello",
                                "timestamp": 1625097600000
                            }
                        ]
                    }
                ]
            }
            
            # データを挿入
            cursor.execute(
                "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(test_data))
            )
            
            conn.commit()
            conn.close()
            
            # データを取得
            result = extract_cursor_chat_v2.get_chat_data("test_workspace", db_path)
            
            # テスト
            self.assertIsNotNone(result)
            self.assertEqual(result["chats"][0]["created_at"], 1625097600, "最初のチャットのcreated_atが一致しません")
            
        finally:
            # クリーンアップ
            shutil.rmtree(temp_dir)

    def test_workspace_path_processing(self):
        """ワークスペースパスの処理をテスト"""
        # 様々な形式のワークスペースパスをテスト
        test_paths = [
            # 標準的なパス
            "C:\\Users\\test\\project",
            # 長いパス
            "C:\\Users\\test\\very\\long\\path\\with\\many\\directories\\project_name_that_is_extremely_long_and_might_cause_issues",
            # 非ASCII文字を含むパス
            "C:\\Users\\test\\プロジェクト\\テスト",
            # 特殊文字を含むパス
            "C:\\Users\\test\\project!@#$%^&()_+{}[]",
            # URLエンコードされたパス
            "C:\\Users\\test\\%E3%83%97%E3%83%AD%E3%82%B8%E3%82%A7%E3%82%AF%E3%83%88",
            # 異なるOS形式のパス
            "/home/user/projects/test_project",
            # 空白を含むパス
            "C:\\Users\\test\\My Project Name"
        ]
        
        # テスト用のデータを作成
        test_data = {
            "workspace_id": "test-workspace-123",
            "workspace_path": "",  # これはテスト中に設定
            "chats": [
                {
                    "id": "test-chat-1",
                    "title": "Test Chat",
                    "created_at": 1625097600  # 2021-07-01 12:00:00
                }
            ],
            "composers": []
        }
        
        for path in test_paths:
            # ワークスペースパスを設定
            test_data["workspace_path"] = path
            
            # save_json_file関数をテスト
            with self.subTest(path=path):
                try:
                    # 一時ディレクトリを作成
                    temp_json_dir = Path("./json")
                    temp_json_dir.mkdir(exist_ok=True)
                    
                    # ファイルを保存
                    workspace_file, _ = extract_cursor_chat_v2.save_json_file(
                        test_data, 
                        test_data["workspace_id"], 
                        len(test_data["chats"]), 
                        len(test_data["composers"])
                    )
                    
                    # ファイルが作成されたことを確認
                    self.assertIsNotNone(workspace_file, f"パス '{path}' に対してファイルが作成されませんでした")
                    self.assertTrue(os.path.exists(workspace_file), f"ファイルが存在しません: {workspace_file}")
                    
                    # ファイル名の長さが許容範囲内かチェック
                    filename = os.path.basename(workspace_file)
                    self.assertLessEqual(len(filename), 200, f"ファイル名が長すぎます: {len(filename)} 文字")
                    
                    # ファイル名に許可されていない文字が含まれていないことをチェック
                    self.assertTrue(re.match(r'^[\w\-\.]+$', filename), f"ファイル名に無効な文字が含まれています: {filename}")
                    
                    # ファイル名が新しいフォーマットに従っているかチェック
                    self.assertTrue(filename.startswith("ws_"), f"ファイル名が正しいフォーマットではありません: {filename}")
                    
                    # JSONデータが正しく保存されたことを確認
                    with open(workspace_file, 'r', encoding='utf-8') as f:
                        saved_data = json.load(f)
                        self.assertEqual(saved_data["workspace_id"], test_data["workspace_id"], "ワークスペースIDが一致しません")
                    
                    # ファイルを削除
                    os.unlink(workspace_file)
                    
                except Exception as e:
                    self.fail(f"パス '{path}' の処理中にエラーが発生しました: {e}")
        
        # テスト後の後片付け
        try:
            if temp_json_dir.exists() and not any(temp_json_dir.iterdir()):
                temp_json_dir.rmdir()
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main() 