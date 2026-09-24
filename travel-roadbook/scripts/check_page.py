#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_page.py — 路书网页自检（脚本语法、手机宽度、浅色/深色、链接）

用法:
    python3 check_page.py <路书.html> [--shots 截图目录]
    python3 check_page.py <路书.html> --js-only     # 只查脚本语法，deploy.sh 发布前会调用

1. 脚本语法（不需要浏览器）：内联 <script> 逐个跑 `node --check`，常见错误是单引号字符串里的
   撇号没转义（'Wombat's'、'All'Arco'）；<script type="application/json"> 数据块用 JSON 解析校验。
   没装 node 时跳过这一项并提示。
2. 页面检查（需要 Playwright + Chromium）：以 375×812 手机视口分别在浅色、深色模式打开页面，检查
   横向滚动（列出超出屏幕的元素）、控制台报错、链接协议（只允许 https://、amapuri://、tel:、
   mailto:、页内锚点），并保存两张整页截图（默认与 HTML 同目录），打开看排版和深色模式是否可读。

退出码: 0 通过；1 发现问题；2 参数错误；3 没有 Playwright 或浏览器，跳过页面检查（脚本语法已查）。
依赖: node（脚本语法）；pip install playwright && python -m playwright install chromium（页面检查）
      浏览器装在别处时，用环境变量 CHROMIUM_PATH 指定可执行文件。
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ALLOWED_LINKS = ("https://", "amapuri://", "tel:", "mailto:", "#")
JS_TYPES = ("", "text/javascript", "application/javascript", "module")
JSON_TYPES = ("application/json", "application/ld+json")

PROBE = r"""() => {
  const de = document.documentElement, vw = de.clientWidth, wide = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width && r.right > vw + 1) {
      const cls = typeof el.className === 'string' && el.className.trim()
        ? '.' + el.className.trim().split(/\s+/).join('.') : '';
      wide.push(el.tagName.toLowerCase() + cls);
    }
  }
  return {
    scrollWidth: de.scrollWidth, clientWidth: vw, wide: wide.slice(0, 8),
    links: [...document.querySelectorAll('a')].map(a => a.getAttribute('href') || ''),
    bodyBg: getComputedStyle(document.body).backgroundColor,
  };
}"""


def node_error(stderr, path):
    """从 node --check 的输出里取出行号、出错代码和错误信息。"""
    lines = stderr.splitlines()
    loc = next((i for i, l in enumerate(lines) if l.startswith(path + ":")), None)
    lineno = lines[loc].rsplit(":", 1)[-1] if loc is not None else "?"
    code = lines[loc + 1].strip()[:80] if loc is not None and loc + 1 < len(lines) else ""
    err = next((l.strip() for l in lines if re.match(r"\s*\w*Error\b", l)), lines[-1].strip() if lines else "")
    return lineno, code, err


def check_scripts(html):
    """内联脚本跑 node --check、JSON 数据块做解析；返回 (问题列表, 是否查过 JS)。"""
    problems, node = [], shutil.which("node")
    blocks = re.findall(r"<script\b([^>]*)>(.*?)</script\s*>", html, re.S | re.I)
    for n, (attrs, body) in enumerate(blocks, 1):
        if re.search(r"\bsrc\s*=", attrs, re.I) or not body.strip():
            continue
        m = re.search(r"""\btype\s*=\s*["']?([^"'\s>]+)""", attrs, re.I)
        kind = m.group(1).lower() if m else ""
        if kind in JSON_TYPES:
            try:
                json.loads(body)
            except ValueError as e:
                problems.append("第 %d 个 <script> 是 JSON 数据块，格式错误：%s" % (n, e))
        elif kind in JS_TYPES and node:
            with tempfile.NamedTemporaryFile("w", suffix=".mjs" if kind == "module" else ".js",
                                             delete=False, encoding="utf-8") as f:
                f.write(body)
            try:
                r = subprocess.run([node, "--check", f.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True)
            finally:
                os.unlink(f.name)
            if r.returncode != 0:
                lineno, code, err = node_error(r.stderr, f.name)
                problems.append("第 %d 个 <script> 第 %s 行语法错误：%s；代码：%s（常见原因：单引号字符串里的撇号没转义，"
                                "如 'Wombat's' 要写成 'Wombat\\'s' 或改用双引号）" % (n, lineno, err, code))
    return problems, bool(node)


def main(argv=None):
    ap = argparse.ArgumentParser(description="路书网页自检")
    ap.add_argument("html", help="路书 HTML 文件")
    ap.add_argument("--shots", help="截图保存目录，默认与 HTML 同目录")
    ap.add_argument("--js-only", action="store_true", help="只检查脚本语法，不开浏览器")
    args = ap.parse_args(argv)

    path = os.path.abspath(args.html)
    if not os.path.isfile(path):
        print("找不到文件: %s" % args.html, file=sys.stderr)
        return 2
    with open(path, encoding="utf-8") as f:
        problems, checked = check_scripts(f.read())
    if not checked:
        print("提示：没找到 node，跳过 node --check（装 Node.js 后重跑）", file=sys.stderr)

    if args.js_only:
        return report(problems, "脚本语法检查通过" if checked else "JSON 数据块检查通过")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("未安装 Playwright，跳过页面检查（pip install playwright && python -m playwright install chromium）",
              file=sys.stderr)
        return report(problems, "脚本语法检查通过" if checked else None) or 3

    shots = args.shots or os.path.dirname(path)
    os.makedirs(shots, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    bg = {}
    with sync_playwright() as p:
        exe = os.environ.get("CHROMIUM_PATH")
        try:
            browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        except Exception as e:  # 浏览器没装或版本不匹配
            print("无法启动 Chromium，跳过页面检查：%s" % str(e).strip().splitlines()[0], file=sys.stderr)
            return report(problems, "脚本语法检查通过" if checked else None) or 3
        for scheme in ("light", "dark"):
            ctx = browser.new_context(viewport={"width": 375, "height": 812}, device_scale_factor=2,
                                      is_mobile=True, has_touch=True, color_scheme=scheme)
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(pathlib.Path(path).as_uri())
            r = page.evaluate(PROBE)
            label = "浅色" if scheme == "light" else "深色"
            if r["scrollWidth"] > r["clientWidth"]:
                problems.append("[%s] 横向滚动：页面宽 %dpx，屏幕 %dpx；超出屏幕的元素：%s"
                                % (label, r["scrollWidth"], r["clientWidth"], "、".join(r["wide"]) or "未定位到"))
            problems.extend("[%s] 控制台报错：%s" % (label, e) for e in errors)
            if scheme == "light":
                problems.extend("链接协议不对：%r" % h for h in r["links"] if not h.startswith(ALLOWED_LINKS))
            bg[scheme] = r["bodyBg"]
            shot = os.path.join(shots, "%s-mobile-%s.png" % (base, scheme))
            page.screenshot(path=shot, full_page=True)
            print("截图（%s）: %s" % (label, shot))
            ctx.close()
        browser.close()

    if bg.get("light") == bg.get("dark"):
        print("提示：深色模式下背景没有变化，页面未适配深色（浅色页仍可读，按需处理）")
    return report(problems, "通过：脚本语法正确，375px 手机宽度无横向滚动，浅色/深色均无脚本报错，链接协议正确")


def report(problems, ok_msg):
    """打印结果：有问题返回 1；没问题时打印 ok_msg（为 None 则不打印）并返回 0。"""
    if problems:
        print("发现 %d 个问题：" % len(problems))
        for x in problems:
            print("  - " + x)
        return 1
    if ok_msg:
        print(ok_msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
