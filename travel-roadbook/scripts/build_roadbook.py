#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_roadbook.py — 旅行路书网页构建器

用法:
    python3 build_roadbook.py roadbook.json [输出.html] [--allow-placeholders]

读取一份结构化路书 JSON，渲染成自包含的手机端 HTML（含地图打开按钮、出行提醒、
天气速览、逐站路书、当地美食、门票花费、穿着建议、注意事项），自动适配深色模式。
不传输出路径时，输出到与 JSON 同目录、同名的 .html。

构建前先校验 JSON，不通过就报错退出（退出码 2）并列出字段路径：
    - 未知字段（多半是拼错，会提示最接近的字段名）、缺必填字段、枚举值不合法
    - 链接协议：amap_uri 只收 amapuri://，其余链接只收 https://；两种地图链接必须二选一
    - 模板占位内容（REPLACE_WITH…、YYYY-MM-DD、LNG,LAT、替换为…、按…实查、示例 等）；
      只有构建示例时才加 --allow-placeholders
以 _ 开头的字段当注释，不渲染也不校验。

地图二选一：
    amap_uri   国内，高德 amapuri:// 行程链接（maps_schema_personal_map 返回）
    gmaps_url  国外，Google Maps https 路线链接（全程总览）
字段说明见 references/scripts.md，模板见 assets/roadbook.sample.json（国内）与
assets/roadbook.google.sample.json（国外）。所有文本均做 HTML 转义。
"""
import argparse
import difflib
import html
import json
import os
import re
import sys
from datetime import datetime
from string import Template

CSS = r"""
  :root{
    color-scheme:light dark;
    --ink:#17202b; --sub:#5c6672; --muted:#66707c; --line:#e2e7ee;
    --bg:#f4f6f9; --card:#ffffff; --card2:#fafbfc; --head:#eef3f9;
    --text2:#46505c; --text3:#333d4a;
    --deep:#17365d; --deep2:#24507f; --accent:#17365d;
    --green:#15803d; --orange:#c2410c; --slate:#5f6b78; --purple:#7c3aed; --blue:#0b57d0; --red:#b91c1c;
    --orange-text:#c2410c; --orange-soft:#fdf3ea; --orange-line:#f2c7a3; --orange-ink:#8a3b0e;
    --blue-text:#0b57d0; --blue-soft:#eaf2fe; --blue-line:#c6dafc; --blue-press:#d6e6fd;
    --red-soft:#fdecec;
    --toast-bg:rgba(23,32,43,.92); --toast-ink:#ffffff; --shadow:rgba(23,32,43,.04);
    --radius:10px;
  }
  @media (prefers-color-scheme:dark){
    :root{
      --ink:#e6ebf1; --sub:#a3adb9; --muted:#8e99a6; --line:#2a333f;
      --bg:#0e1319; --card:#161d26; --card2:#1b232d; --head:#1f2935;
      --text2:#c2c9d2; --text3:#cfd5dc;
      --deep:#2c5a91; --deep2:#1f456f; --accent:#8fb6ea;
      --orange-text:#f4a26b; --orange-soft:#33231a; --orange-line:#6b4128; --orange-ink:#f5c9a6;
      --blue-text:#8ab4f8; --blue-soft:#1a2940; --blue-line:#2c4a73; --blue-press:#22385a;
      --red-soft:#3a1e1f;
      --toast-bg:rgba(230,235,241,.95); --toast-ink:#17202b; --shadow:rgba(0,0,0,.3);
    }
  }
  [hidden]{display:none!important;}
  *{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent;}
  html{font-size:16px;}
  body{
    font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    background:var(--bg); color:var(--ink);
    line-height:1.55; -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:560px;margin:0 auto;padding:20px 16px calc(28px + env(safe-area-inset-bottom));}
  header{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--sub);}
  header svg{flex:none;}
  .logo .pin{fill:var(--accent);}
  h1{font-size:25px;line-height:1.3;margin:14px 0 6px;letter-spacing:.01em;}
  .lead{color:var(--sub);font-size:15px;}
  .lead b{color:var(--ink);font-weight:600;}
  .wechat-tip{
    margin:16px 0 14px;padding:10px 12px;border:1px solid var(--orange-line);background:var(--orange-soft);
    border-radius:var(--radius);font-size:13.5px;color:var(--orange-ink);
  }
  .cta-card{
    background:var(--card);border:1px solid var(--line);border-radius:14px;
    padding:18px 16px;box-shadow:0 1px 2px var(--shadow);
  }
  .lead + .cta-card,.wechat-tip[hidden] + .cta-card{margin-top:18px;}
  .btn-open{
    display:block;width:100%;text-align:center;text-decoration:none;
    background:var(--deep);color:#fff;font-size:18px;font-weight:600;
    padding:16px 12px;border-radius:var(--radius);
    box-shadow:0 3px 0 var(--deep2);
  }
  .btn-open:active{transform:translateY(2px);box-shadow:0 1px 0 var(--deep2);}
  .btn-open .sub{display:block;font-size:12.5px;font-weight:400;opacity:.85;margin-top:3px;}
  .cta-note{font-size:13px;color:var(--sub);text-align:center;margin-top:10px;}
  section{margin-top:26px;}
  .sec-title{font-size:15px;font-weight:600;margin-bottom:10px;display:flex;flex-wrap:wrap;align-items:center;gap:2px 8px;}
  .sec-title .bar{flex:none;width:4px;height:16px;border-radius:2px;background:var(--deep);display:inline-block;}
  .upd{margin-left:auto;font-size:12px;font-weight:400;color:var(--muted);white-space:nowrap;}
  .upd.stale{color:var(--orange-text);font-weight:600;}
  .steps{list-style:none;counter-reset:step;}
  .steps li{counter-increment:step;position:relative;padding:0 0 16px 44px;font-size:14.5px;color:var(--text3);}
  .steps li::before{
    content:counter(step,decimal-leading-zero);
    position:absolute;left:0;top:-2px;width:28px;height:28px;border-radius:8px;
    background:var(--deep);color:#fff;font-size:12.5px;font-weight:600;
    display:flex;align-items:center;justify-content:center;
  }
  .steps li:not(:last-child)::after{content:"";position:absolute;left:13px;top:32px;bottom:2px;width:2px;background:var(--line);}
  .steps b{font-weight:600;}
  .copy-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:12px;display:flex;gap:10px;align-items:stretch;}
  .link-box{
    flex:1;min-width:0;border:1px solid var(--line);border-radius:8px;padding:10px 12px;
    font-size:14px;color:var(--ink);line-height:1.5;background:var(--card2);
  }
  .link-box .route{font-weight:600;overflow-wrap:anywhere;}
  .link-box .mode{display:block;font-size:12px;color:var(--sub);font-weight:400;margin-top:2px;}
  .link-box details{margin-top:6px;}
  .link-box summary{font-size:12px;color:var(--sub);cursor:pointer;}
  .link-box .raw{margin-top:4px;font-size:12px;color:var(--muted);word-break:break-all;user-select:all;}
  .btn-copy{
    flex:none;width:76px;height:44px;align-self:center;border:1px solid var(--accent);color:var(--accent);background:var(--card);
    border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;
  }
  .btn-copy:active{background:var(--head);}
  #toast{
    position:fixed;left:16px;right:16px;bottom:calc(24px + env(safe-area-inset-bottom));
    margin:0 auto;width:-webkit-fit-content;width:fit-content;max-width:420px;transform:translateY(8px);
    background:var(--toast-bg);color:var(--toast-ink);font-size:14px;line-height:1.45;text-align:center;
    padding:9px 18px;border-radius:14px;
    opacity:0;pointer-events:none;transition:opacity .18s ease,transform .18s ease;z-index:9;
  }
  #toast.show{opacity:1;transform:translateY(0);}
  .alert{display:flex;gap:10px;align-items:flex-start;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--slate);border-radius:var(--radius);padding:10px 12px;margin-bottom:8px;}
  .alert .lv{flex:none;margin-top:2px;font-size:11px;font-weight:600;color:#fff;background:var(--slate);border-radius:4px;padding:1.5px 6px;}
  .alert .body{flex:1;min-width:0;}
  .alert .meta{font-size:12px;color:var(--sub);}
  .alert .txt{font-size:13.5px;color:var(--text2);line-height:1.5;overflow-wrap:anywhere;}
  .alert .src-link{display:inline-block;margin-top:3px;font-size:12.5px;font-weight:600;color:var(--blue-text);text-decoration:none;}
  .alert.warn{border-left-color:var(--orange);} .alert.warn .lv{background:var(--orange);}
  .alert.severe{border-left-color:var(--red);background:var(--red-soft);} .alert.severe .lv{background:var(--red);}
  .alert.severe .txt{color:var(--ink);font-weight:600;}
  .alert-empty{font-size:13px;color:var(--sub);background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:10px 12px;}
  .weather-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;}
  @media (min-width:480px){.weather-grid{grid-template-columns:repeat(3,minmax(0,1fr));}}
  .wk{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:9px 11px;}
  .wk .city{font-size:13.5px;font-weight:600;overflow-wrap:anywhere;}
  .wk .city small{display:block;font-size:12px;color:var(--sub);font-weight:400;}
  .wk .kind{display:inline-block;margin-left:4px;padding:0 4px;border-radius:3px;font-size:11px;font-weight:600;line-height:1.5;}
  .kind.forecast{color:var(--blue-text);background:var(--blue-soft);}
  .kind.climate{color:var(--sub);background:var(--head);}
  .wk .t{margin-top:2px;font-size:13.5px;color:var(--sub);}
  .wk .t b{color:var(--ink);font-size:15px;}
  .wk .sun{margin-top:2px;font-size:12px;color:var(--sub);}
  .src-note{font-size:12px;color:var(--muted);margin-top:8px;line-height:1.6;}
  .tl{display:grid;grid-template-columns:58px 22px minmax(0,1fr);column-gap:0;position:relative;}
  .tl::before{content:"";position:absolute;left:68px;top:0;bottom:0;width:2px;background:var(--line);}
  .tl .t{font-size:12.5px;color:var(--sub);padding:10px 0;text-align:right;line-height:1.35;}
  .tl .axis{position:relative;}
  .tl .dot{position:absolute;top:13px;left:50%;transform:translateX(-50%);width:10px;height:10px;border-radius:50%;border:2px solid var(--card);box-shadow:0 0 0 1px var(--line);}
  .dot.blue{background:var(--deep);} .dot.green{background:var(--green);} .dot.orange{background:var(--orange);}
  .tl .cnt{padding:7px 0 13px 10px;}
  .tl .cnt .name{font-size:15px;font-weight:600;line-height:1.4;}
  .tl .cnt .name .km{font-size:12.5px;font-weight:400;color:var(--sub);margin-left:6px;}
  .d{display:flex;gap:7px;font-size:13px;color:var(--text2);margin-top:4px;line-height:1.45;}
  .d .tag{flex:none;align-self:flex-start;min-width:26px;text-align:center;font-size:11px;font-weight:600;color:#fff;border-radius:4px;padding:1.5px 6px;letter-spacing:.03em;}
  .tag.w{background:var(--deep);} .tag.p{background:var(--green);} .tag.f{background:var(--orange);}
  .tag.m{background:var(--purple);} .tag.t{background:var(--slate);} .tag.g{background:var(--blue);}
  .map-btn{
    display:inline-flex;align-items:center;gap:5px;max-width:100%;text-decoration:none;
    color:var(--blue-text);background:var(--blue-soft);border:1px solid var(--blue-line);border-radius:999px;
    padding:3px 10px 3px 8px;font-size:12.5px;font-weight:600;line-height:1.4;
  }
  .map-btn:active{background:var(--blue-press);}
  .map-btn svg{flex:none;}
  .map-btn span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .d .map-btn{min-width:0;}
  .stage{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;color:var(--sub);margin:18px 0 8px;letter-spacing:.04em;}
  .stage i{flex:none;width:8px;height:8px;border-radius:50%;display:inline-block;}
  .stage i.blue{background:var(--deep);} .stage i.green{background:var(--green);} .stage i.orange{background:var(--orange);}
  table.tk{width:100%;table-layout:fixed;border-collapse:separate;border-spacing:0;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;font-size:13px;}
  table.tk col.c1{width:34%;} table.tk col.c2{width:30%;}
  table.tk th,table.tk td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:break-word;}
  table.tk th{background:var(--head);font-weight:600;font-size:12.5px;}
  table.tk tbody tr:last-child td{border-bottom:none;}
  table.tk td.price{color:var(--ink);font-weight:600;}
  .total{margin-top:8px;font-size:13px;color:var(--text3);line-height:1.6;}
  .dish{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px;margin-bottom:8px;}
  .dish .n{font-size:15px;font-weight:600;display:flex;flex-wrap:wrap;align-items:center;gap:6px;}
  .dish .chip{font-size:11px;font-weight:600;color:var(--orange-text);background:var(--orange-soft);border-radius:4px;padding:1px 6px;}
  .dish .desc{font-size:13px;color:var(--text2);margin-top:4px;line-height:1.5;}
  .shop{display:flex;align-items:center;gap:10px;margin-top:8px;padding-top:8px;border-top:1px dashed var(--line);}
  .shop .info{flex:1;min-width:0;}
  .shop .sn{font-size:13.5px;font-weight:600;}
  .shop .sm{font-size:12px;color:var(--sub);margin-top:1px;line-height:1.45;}
  .shop .map-btn{flex:none;}
  .cloth{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px;margin-bottom:8px;}
  .cloth .g{font-size:14px;font-weight:600;margin-bottom:3px;}
  .cloth .g .ic{display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--deep);margin-right:7px;}
  .cloth .it{font-size:13px;color:var(--text2);}
  .tips{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:14px 15px;}
  .tips li{list-style:none;position:relative;padding:5px 0 5px 18px;font-size:13.5px;color:var(--text3);}
  .tips li::before{content:"";position:absolute;left:2px;top:12px;width:6px;height:6px;border-radius:2px;background:var(--orange);}
  footer{margin-top:26px;padding-top:14px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted);text-align:center;line-height:1.7;}
"""

JS = r"""
(function(){
  var toast=document.getElementById('toast'),timer=null;
  function show(msg,ms){
    toast.textContent=msg;toast.classList.add('show');
    if(timer)clearTimeout(timer);
    timer=setTimeout(function(){toast.classList.remove('show');},ms||1600);
  }
  var btn=document.getElementById('btnCopy'),box=document.getElementById('linkBox');
  if(btn&&box){
    btn.addEventListener('click',function(){
      var text=box.getAttribute('data-url');
      if(navigator.clipboard&&navigator.clipboard.writeText){
        navigator.clipboard.writeText(text).then(function(){show('已复制，去浏览器地址栏粘贴');},function(){fallback(text);});
      }else{fallback(text);}
    });
  }
  function fallback(text){
    var ta=document.createElement('textarea');
    ta.value=text;ta.style.position='fixed';ta.style.opacity='0';
    document.body.appendChild(ta);ta.select();
    try{document.execCommand('copy');show('已复制，去浏览器地址栏粘贴');}
    catch(e){show('请长按链接文本手动复制');}
    document.body.removeChild(ta);
  }
  // 只在会拦截 App 跳转的内置浏览器里提示“用浏览器打开”
  var tip=document.getElementById('wechatTip');
  if(tip&&/MicroMessenger|\bQQ\/|Weibo|DingTalk/i.test(navigator.userAgent))tip.hidden=false;
  // 点了高德按钮后页面一直在前台，多半是没装 App 或被拦截
  var open=document.getElementById('btnOpen'),pending=null;
  if(open&&(open.getAttribute('href')||'').indexOf('amapuri:')===0){
    open.addEventListener('click',function(){
      clearTimeout(pending);
      pending=setTimeout(function(){
        if(!document.hidden)show('如果没有跳转到高德：请确认已安装高德地图，或复制下方备用链接到浏览器打开',4000);
      },2500);
    });
    document.addEventListener('visibilitychange',function(){if(document.hidden)clearTimeout(pending);});
    window.addEventListener('pagehide',function(){clearTimeout(pending);});
  }
  // 实时数据超过 36 小时未更新，提示可能过期
  var now=Date.now();
  [].forEach.call(document.querySelectorAll('.upd[data-ts]'),function(el){
    if(now-Number(el.getAttribute('data-ts'))>36*3600*1000){
      el.classList.add('stale');el.appendChild(document.createTextNode(' · 可能已过期'));
    }
  });
})();
"""

PAGE = Template(r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#f4f6f9" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0e1319" media="(prefers-color-scheme: dark)">
<title>$title</title>
<meta name="description" content="$description">
<meta property="og:type" content="website">
<meta property="og:title" content="$title">
<meta property="og:description" content="$description">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%2317365d'/%3E%3Cpath d='M16 6c-4.4 0-8 3.4-8 7.6 0 5.4 7.2 11.9 7.6 12.2.2.2.6.2.8 0 .4-.3 7.6-6.8 7.6-12.2C24 9.4 20.4 6 16 6z' fill='%23fff'/%3E%3Ccircle cx='16' cy='13.5' r='2.6' fill='%23ea580c'/%3E%3C/svg%3E">
<style>$css</style>
</head>
<body>
<div class="wrap">
  <header>
    <svg class="logo" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path class="pin" d="M12 2C7.6 2 4 5.5 4 9.8 4 15.2 11.2 21.6 11.6 22c.2.2.6.2.8 0 .4-.4 7.6-6.8 7.6-12.2C20 5.5 16.4 2 12 2z"/>
      <circle cx="12" cy="9.8" r="2.8" fill="#ea580c"/>
    </svg>
    $eyebrow
  </header>

  <h1>$h1</h1>
  <p class="lead">$subtitle</p>
$wechat_block
  <div class="cta-card">
    <a class="btn-open" id="btnOpen" href="$map_uri"$map_target>
      $cta_title$cta_sub_block
    </a>$cta_note_block
  </div>
$steps_block$backup_block$alerts_block$weather_block
$stages_block
$food_block
$tickets_block
$clothing_block
$tips_block
  <footer>$footer</footer>
</div>
<div id="toast" role="status" aria-live="polite"></div>
<script>$js</script>
</body>
</html>
""")

TAG_COLORS = {"weather": "w", "spots": "p", "food": "f", "tickets": "m", "tips": "t"}
TAG_LABELS = {"weather": "天气", "spots": "景点", "food": "美食", "tickets": "门票", "tips": "贴士"}
KIND_LABELS = {"forecast": "预报", "climate": "气候参考"}
ALERT_LEVELS = (("severe", "严重"), ("warn", "注意"), ("info", "提示"))  # 按严重程度排序
LEVEL_LABELS = dict(ALERT_LEVELS)
LEVEL_RANK = dict((k, i) for i, (k, _) in enumerate(ALERT_LEVELS))

MAP_TEXT = {
    "amap": {
        "wechat_tip": "微信、QQ 等 App 内可能无法直接跳转高德：请先点右上角「···」→ 选择「在浏览器中打开」，再点下方按钮。",
        "cta_title": "在高德地图中打开行程",
        "cta_sub": "自动唤起已安装的高德地图 App",
        "cta_note": "手机需已安装「高德地图」App",
        "steps": [
            "在<b>手机浏览器</b>（Safari / Chrome）中打开本页；微信内请先用「在浏览器中打开」。",
            "点击上方按钮，<b>高德地图 App 会自动弹出</b>并生成行程路线图。",
            "若没有反应，复制下面的链接，粘贴到手机浏览器地址栏打开。",
        ],
    },
    "google": {
        # Google 版只保留按钮，不加打开提示
        "wechat_tip": "",
        "cta_title": "在 Google 地图中打开行程",
        "cta_sub": "",
        "cta_note": "",
        "steps": [],
    },
}

PIN_SVG = ('<svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C7.6 2 4 5.5 4 9.8 '
           '4 15.2 11.2 21.6 11.6 22c.2.2.6.2.8 0 .4-.4 7.6-6.8 7.6-12.2C20 5.5 16.4 2 12 2zm0 10.6a2.8 2.8 0 1 1 '
           '0-5.6 2.8 2.8 0 0 1 0 5.6z" fill="currentColor"/></svg>')


# ---------- 数据校验 ----------

class Obj(object):
    """JSON 对象：fields 为 字段名 → 规格，required 为必填字段。"""

    def __init__(self, fields, required=()):
        self.fields = fields
        self.required = tuple(required)


class Enum(object):
    def __init__(self, *values):
        self.values = values


TEXT = "text"    # 文本或数字
HTTPS = "https"  # 只收 https:// 链接

STOP = Obj({"date": TEXT, "time": TEXT, "name": TEXT, "km": TEXT, "weather": TEXT, "spots": TEXT,
            "food": TEXT, "tickets": TEXT, "tips": TEXT, "map_url": HTTPS, "map_label": TEXT}, ["name"])
SHOP = Obj({"name": TEXT, "note": TEXT, "map_url": HTTPS}, ["name"])
DISH = Obj({"name": TEXT, "tags": [TEXT], "desc": TEXT, "shops": [SHOP]}, ["name"])
SCHEMA = Obj({
    "title": TEXT, "eyebrow": TEXT, "title_lines": [TEXT], "subtitle": TEXT,
    "amap_uri": TEXT, "gmaps_url": HTTPS,
    "updated_at": TEXT,
    "alerts": [Obj({"level": Enum(*LEVEL_LABELS), "date": TEXT, "city": TEXT, "text": TEXT, "url": HTTPS},
                   ["text"])],
    "weather": [Obj({"city": TEXT, "label": TEXT, "date": TEXT, "day": TEXT, "night": TEXT, "text": TEXT,
                     "kind": Enum(*KIND_LABELS), "sunrise": TEXT, "sunset": TEXT}, ["city"])],
    "weather_note": TEXT,
    "stages": [Obj({"name": TEXT, "color": Enum("blue", "green", "orange"), "stops": [STOP]}, ["name"])],
    "food": [Obj({"city": TEXT, "items": [DISH]}, ["city"])],
    "food_note": TEXT,
    "tickets": [Obj({"name": TEXT, "price": TEXT, "book": TEXT}, ["name"])],
    "tickets_total": TEXT,
    "budget_note": TEXT,
    "clothing": [Obj({"group": TEXT, "items": TEXT}, ["group", "items"])],
    "tips": [TEXT],
    "footer": TEXT,
})

# 模板里的占位写法，成品里不能出现
PLACEHOLDERS = (
    ("REPLACE_WITH…", re.compile(r"REPLACE_WITH")),
    ("YYYY-MM-DD", re.compile(r"YYYY-MM-DD")),
    ("HH:MM", re.compile(r"HH:MM")),
    ("LNG,LAT", re.compile(r"LNG,LAT")),
    ("YY", re.compile(r"^YY$")),
    ("替换为…", re.compile(r"替换为")),
    ("按…实查", re.compile(r"实查")),
    ("示例", re.compile(r"示例")),
)


def has(v):
    return v is not None and v != ""


def join(path, key):
    return "%s.%s" % (path, key) if path else key


def check(value, spec, path, errors):
    where = path or "顶层"
    if isinstance(spec, list):
        if not isinstance(value, list):
            errors.append("%s 应为数组" % where)
            return
        for i, v in enumerate(value):
            check(v, spec[0], "%s[%d]" % (path, i), errors)
    elif isinstance(spec, Obj):
        if not isinstance(value, dict):
            errors.append("%s 应为对象" % where)
            return
        for k in spec.required:
            if not has(value.get(k)):
                errors.append("%s 缺少必填字段 %s" % (where, k))
        for k, v in value.items():
            if k.startswith("_"):
                continue
            if k not in spec.fields:
                hint = difflib.get_close_matches(k, list(spec.fields), n=1)
                errors.append("%s 未知字段 %s%s" % (where, k, "（是不是 %s？）" % hint[0] if hint else ""))
                continue
            check(v, spec.fields[k], join(path, k), errors)
    elif isinstance(spec, Enum):
        if value not in spec.values:
            errors.append("%s 只能是 %s，当前为 %s" % (where, " / ".join(spec.values),
                                                    json.dumps(value, ensure_ascii=False)))
    elif isinstance(value, bool) or not isinstance(value, (str, int, float)):
        errors.append("%s 应为文本或数字" % where)
    elif spec == HTTPS and not str(value).startswith("https://"):
        errors.append("%s 只收 https:// 链接，当前为 %s" % (where, value))


def placeholder_label(text):
    for label, rx in PLACEHOLDERS:
        if rx.search(text):
            return label
    return None


def find_placeholders(value, path="", found=None):
    if found is None:
        found = []
    if isinstance(value, dict):
        for k, v in value.items():
            if not k.startswith("_"):
                find_placeholders(v, join(path, k), found)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            find_placeholders(v, "%s[%d]" % (path, i), found)
    elif isinstance(value, str):
        label = placeholder_label(value)
        if label:
            found.append((path, label))
    return found


def parse_updated(text):
    """带时区的 ISO 8601 → (毫秒时间戳, "MM-DD HH:MM")；格式不对返回 None。"""
    try:
        dt = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return int(dt.timestamp() * 1000), dt.strftime("%m-%d %H:%M")


def validate(d):
    errors = []
    check(d, SCHEMA, "", errors)
    if not isinstance(d, dict):
        return errors
    amap, gmaps = d.get("amap_uri"), d.get("gmaps_url")
    if has(amap) and has(gmaps):
        errors.append("amap_uri 与 gmaps_url 只能填一个（国内填 amap_uri，国外填 gmaps_url）")
    elif not has(amap) and not has(gmaps):
        errors.append("缺少地图链接：国内填 amap_uri（amapuri://…），国外填 gmaps_url（https://…）")
    if has(amap) and not str(amap).startswith("amapuri://"):
        errors.append("amap_uri 必须是 maps_schema_personal_map 返回的 amapuri:// 链接，当前为 %s" % amap)
    updated = d.get("updated_at")
    if has(updated) and parse_updated(updated) is None and not placeholder_label(str(updated)):
        errors.append("updated_at 需为带时区的 ISO 8601 时间，如 2026-09-24T07:00:00+08:00，当前为 %s" % updated)
    return errors


# ---------- 渲染 ----------

def esc(v):
    return html.escape(str(v), quote=True)


def section(title, body, extra=""):
    return ('\n  <section>\n    <div class="sec-title"><span class="bar"></span>%s%s</div>\n%s\n  </section>'
            % (title, extra, body))


def render_stamp(updated):
    if not updated:
        return ""
    return '<span class="upd" data-ts="%d">更新于 %s</span>' % updated


def render_alerts(alerts, updated):
    if alerts is None:
        return ""
    if not alerts:
        return section("出行提醒", '    <div class="alert-empty">暂无已公告的预警、罢工或临时关闭</div>',
                       render_stamp(updated))
    rows = []
    for a in sorted(alerts, key=lambda a: LEVEL_RANK[a.get("level", "info")]):
        level = a.get("level", "info")
        meta = " · ".join(esc(a[k]) for k in ("date", "city") if has(a.get(k)))
        link = ('<a class="src-link" href="%s" target="_blank" rel="noopener">查看来源 ›</a>' % esc(a["url"])
                if has(a.get("url")) else "")
        rows.append('    <div class="alert %s"><span class="lv">%s</span><div class="body">%s<div class="txt">%s</div>%s</div></div>'
                    % (level, LEVEL_LABELS[level], '<div class="meta">%s</div>' % meta if meta else "",
                       esc(a["text"]), link))
    return section("出行提醒", "\n".join(rows), render_stamp(updated))


def render_weather(weather, note, updated):
    if not weather:
        return ""
    cards = []
    for w in weather:
        label = w.get("label", w.get("date", ""))
        kind = '<span class="kind %s">%s</span>' % (w["kind"], KIND_LABELS[w["kind"]]) if has(w.get("kind")) else ""
        small = '<small>%s%s</small>' % (esc(label), kind) if has(label) or kind else ""
        day, night = w.get("day"), w.get("night")
        if has(day) and has(night):
            temp = '<b>%s°</b>/%s°' % (esc(day), esc(night))
        elif has(day):
            temp = '<b>%s°</b>' % esc(day)
        elif has(night):
            temp = '夜 %s°' % esc(night)
        else:
            temp = ""
        t = " ".join(x for x in (temp, esc(w.get("text", ""))) if x)
        sun = " · ".join("%s %s" % (name, esc(w[k])) for k, name in (("sunrise", "日出"), ("sunset", "日落"))
                         if has(w.get(k)))
        cards.append('<div class="wk"><div class="city">%s%s</div><div class="t">%s</div>%s</div>'
                     % (esc(w["city"]), small, t, '<div class="sun">%s</div>' % sun if sun else ""))
    note_html = '<div class="src-note">%s</div>' % esc(note) if note else ""
    return section("沿途天气速览", '    <div class="weather-grid">%s</div>%s' % ("".join(cards), note_html),
                   render_stamp(updated))


def render_stop(stop, color):
    rows = []
    for key in ("weather", "spots", "food", "tickets", "tips"):
        val = stop.get(key)
        if has(val):
            rows.append('<div class="d"><span class="tag %s">%s</span><span>%s</span></div>'
                        % (TAG_COLORS[key], TAG_LABELS[key], esc(val)))
    if has(stop.get("map_url")):
        rows.append('<div class="d"><span class="tag g">地图</span>'
                    '<a class="map-btn" href="%s" target="_blank" rel="noopener">%s<span>%s</span> ›</a></div>'
                    % (esc(stop["map_url"]), PIN_SVG, esc(stop.get("map_label") or "打开当日路线")))
    km = '<span class="km">%s</span>' % esc(stop["km"]) if has(stop.get("km")) else ""
    return (
        '      <div class="t">%s<br>%s</div><div class="axis"><div class="dot %s"></div></div>\n'
        '      <div class="cnt">\n        <div class="name">%s%s</div>\n%s\n      </div>'
        % (esc(stop.get("date", "")), esc(stop.get("time", "")), color,
           esc(stop["name"]), km, "\n".join(rows)))


def render_stages(stages):
    if not stages:
        return ""
    blocks = []
    for st in stages:
        color = st.get("color", "blue")
        stops = "\n".join(render_stop(s, color) for s in st.get("stops", []))
        blocks.append('    <div class="stage"><i class="%s"></i>%s</div>\n    <div class="tl">\n%s\n    </div>'
                      % (color, esc(st["name"]), stops))
    return section("逐站路书", "\n".join(blocks))


def render_food(food, note):
    if not food:
        return ""
    blocks = []
    for group in food:
        dishes = []
        for it in group.get("items", []):
            chips = "".join('<span class="chip">%s</span>' % esc(t) for t in it.get("tags", []))
            desc = '<div class="desc">%s</div>' % esc(it["desc"]) if has(it.get("desc")) else ""
            shops = []
            for sh in it.get("shops", []):
                meta = '<div class="sm">%s</div>' % esc(sh["note"]) if has(sh.get("note")) else ""
                btn = ('<a class="map-btn" href="%s" target="_blank" rel="noopener">%s<span>导航</span></a>'
                       % (esc(sh["map_url"]), PIN_SVG)) if has(sh.get("map_url")) else ""
                shops.append('<div class="shop"><div class="info"><div class="sn">%s</div>%s</div>%s</div>'
                             % (esc(sh["name"]), meta, btn))
            dishes.append('    <div class="dish"><div class="n">%s%s</div>%s%s</div>'
                          % (esc(it["name"]), chips, desc, "".join(shops)))
        blocks.append('    <div class="stage"><i class="orange"></i>%s</div>\n%s'
                      % (esc(group["city"]), "\n".join(dishes)))
    note_html = '\n    <div class="src-note">%s</div>' % esc(note) if note else ""
    return section("当地美食推荐", "\n".join(blocks) + note_html)


def render_tickets(tickets, total, note):
    if not tickets:
        return ""
    rows = "".join('<tr><td>%s</td><td class="price">%s</td><td>%s</td></tr>'
                   % (esc(t["name"]), esc(t.get("price", "")), esc(t.get("book", ""))) for t in tickets)
    body = ('    <table class="tk"><colgroup><col class="c1"><col class="c2"><col></colgroup>'
            '<thead><tr><th>景点/项目</th><th>票价参考</th><th>预约/说明</th></tr></thead><tbody>%s</tbody></table>'
            % rows)
    if total:
        body += '<div class="total">%s</div>' % esc(total)
    if note:
        body += '<div class="src-note">%s</div>' % esc(note)
    return section("门票与花费参考", body)


def render_clothing(clothing):
    if not clothing:
        return ""
    cards = "".join('<div class="cloth"><div class="g"><span class="ic"></span>%s</div><div class="it">%s</div></div>'
                    % (esc(c["group"]), esc(c["items"])) for c in clothing)
    return section("穿着建议", cards)


def render_tips(tips):
    if not tips:
        return ""
    lis = "\n".join("      <li>%s</li>" % esc(t) for t in tips)
    return section("注意事项", '    <ul class="tips">\n%s\n    </ul>' % lis)


def render_page(d):
    provider = "google" if has(d.get("gmaps_url")) else "amap"
    map_uri = d.get("gmaps_url") if provider == "google" else d.get("amap_uri")
    text = MAP_TEXT[provider]
    updated = parse_updated(d["updated_at"]) if has(d.get("updated_at")) else None
    # 备用链接卡片只给高德：amapuri 在部分浏览器点了没反应，需要复制到别的浏览器打开；
    # Google 按钮本身就是 https 链接，不需要备用
    backup = ""
    if provider == "amap":
        backup = section("行程链接（备用）",
                         '    <div class="copy-card">\n'
                         '      <div class="link-box" id="linkBox" data-url="%s">\n'
                         '        <div class="route">高德地图行程<span class="mode">点「复制」后粘贴到手机浏览器地址栏打开</span></div>\n'
                         '        <details><summary>查看完整链接</summary><div class="raw">%s</div></details>\n'
                         '      </div>\n'
                         '      <button class="btn-copy" id="btnCopy" type="button">复制</button>\n'
                         '    </div>' % (esc(map_uri), esc(map_uri)))
    title = d.get("title") or "旅行路书"
    h1 = "<br>".join(esc(x) for x in d["title_lines"]) if d.get("title_lines") else esc(title)
    return PAGE.substitute(
        title=esc(title),
        description=esc(d.get("subtitle") or d.get("eyebrow") or title),
        css=CSS,
        js=JS,
        eyebrow=esc(d.get("eyebrow") or "旅行路书"),
        h1=h1,
        subtitle=esc(d.get("subtitle", "")),
        wechat_block=('  <div class="wechat-tip" id="wechatTip" hidden>%s</div>' % esc(text["wechat_tip"]))
        if text["wechat_tip"] else "",
        cta_title=esc(text["cta_title"]),
        cta_sub_block=('\n      <span class="sub">%s</span>' % esc(text["cta_sub"])) if text["cta_sub"] else "",
        cta_note_block=('\n    <div class="cta-note">%s</div>' % esc(text["cta_note"])) if text["cta_note"] else "",
        steps_block=section("怎么在手机上打开", '    <ol class="steps">\n%s\n    </ol>'
                            % "\n".join("      <li>%s</li>" % li for li in text["steps"])) if text["steps"] else "",
        map_uri=esc(map_uri),
        map_target=' target="_blank" rel="noopener"' if provider == "google" else "",
        backup_block=backup,
        alerts_block=render_alerts(d.get("alerts"), updated),
        weather_block=render_weather(d.get("weather", []), d.get("weather_note", ""), updated),
        stages_block=render_stages(d.get("stages", [])),
        food_block=render_food(d.get("food", []), d.get("food_note", "")),
        tickets_block=render_tickets(d.get("tickets", []), d.get("tickets_total", ""), d.get("budget_note", "")),
        clothing_block=render_clothing(d.get("clothing", [])),
        tips_block=render_tips(d.get("tips", [])),
        footer=esc(d.get("footer", "")).replace("&lt;br&gt;", "<br>"),
    )


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def bullets(items):
    return "\n".join("  - " + x for x in items)


def main(argv=None):
    ap = argparse.ArgumentParser(description="旅行路书 JSON → 手机端 HTML")
    ap.add_argument("json_path", help="路书数据 JSON")
    ap.add_argument("out_path", nargs="?", help="输出 HTML，默认与 JSON 同目录同名")
    ap.add_argument("--allow-placeholders", action="store_true", help="允许模板占位内容（只用于构建示例）")
    args = ap.parse_args(argv)

    try:
        with open(args.json_path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except OSError as e:
        fail("读取失败：%s" % e)
    except ValueError as e:
        fail("JSON 格式错误：%s" % e)

    errors = validate(d)
    if errors:
        fail("路书 JSON 校验失败（%d 处）：\n%s" % (len(errors), bullets(errors)))
    found = find_placeholders(d)
    if found:
        msg = "模板占位内容 %d 处，须替换为实查数据：\n%s" % (len(found), bullets("%s：%s" % p for p in found))
        if not args.allow_placeholders:
            fail(msg + "\n（只有构建示例时才加 --allow-placeholders）")
        print("注意：" + msg, file=sys.stderr)

    out_path = args.out_path or os.path.splitext(args.json_path)[0] + ".html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_page(d))
    print("saved:", out_path)


if __name__ == "__main__":
    main()
