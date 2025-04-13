#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cursor-chat-browser",
    version="1.0.0",
    author="Cursor Chat Browser Team",
    description="Cursorでの会話データを簡単に閲覧・管理するためのツール",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/username/cursor-chat-browser",
    packages=["src"] + ["src." + p for p in find_packages(where="src")],
    package_dir={"": "."},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "pathlib>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "extract-cursor-chat=extract_cursor_chat_v2:main",
            "cursor-chat-viewer=cursor_chat_viewer_new:main",
        ],
    },
) 