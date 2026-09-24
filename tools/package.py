#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
package.py — 把 travel-roadbook/ 打包成可上传的技能 zip

用法:
    python3 tools/package.py [输出.zip]     # 默认 dist/travel-roadbook.zip

zip 顶层是 travel-roadbook/ 目录（SKILL.md 在其中），在 claude.ai 的技能设置里上传即可；
排除 __pycache__、.pyc、.DS_Store 和隐藏目录等本地文件。
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = "travel-roadbook"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", SKILL + ".zip")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, SKILL)):
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__" and not d.startswith("."))
            for name in sorted(filenames):
                if name.endswith(".pyc") or name.startswith("."):
                    continue
                path = os.path.join(dirpath, name)
                z.write(path, os.path.relpath(path, ROOT))
                count += 1
    print("saved: %s（%d 个文件）" % (out, count))


if __name__ == "__main__":
    main()
