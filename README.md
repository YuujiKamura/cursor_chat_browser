# Cursor Chat Browser

Cursorでの会話データを簡単に閲覧・管理するためのツールです。

## 機能

- SQLiteデータベースからCursorのチャットデータを直接抽出
- 抽出したデータをJSON形式で保存
- 会話データをツリービューで表示
- チャットとComposerの両方のデータに対応

## 使用方法

### データの抽出

```
python extract_cursor_chat_v2.py
```

### データの閲覧

```
python cursor_chat_viewer_new.py
```

## 注意事項

- Cursorを閉じてから実行することをお勧めします
- チャットデータには機密情報が含まれる場合があります

## 要件

- Python 3.7以上
- tkinter
- json
- sqlite3 