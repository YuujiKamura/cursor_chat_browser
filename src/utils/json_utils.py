#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re

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