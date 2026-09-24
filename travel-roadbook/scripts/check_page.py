#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_page.py — 路书网页自检（手机宽度、浅色/深色、链接、脚本报错）

用法:
    python3 check_page.py <路书.html> [--shots 截图目录]

用 Playwright + Chromium 以 375×812 手机视口，分别在浅色、深色模式打开页面，检查：
    - 横向滚动：页面比屏幕宽（列出超出屏幕的元素）
    - 控制台报错与脚本异常
    - 链接：href 只能是 https://、amapuri://、tel:、mailto: 或页内锚点
并保存两张整页截图（默认与 HTML 同目录），打开看排版和深色模式是否可读。

退出码: 0 通过；1 发现问题；2 参数错误；3 没有 Playwright 或浏览器，跳过（按 SKILL.md 清单人工自检）。
依赖: pip install playwright && python -m playwright install chromium
      浏览器装在别处时，用环境变量 CHROMIUM_PATH 指定可执行文件。
"""
import argparse
import os
import pathlib
import sys

ALLOWED_LINKS = ("https://", "amapuri://", "tel:", "mailto:", "#")

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


def main(argv=None):
    ap = argparse.ArgumentParser(description="路书网页自检")
    ap.add_argument("html", help="路书 HTML 文件")
    ap.add_argument("--shots", help="截图保存目录，默认与 HTML 同目录")
    args = ap.parse_args(argv)

    path = os.path.abspath(args.html)
    if not os.path.isfile(path):
        print("找不到文件: %s" % args.html, file=sys.stderr)
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("未安装 Playwright，跳过自动自检（pip install playwright && python -m playwright install chromium）",
              file=sys.stderr)
        return 3

    shots = args.shots or os.path.dirname(path)
    os.makedirs(shots, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    problems, bg = [], {}
    with sync_playwright() as p:
        exe = os.environ.get("CHROMIUM_PATH")
        try:
            browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        except Exception as e:  # 浏览器没装或版本不匹配
            print("无法启动 Chromium，跳过自动自检：%s" % str(e).strip().splitlines()[0], file=sys.stderr)
            return 3
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
    if problems:
        print("发现 %d 个问题：" % len(problems))
        for x in problems:
            print("  - " + x)
        return 1
    print("通过：375px 手机宽度无横向滚动，浅色/深色均无脚本报错，链接协议正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())
