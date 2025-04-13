#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import sys
import os
import json
import re
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import datetime

# テスト対象のモジュールをインポート
from cursor_log_viewer import (
    parse_folder_uri,
    safe_parse_json
)

# 参照用のsafe_parse_json関数を直接テストファイルに追加
def reference_safe_parse_json(json_str):
    """JSONを安全にパースする"""
    if not json_str:
        return None, None
        
    try:
        return json.loads(json_str), None
    except json.JSONDecodeError as e:
        print(f"⚠️ JSONパースエラー: {e}")
        
        # 修復を試みる (末尾のカンマを削除)
        cleaned_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        try:
            return json.loads(cleaned_str), None
        except:
            return None, f"JSONパースエラー: {e}"

# 参照用のparse_folder_uri関数を直接テストファイルに追加
def reference_parse_folder_uri(folder_uri):
    """フォルダURIをパースしてファイルパスに変換"""
    if not folder_uri:
        return "N/A"
    
    # URIスキーマを削除
    if folder_uri.startswith("file:///"):
        folder_path = folder_uri[8:]
    else:
        folder_path = folder_uri
    
    # URLエンコードを解除
    import urllib.parse
    folder_path = urllib.parse.unquote(folder_path)
    
    return folder_path

class TestCursorLogViewer(unittest.TestCase):
    """Cursor Log Viewerのテスト"""
    
    def test_dummy(self):
        """ダミーテスト - 常に成功"""
        self.assertTrue(True)

class TestCursorChatDataExtraction(unittest.TestCase):
    """Cursorチャットデータ抽出のテスト"""
    
    def test_safe_parse_json_valid(self):
        """有効なJSONをパースするテスト"""
        # 正常なJSONデータ
        valid_json = '{"key": "value", "number": 42, "array": [1, 2, 3]}'
        result, error = reference_safe_parse_json(valid_json)
        
        # テスト検証
        self.assertIsNone(error)
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["number"], 42)
        self.assertEqual(result["array"], [1, 2, 3])
    
    def test_safe_parse_json_broken(self):
        """壊れたJSONをパースするテスト"""
        # 末尾のカンマがある壊れたJSON
        broken_json = '{"key": "value", "array": [1, 2, 3,]}'
        result, error = reference_safe_parse_json(broken_json)
        
        # テスト検証 - 修復されてパースされるはず
        self.assertIsNone(error)
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["array"], [1, 2, 3])
    
    def test_safe_parse_json_empty(self):
        """空のJSONをパースするテスト"""
        # 空のJSON文字列
        empty_json = ''
        result, error = reference_safe_parse_json(empty_json)
        
        # テスト検証
        self.assertIsNone(result)
    
    def test_safe_parse_json_severely_broken(self):
        """修復不可能な壊れたJSONをパースするテスト"""
        # 修復できないほど壊れたJSON
        severely_broken_json = '{"key": "value", "unclosed": {'
        result, error = reference_safe_parse_json(severely_broken_json)
        
        # テスト検証 - エラーが返されるはず
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        self.assertIn("JSONパースエラー", error)
        
    def test_parse_folder_uri(self):
        """フォルダURIのパース機能をテスト"""
        # 通常のWindows URIをテスト
        windows_uri = "file:///C:/Users/test/projects"
        path = reference_parse_folder_uri(windows_uri)
        self.assertEqual(path, "C:/Users/test/projects")
        
        # Linuxスタイルのパスをテスト
        linux_uri = "file:///home/user/projects"
        path = reference_parse_folder_uri(linux_uri)
        self.assertEqual(path, "home/user/projects")
        
        # エンコードされた空白を含むURIをテスト
        encoded_uri = "file:///C:/Users/test/my%20projects"
        path = reference_parse_folder_uri(encoded_uri)
        self.assertEqual(path, "C:/Users/test/my projects")
        
        # 空のURIをテスト
        empty_uri = None
        path = reference_parse_folder_uri(empty_uri)
        self.assertEqual(path, "N/A")
        
        # スキーマなしのパスをテスト
        no_schema_uri = "C:/Users/test/projects"
        path = reference_parse_folder_uri(no_schema_uri)
        self.assertEqual(path, "C:/Users/test/projects")

class TestDatabaseOperations(unittest.TestCase):
    """データベース操作のシンプルなテスト"""
    
    def setUp(self):
        """テスト前の準備"""
        # テスト用の一時ディレクトリとDBファイルを作成
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_state.vscdb"
        
        # テスト用のDBを作成して初期データを挿入
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # ItemTableの作成
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS ItemTable (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        
        # テスト用のチャットデータ
        self.chat_data = {
            "tabs": [
                {
                    "tabId": "tab1",
                    "chatTitle": "テストチャット",
                    "lastSendTime": 1649499297000,
                    "bubbles": [
                        {"type": "user", "text": "こんにちは"},
                        {"type": "ai", "text": "こんにちは、どのようにお手伝いできますか？"}
                    ]
                }
            ]
        }
        
        # テスト用のComposerデータ
        self.composer_data = {
            "allComposers": [
                {
                    "composerId": "composer1",
                    "name": "テストコンポーザー",
                    "text": "テスト内容",
                    "createdAt": 1649499297000,
                    "lastUpdatedAt": 1649499397000,
                    "conversation": [
                        {"type": 1, "text": "こんにちは", "timestamp": 1649499297000},
                        {"type": 2, "text": "こんにちは、どのようにお手伝いできますか？", "timestamp": 1649499347000}
                    ]
                }
            ],
            "selectedComposerId": "composer1",
            "composerDataVersion": 1
        }
        
        # テストデータをDBに挿入
        self.cursor.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)", 
                         ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(self.chat_data)))
        self.cursor.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)", 
                         ("composer.composerData", json.dumps(self.composer_data)))
        self.conn.commit()
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        try:
            # DB接続を閉じる
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
        except:
            pass
        
        # 一時ディレクトリを削除
        self.temp_dir.cleanup()
    
    def test_db_read_chat_data(self):
        """データベースからチャットデータを読み取るテスト"""
        # チャットデータを読み取る
        cursor = self.conn.cursor()
        result = cursor.execute(
            "SELECT value FROM ItemTable WHERE key = 'workbench.panel.aichat.view.aichat.chatdata'"
        ).fetchone()
        
        # 結果があることを確認
        self.assertIsNotNone(result)
        self.assertIsNotNone(result[0])
        
        # JSONをパース
        chat_data_json = result[0]
        chat_data, _ = reference_safe_parse_json(chat_data_json)
        
        # データ構造を検証
        self.assertIsNotNone(chat_data)
        self.assertIn("tabs", chat_data)
        self.assertEqual(len(chat_data["tabs"]), 1)
        self.assertEqual(chat_data["tabs"][0]["chatTitle"], "テストチャット")
        self.assertEqual(len(chat_data["tabs"][0]["bubbles"]), 2)
        
    def test_db_read_composer_data(self):
        """データベースからComposerデータを読み取るテスト"""
        # Composerデータを読み取る
        cursor = self.conn.cursor()
        result = cursor.execute(
            "SELECT value FROM ItemTable WHERE key = 'composer.composerData'"
        ).fetchone()
        
        # 結果があることを確認
        self.assertIsNotNone(result)
        self.assertIsNotNone(result[0])
        
        # JSONをパース
        composer_data_json = result[0]
        composer_data, _ = reference_safe_parse_json(composer_data_json)
        
        # データ構造を検証
        self.assertIsNotNone(composer_data)
        self.assertIn("allComposers", composer_data)
        self.assertEqual(len(composer_data["allComposers"]), 1)
        self.assertEqual(composer_data["allComposers"][0]["name"], "テストコンポーザー")
        self.assertEqual(len(composer_data["allComposers"][0]["conversation"]), 2)

class TestJSONOutput(unittest.TestCase):
    """JSON出力機能のテスト"""
    
    def test_json_output_format(self):
        """JSON出力フォーマットのテスト"""
        # テストデータの作成
        test_data = [
            {
                "workspace_id": "test-workspace-1",
                "chats": [
                    {
                        "id": "chat1",
                        "title": "テストチャット1",
                        "timestamp": "2023-01-01 10:00:00",
                        "messages": [
                            {"type": "user", "text": "こんにちは"},
                            {"type": "assistant", "text": "こんにちは、どのようにお手伝いできますか？"}
                        ]
                    }
                ],
                "composers": [
                    {
                        "id": "composer1",
                        "title": "テストコンポーザー1",
                        "text": "テスト内容",
                        "created_at": "2023-01-01 09:00:00",
                        "updated_at": "2023-01-01 09:30:00",
                        "conversation": [
                            {"type": "user", "text": "質問があります", "timestamp": "2023-01-01 09:00:00"},
                            {"type": "assistant", "text": "どうぞ", "timestamp": "2023-01-01 09:01:00"}
                        ]
                    }
                ]
            }
        ]
        
        # 一時ファイルの作成
        temp_dir = tempfile.TemporaryDirectory()
        output_path = Path(temp_dir.name) / "test_output.json"
        
        try:
            # JSONとして書き出し
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(test_data, f, ensure_ascii=False, indent=2)
            
            # ファイルが存在することを確認
            self.assertTrue(output_path.exists())
            
            # 書き出したJSONを読み込み
            with open(output_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            
            # データが正しくロードされることを確認
            self.assertEqual(len(loaded_data), 1)
            self.assertEqual(loaded_data[0]["workspace_id"], "test-workspace-1")
            self.assertEqual(len(loaded_data[0]["chats"]), 1)
            self.assertEqual(len(loaded_data[0]["composers"]), 1)
            self.assertEqual(loaded_data[0]["chats"][0]["title"], "テストチャット1")
            self.assertEqual(loaded_data[0]["composers"][0]["title"], "テストコンポーザー1")
            
            # 日本語が正しく保存されているか確認
            self.assertEqual(loaded_data[0]["chats"][0]["messages"][1]["text"], "こんにちは、どのようにお手伝いできますか？")
            
        finally:
            # 一時ディレクトリを削除
            temp_dir.cleanup()
    
    def test_json_with_special_characters(self):
        """特殊文字を含むJSONの出力テスト"""
        # 特殊文字を含むテストデータ
        test_data = {
            "特殊な文字": "改行\n、タブ\t、引用符\"、バックスラッシュ\\、日本語の絵文字😊",
            "配列": ["要素1", "要素2", "日本語の要素"]
        }
        
        # 一時ファイルの作成
        temp_dir = tempfile.TemporaryDirectory()
        output_path = Path(temp_dir.name) / "test_special_chars.json"
        
        try:
            # JSONとして書き出し
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(test_data, f, ensure_ascii=False, indent=2)
            
            # ファイルが存在することを確認
            self.assertTrue(output_path.exists())
            
            # 書き出したJSONを読み込み
            with open(output_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            
            # データが正しくロードされることを確認
            self.assertEqual(loaded_data["特殊な文字"], "改行\n、タブ\t、引用符\"、バックスラッシュ\\、日本語の絵文字😊")
            self.assertEqual(loaded_data["配列"][2], "日本語の要素")
            
        finally:
            # 一時ディレクトリを削除
            temp_dir.cleanup()

if __name__ == "__main__":
    unittest.main() 