import json
import os

def check_json_format(file_path):
    """
    JSONファイルの形式をチェックする関数
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            json.load(f)
        return True
    except json.JSONDecodeError as e:
        print(f"JSON形式エラー: {file_path} - {e}")
        return False
    except Exception as e:
        print(f"エラー: {file_path} - {e}")
        return False

if __name__ == "__main__":
    # カレントディレクトリのJSONファイルをチェック
    json_files = [f for f in os.listdir('.') if f.endswith('.json')]
    
    all_valid = True
    for json_file in json_files:
        if not check_json_format(json_file):
            all_valid = False
    
    if all_valid:
        print("すべてのJSONファイルの形式は正しいです。")
    else:
        print("JSON形式エラーがあるファイルが存在します。")
