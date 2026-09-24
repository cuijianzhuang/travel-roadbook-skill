#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_qr.py — 为已发布的路书网页生成二维码 PNG

用法:
    python3 make_qr.py <已发布的https链接> <输出.png>

依赖: pip install qrcode[pil]
注意: 二维码必须编码发布后的 https 网页链接（手机相机可扫），
不要编码 amapuri:// 自定义协议链接（iOS 相机无法可靠识别）。
"""
import sys


def main():
    if len(sys.argv) != 3:
        print("usage: make_qr.py <https-url> <output.png>", file=sys.stderr)
        sys.exit(2)
    url, out = sys.argv[1], sys.argv[2]
    if not url.startswith("https://"):
        print("warning: 二维码通常应编码 https 网页链接，而非自定义协议", file=sys.stderr)
    try:
        import qrcode
    except ImportError:
        print("缺少依赖，请先运行: pip3 install 'qrcode[pil]'", file=sys.stderr)
        sys.exit(1)
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#17202b", back_color="white")
    img.save(out)
    print("saved:", out)


if __name__ == "__main__":
    main()
