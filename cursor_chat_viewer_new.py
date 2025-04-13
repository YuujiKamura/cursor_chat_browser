#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import glob
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime
import re

class CursorChatViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Cursor Chat Viewer")
        self.root.geometry("1200x700")
        
        # データの初期化
        self.current_json_data = None
        self.current_json_file = None
        self.json_files = []
        
        # メニューバーの作成
        self.create_menu()
        
        # メインフレームの作成
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左右のペイン分割
        self.paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # 左ペイン（ファイルリスト）
        self.left_frame = ttk.Frame(self.paned_window, width=300)
        self.paned_window.add(self.left_frame, weight=1)
        
        # ファイルリスト
        self.file_list = tk.Listbox(self.left_frame, selectmode=tk.SINGLE)
        self.file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.file_list.bind("<<ListboxSelect>>", self.on_file_select)
        
        # ファイルリストのスクロールバー
        scrollbar = ttk.Scrollbar(self.left_frame, orient="vertical", command=self.file_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_list.configure(yscrollcommand=scrollbar.set)
        
        # 右ペイン（上下分割）
        self.right_frame = ttk.Frame(self.paned_window, width=700)
        self.paned_window.add(self.right_frame, weight=3)
        
        # 右ペインを上下に分割
        self.right_paned = ttk.PanedWindow(self.right_frame, orient=tk.VERTICAL)
        self.right_paned.pack(fill=tk.BOTH, expand=True)
        
        # 上部（ツリービュー）
        self.tree_frame = ttk.Frame(self.right_paned)
        self.right_paned.add(self.tree_frame, weight=1)
        
        # ツリービュー
        self.tree = ttk.Treeview(self.tree_frame, selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # ツリービューのスクロールバー
        tree_scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)
        
        # 下部（メッセージ表示）
        self.text_frame = ttk.Frame(self.right_paned)
        self.right_paned.add(self.text_frame, weight=2)
        
        # テキストウィジェット
        self.text = tk.Text(self.text_frame, wrap=tk.WORD, padx=10, pady=10)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text.config(state=tk.DISABLED)
        
        # テキストのスクロールバー
        text_scrollbar = ttk.Scrollbar(self.text_frame, orient="vertical", command=self.text.yview)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=text_scrollbar.set)
        
        # ステータスバー
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(root, textvariable=self.status_var, anchor=tk.W, relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # スタイル設定
        self.setup_styles()
        
        # 初期表示
        self.populate_file_list()
        
        # ツリービューの列設定
        self.tree["columns"] = ("type", "timestamp")
        self.tree.column("#0", width=300)
        self.tree.column("type", width=100)
        self.tree.column("timestamp", width=150)
        self.tree.heading("#0", text="タイトル")
        self.tree.heading("type", text="種類")
        self.tree.heading("timestamp", text="タイムスタンプ")
    
    def create_menu(self):
        """メニューバーを作成"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # ファイルメニュー
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ファイル", menu=file_menu)
        
        file_menu.add_command(label="JSONファイルを開く", command=self.open_json_file)
        file_menu.add_command(label="JSONデータを抽出", command=self.extract_data)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self.root.quit)
        
        # ヘルプメニュー
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ヘルプ", menu=help_menu)
        
        help_menu.add_command(label="Cursorチャットデータについて", command=self.show_help)
    
    def setup_styles(self):
        """スタイルの設定"""
        self.text.tag_configure("user", foreground="#0066cc", spacing1=10, spacing3=5, font=("Helvetica", 10))
        self.text.tag_configure("assistant", foreground="#006633", spacing1=10, spacing3=5, font=("Helvetica", 10))
        self.text.tag_configure("system", foreground="#666666", spacing1=10, spacing3=5, font=("Helvetica", 10, "italic"))
        self.text.tag_configure("header", font=("Helvetica", 12, "bold"), spacing1=5, spacing3=10)
        self.text.tag_configure("timestamp", foreground="#999999", font=("Helvetica", 9, "italic"))
        
        # リストボックスのスタイル
        self.file_list.configure(font=("Helvetica", 9))
        self.file_list.configure(selectmode=tk.SINGLE)
        self.file_list.configure(activestyle="none")
        self.file_list.configure(highlightthickness=1)
        self.file_list.configure(selectbackground="#0078d7")
        self.file_list.configure(selectforeground="white")
    
    def populate_file_list(self):
        """jsonディレクトリ内のJSONファイルをリスト表示"""
        json_dir = Path("./json")
        if json_dir.exists():
            # ファイルリストをクリア
            self.json_files = []
            self.file_list.delete(0, tk.END)
            
            # JSONファイルを取得
            json_files = list(json_dir.glob("*.json"))
            # 更新日時順からファイル名順に変更
            json_files.sort(key=lambda x: x.name)
            
            # 重複を除去
            seen_files = set()
            for file in json_files:
                if file.name not in seen_files:
                    seen_files.add(file.name)
                    self.json_files.append(file)
                    
                    # ファイル名から情報を抽出
                    filename = file.name
                    timestamp = datetime.fromtimestamp(os.path.getmtime(file))
                    formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    
                    try:
                        with open(file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            workspace_id = data.get("workspace_id", "Unknown")
                            workspace_path = data.get("workspace_path", "Unknown")
                            chat_count = len(data.get("chats", []))
                            composer_count = len(data.get("composers", []))
                            
                            # パスを短縮
                            if workspace_path != "Unknown":
                                workspace_path = Path(workspace_path).name
                            
                            # 表示用の文字列を作成
                            display_text = f"[{filename}] "
                            display_text += f"チャット: {chat_count}件, Composer: {composer_count}件"
                            
                            self.file_list.insert(tk.END, display_text)
                    except Exception as e:
                        # ファイルが読み込めない場合は基本情報のみ表示
                        self.file_list.insert(tk.END, f"[{formatted_time}] {filename}")
                        print(f"ファイル読み込みエラー: {file} - {e}")
            
            if not self.json_files:
                self.status_var.set("JSONファイルが見つかりません。")
        else:
            self.status_var.set("jsonディレクトリが見つかりません。")
            print("jsonディレクトリが見つかりません。")
    
    def open_json_file(self):
        """JSONファイルを開くダイアログ"""
        filetypes = [("JSONファイル", "*.json"), ("すべてのファイル", "*.*")]
        filepath = filedialog.askopenfilename(
            title="JSONファイルを選択",
            filetypes=filetypes,
            initialdir="./json" if os.path.exists("./json") else "."
        )
        
        if filepath:
            self.load_json_file(filepath)
    
    def load_json_file(self, filepath):
        """JSONファイルを読み込んで表示"""
        try:
            file_size = os.path.getsize(filepath)
            print(f"ファイルサイズ: {filepath} - {file_size} バイト")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            self.current_json_file = filepath
            self.current_json_data = json_data
            
            # ツリービューをクリア
            self.tree.delete(*self.tree.get_children())
            
            # テキスト表示をクリア
            self.clear_text()
            
            # ワークスペース情報を表示
            workspace_id = json_data.get("workspace_id", "Unknown")
            workspace_path = json_data.get("workspace_path", "Unknown")
            workspace_node = self.tree.insert("", "end", text=f"ワークスペース: {workspace_id}", 
                                           values=("workspace", ""))
            
            # ワークスペースのパスを表示
            self.tree.insert(workspace_node, "end", text=f"パス: {workspace_path}", 
                           values=("workspace_path", ""))
            
            # チャットを表示
            chats = json_data.get("chats", [])
            if chats:
                chats_node = self.tree.insert(workspace_node, "end", text=f"チャット ({len(chats)}件)", 
                                            values=("chats_folder", ""))
                for chat in chats:
                    title = chat.get("title", "無題")
                    chat_id = chat.get("id", "")
                    timestamp = chat.get("timestamp", "")
                    self.tree.insert(chats_node, "end", text=title, values=("chat", timestamp),
                                   iid=chat_id)
            
            # Composerを表示
            composers = json_data.get("composers", [])
            if composers:
                composers_node = self.tree.insert(workspace_node, "end", text=f"Composer ({len(composers)}件)", 
                                                values=("composers_folder", ""))
                for composer in composers:
                    title = composer.get("title", "無題")
                    composer_id = composer.get("id", "")
                    timestamp = composer.get("timestamp", "")
                    self.tree.insert(composers_node, "end", text=title, 
                                   values=("composer", timestamp), iid=composer_id)
            
            # ステータス更新
            self.status_var.set(f"読み込み完了: {filepath}")
            
        except Exception as e:
            messagebox.showerror("エラー", f"JSONファイルの読み込みエラー: {e}")
            self.status_var.set(f"エラー: {e}")
    
    def clear_text(self):
        """テキスト表示をクリア"""
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.config(state=tk.DISABLED)
    
    def on_file_select(self, event):
        """ファイルリストのアイテムが選択されたときの処理"""
        selected_index = self.file_list.curselection()
        if selected_index:
            filepath = str(self.json_files[selected_index[0]])
            self.load_json_file(filepath)
    
    def show_help(self):
        """ヘルプダイアログを表示"""
        help_text = """
Cursor Chat Viewer

このビューアは、extract_cursor_chat_v2.pyによって生成されたJSONファイルを
表示するためのツールです。

使用方法:
1. 左側のファイルリストからJSONファイルを選択
2. 右側にJSONファイルの内容が表示されます
4. 検索ボックスを使用して特定のチャットを検索できます

※ json/フォルダに
   workspace_*.json形式のファイルがある場合、
   自動的にファイルリストが更新されます。
"""
        messagebox.showinfo("ヘルプ", help_text)

    def extract_data(self):
        """JSONデータを抽出するextract_cursor_chat_v2.pyを実行"""
        try:
            import subprocess
            # ユーザーに確認
            result = messagebox.askquestion("確認", "Cursorチャットデータを抽出しますか?\n(Cursorを終了してから実行することをお勧めします)")
            if result == "yes":
                self.status_var.set("データ抽出中...")
                self.root.update()
                
                # Pythonスクリプトを実行
                process = subprocess.Popen(["python", "extract_cursor_chat_v2.py"], 
                                          stdout=subprocess.PIPE, 
                                          stderr=subprocess.PIPE,
                                          text=True)
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    # 成功した場合、最新のJSONを読み込む
                    self.status_var.set("データ抽出完了。JSONを読み込んでいます...")
                    self.root.update()
                    self.populate_file_list()
                else:
                    # エラーがあった場合
                    error_msg = stderr if stderr else "不明なエラーが発生しました"
                    messagebox.showerror("抽出エラー", f"データの抽出中にエラーが発生しました:\n{error_msg}")
                    self.status_var.set(f"抽出エラー: {error_msg[:50]}...")
        except Exception as e:
            messagebox.showerror("エラー", f"スクリプト実行エラー: {e}")
            self.status_var.set(f"エラー: {e}")

    def on_tree_select(self, event):
        """ツリービューのアイテムが選択されたときの処理"""
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        item = selected_item[0]
        item_type = self.tree.item(item, "values")[0]
        
        # テキスト表示をクリア
        self.clear_text()
        
        if item_type == "composer":
            # コンポーザーの詳細を表示
            composer_data = self.find_composer_by_id(item)
            if composer_data:
                self.display_composer_detail(composer_data)
        elif item_type == "chat":
            # チャットの詳細を表示
            chat_data = self.find_chat_by_id(item)
            if chat_data:
                self.display_chat_detail(chat_data)

    def find_composer_by_id(self, composer_id):
        """コンポーザーIDからデータを検索"""
        if not self.current_json_data:
            return None
        
        composers = self.current_json_data.get("composers", [])
        for composer in composers:
            if composer.get("id") == composer_id:
                return composer
        return None

    def find_chat_by_id(self, chat_id):
        """チャットIDからデータを検索"""
        if not self.current_json_data:
            return None
        
        chats = self.current_json_data.get("chats", [])
        for chat in chats:
            if chat.get("id") == chat_id:
                return chat
        return None

    def display_composer_detail(self, composer):
        """コンポーザーの詳細を表示"""
        self.text.config(state=tk.NORMAL)
        
        title = composer.get("title", "無題")
        self.text.insert(tk.END, f"コンポーザー: {title}\n\n", "header")
        
        conversation = composer.get("conversation", [])
        if conversation:
            for msg in conversation:
                msg_type = msg.get("type", "unknown")
                msg_text = msg.get("text", "")
                msg_timestamp = msg.get("timestamp", "")
                
                if msg_type == "user":
                    self.text.insert(tk.END, "👤 ユーザー: ", "user")
                elif msg_type == "assistant":
                    self.text.insert(tk.END, "🤖 アシスタント: ", "assistant")
                else:
                    self.text.insert(tk.END, f"⚙️ {msg_type}: ", "system")
                
                self.text.insert(tk.END, f"{msg_text}\n")
                if msg_timestamp:
                    self.text.insert(tk.END, f"時間: {msg_timestamp}\n", "timestamp")
                self.text.insert(tk.END, "\n")
        
        self.text.config(state=tk.DISABLED)

    def display_chat_detail(self, chat):
        """チャットの詳細を表示"""
        self.text.config(state=tk.NORMAL)
        
        title = chat.get("title", "無題")
        self.text.insert(tk.END, f"チャット: {title}\n\n", "header")
        
        messages = chat.get("messages", [])
        if messages:
            for message in messages:
                msg_type = message.get("type", "unknown")
                msg_text = message.get("text", "")
                msg_timestamp = message.get("timestamp", "")
                
                if msg_type == "user":
                    self.text.insert(tk.END, "👤 ユーザー: ", "user")
                elif msg_type == "assistant":
                    self.text.insert(tk.END, "🤖 アシスタント: ", "assistant")
                else:
                    self.text.insert(tk.END, f"⚙️ {msg_type}: ", "system")
                
                self.text.insert(tk.END, f"{msg_text}\n")
                if msg_timestamp:
                    self.text.insert(tk.END, f"時間: {msg_timestamp}\n", "timestamp")
                self.text.insert(tk.END, "\n")
        
        self.text.config(state=tk.DISABLED)

def main():
    root = tk.Tk()
    app = CursorChatViewer(root)
    root.mainloop()

if __name__ == "__main__":
    main() 