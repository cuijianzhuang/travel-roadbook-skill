#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_roadbook.py — 旅行路书网页构建器

用法:
    python3 build_roadbook.py roadbook.json [输出.html]

读取一份结构化路书 JSON，渲染成自包含的手机端 HTML（含高德地图唤起按钮、
天气速览、逐站路书、门票花费、穿着建议、注意事项）。不传输出路径时，
输出到与 JSON 同目录、同名的 .html。

JSON 字段见 assets/roadbook.sample.json。所有动态文本均做 HTML 转义。
"""
import json
import sys
import html
import os
from string import Template

CSS = r"""
  :root{
    --ink:#17202b; --sub:#5c6672; --line:#e2e7ee;
    --bg:#f4f6f9; --card:#ffffff;
    --deep:#17365d; --deep2:#24507f; --orange:#ea580c; --green:#15803d;
    --radius:10px;
  }
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
  h1{font-size:25px;line-height:1.3;margin:14px 0 6px;letter-spacing:.01em;}
  .lead{color:var(--sub);font-size:15px;}
  .lead b{color:var(--ink);font-weight:600;}
  .wechat-tip{
    margin:16px 0 14px;padding:10px 12px;border:1px solid #f2c7a3;background:#fdf3ea;
    border-radius:var(--radius);font-size:13.5px;color:#8a3b0e;
  }
  .cta-card{
    background:var(--card);border:1px solid var(--line);border-radius:14px;
    padding:18px 16px;box-shadow:0 1px 2px rgba(23,32,43,.04);
  }
  .btn-open{
    display:block;width:100%;text-align:center;text-decoration:none;
    background:var(--deep);color:#fff;font-size:18px;font-weight:600;
    padding:16px 12px;border-radius:var(--radius);
    box-shadow:0 3px 0 var(--deep2);
  }
  .btn-open:active{transform:translateY(2px);box-shadow:0 1px 0 var(--deep2);}
  .btn-open .sub{display:block;font-size:12.5px;font-weight:400;opacity:.82;margin-top:3px;}
  .cta-note{font-size:13px;color:var(--sub);text-align:center;margin-top:10px;}
  section{margin-top:26px;}
  .sec-title{font-size:15px;font-weight:600;margin-bottom:10px;display:flex;align-items:center;gap:8px;}
  .sec-title .bar{width:4px;height:16px;border-radius:2px;background:var(--deep);display:inline-block;}
  .steps{list-style:none;counter-reset:step;}
  .steps li{counter-increment:step;position:relative;padding:0 0 16px 44px;font-size:14.5px;color:#333d4a;}
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
    font-size:11.5px;color:var(--sub);word-break:break-all;line-height:1.5;background:#fafbfc;user-select:all;
  }
  .btn-copy{
    flex:none;width:76px;border:1px solid var(--deep);color:var(--deep);background:#fff;
    border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;
  }
  .btn-copy:active{background:#eef3f9;}
  #toast{
    position:fixed;left:50%;bottom:calc(24px + env(safe-area-inset-bottom));
    transform:translateX(-50%) translateY(8px);
    background:rgba(23,32,43,.92);color:#fff;font-size:14px;padding:9px 18px;border-radius:20px;
    opacity:0;pointer-events:none;transition:opacity .18s ease,transform .18s ease;z-index:9;white-space:nowrap;
  }
  #toast.show{opacity:1;transform:translateX(-50%) translateY(0);}
  .weather-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;}
  @media (min-width:480px){.weather-grid{grid-template-columns:repeat(3,1fr);}}
  .wk{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:9px 11px;display:flex;align-items:center;justify-content:space-between;gap:8px;}
  .wk .city{font-size:13.5px;font-weight:600;}
  .wk .city small{display:block;font-size:10.5px;color:#9aa3ae;font-weight:400;}
  .wk .t{font-size:13.5px;color:var(--sub);text-align:right;}
  .wk .t b{color:var(--ink);font-size:15px;}
  .src-note{font-size:12px;color:#8a94a1;margin-top:8px;line-height:1.6;}
  .tl{display:grid;grid-template-columns:58px 22px 1fr;column-gap:0;position:relative;}
  .tl::before{content:"";position:absolute;left:68px;top:0;bottom:0;width:2px;background:var(--line);}
  .tl .t{font-size:12.5px;color:var(--sub);padding:10px 0;text-align:right;line-height:1.35;}
  .tl .axis{position:relative;}
  .tl .dot{position:absolute;top:13px;left:50%;transform:translateX(-50%);width:10px;height:10px;border-radius:50%;border:2px solid #fff;box-shadow:0 0 0 1px var(--line);}
  .dot.blue{background:var(--deep);} .dot.green{background:var(--green);} .dot.orange{background:var(--orange);}
  .tl .cnt{padding:7px 0 13px 10px;}
  .tl .cnt .name{font-size:15px;font-weight:600;line-height:1.4;}
  .tl .cnt .name .km{font-size:12.5px;font-weight:400;color:var(--sub);margin-left:6px;}
  .d{display:flex;gap:7px;font-size:13px;color:#46505c;margin-top:4px;line-height:1.45;}
  .d .tag{flex:none;align-self:flex-start;min-width:26px;text-align:center;font-size:11px;font-weight:600;color:#fff;border-radius:4px;padding:1.5px 6px;letter-spacing:.03em;}
  .tag.w{background:var(--deep);} .tag.p{background:var(--green);} .tag.f{background:var(--orange);}
  .tag.m{background:#7c3aed;} .tag.t{background:#8a94a1;}
  .stage{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;color:var(--sub);margin:18px 0 8px;letter-spacing:.04em;}
  .stage i{width:8px;height:8px;border-radius:50%;display:inline-block;}
  table.tk{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;font-size:13px;}
  table.tk th,table.tk td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;}
  table.tk th{background:#eef3f9;font-weight:600;font-size:12.5px;}
  table.tk tr:last-child td{border-bottom:none;}
  table.tk td.price{white-space:nowrap;color:var(--ink);font-weight:600;}
  .cloth{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px;margin-bottom:8px;}
  .cloth .g{font-size:14px;font-weight:600;margin-bottom:3px;}
  .cloth .g .ic{display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--deep);margin-right:7px;}
  .cloth .it{font-size:13px;color:#46505c;}
  .tips{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:14px 15px;}
  .tips li{list-style:none;position:relative;padding:5px 0 5px 18px;font-size:13.5px;color:#3b4550;}
  .tips li::before{content:"";position:absolute;left:2px;top:12px;width:6px;height:6px;border-radius:2px;background:var(--orange);}
  footer{margin-top:26px;padding-top:14px;border-top:1px solid var(--line);font-size:12.5px;color:#8a94a1;text-align:center;line-height:1.7;}
"""

JS = r"""
(function(){
  var btn=document.getElementById('btnCopy'),box=document.getElementById('linkBox'),toast=document.getElementById('toast'),timer=null;
  function show(msg){
    toast.textContent=msg;toast.classList.add('show');
    if(timer)clearTimeout(timer);
    timer=setTimeout(function(){toast.classList.remove('show');},1600);
  }
  if(btn&&box){
    btn.addEventListener('click',function(){
      var text=box.textContent.replace(/\s+/g,'');
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
})();
"""

PAGE = Template(r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>$title</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%2317365d'/%3E%3Cpath d='M16 6c-4.4 0-8 3.4-8 7.6 0 5.4 7.2 11.9 7.6 12.2.2.2.6.2.8 0 .4-.3 7.6-6.8 7.6-12.2C24 9.4 20.4 6 16 6z' fill='%23fff'/%3E%3Ccircle cx='16' cy='13.5' r='2.6' fill='%23ea580c'/%3E%3C/svg%3E">
<style>$css</style>
</head>
<body>
<div class="wrap">
  <header>
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 2C7.6 2 4 5.5 4 9.8 4 15.2 11.2 21.6 11.6 22c.2.2.6.2.8 0 .4-.4 7.6-6.8 7.6-12.2C20 5.5 16.4 2 12 2z" fill="#17365d"/>
      <circle cx="12" cy="9.8" r="2.8" fill="#ea580c"/>
    </svg>
    $eyebrow
  </header>

  <h1>$h1</h1>
  <p class="lead">$subtitle</p>

  <div class="wechat-tip">微信内可能无法直接跳转高德：请先点右上角「···」→ 选择「在浏览器中打开」，再点下方按钮。</div>

  <div class="cta-card">
    <a class="btn-open" href="$amap_uri">
      在高德地图中打开行程
      <span class="sub">自动唤起已安装的高德地图 App</span>
    </a>
    <div class="cta-note">手机需已安装「高德地图」App</div>
  </div>

  <section>
    <div class="sec-title"><span class="bar"></span>怎么在手机上打开</div>
    <ol class="steps">
      <li>在<b>手机浏览器</b>（Safari / Chrome）中打开本页；微信内请先用「在浏览器中打开」。</li>
      <li>点击上方按钮，<b>高德地图 App 会自动弹出</b>并生成行程路线图。</li>
      <li>若没有反应，复制下面的链接，粘贴到手机浏览器地址栏打开。</li>
    </ol>
  </section>

  <section>
    <div class="sec-title"><span class="bar"></span>行程链接（备用）</div>
    <div class="copy-card">
      <div class="link-box" id="linkBox">$amap_uri_text</div>
      <button class="btn-copy" id="btnCopy" type="button">复制</button>
    </div>
  </section>
$weather_block
$stages_block
$tickets_block
$clothing_block
$tips_block
  <footer>$footer</footer>
</div>
<div id="toast" role="status"></div>
<script>$js</script>
</body>
</html>
""")

TAG_COLORS = {"weather": "w", "spots": "p", "food": "f", "tickets": "m", "tips": "t"}
TAG_LABELS = {"weather": "天气", "spots": "景点", "food": "美食", "tickets": "门票", "tips": "贴士"}
STAGE_COLORS = {"blue": "var(--deep)", "green": "var(--green)", "orange": "var(--orange)"}


def esc(v):
    return html.escape(str(v), quote=True)


def render_weather(weather, note):
    if not weather:
        return ""
    cards = []
    for w in weather:
        temp = '<b>%s°</b>/%s° %s' % (esc(w["day"]), esc(w["night"]), esc(w.get("text", "")))
        cards.append(
            '<div class="wk"><div class="city">%s<small>%s</small></div><div class="t">%s</div></div>'
            % (esc(w["city"]), esc(w.get("label", "")), temp))
    note_html = '<div class="src-note">%s</div>' % esc(note) if note else ""
    return ('\n  <section>\n    <div class="sec-title"><span class="bar"></span>沿途天气速览</div>\n'
            '    <div class="weather-grid">%s</div>%s\n  </section>' % ("".join(cards), note_html))


def render_stop(stop, color):
    rows = []
    for key in ("weather", "spots", "food", "tickets", "tips"):
        val = stop.get(key)
        if val:
            rows.append('<div class="d"><span class="tag %s">%s</span><span>%s</span></div>'
                        % (TAG_COLORS[key], TAG_LABELS[key], esc(val)))
    km = '<span class="km">%s</span>' % esc(stop["km"]) if stop.get("km") else ""
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
        blocks.append(
            '    <div class="stage"><i style="background:%s"></i>%s</div>\n'
            '    <div class="tl">\n%s\n    </div>'
            % (STAGE_COLORS.get(color, "var(--deep)"), esc(st["name"]), stops))
    return '\n  <section>\n    <div class="sec-title"><span class="bar"></span>逐站路书</div>\n%s\n  </section>' % "\n".join(blocks)


def render_tickets(tickets, total, note):
    if not tickets:
        return ""
    rows = []
    for t in tickets:
        rows.append('<tr><td>%s</td><td class="price">%s</td><td>%s</td></tr>'
                    % (esc(t["name"]), esc(t.get("price", "")), esc(t.get("book", ""))))
    total_html = ('<div class="src-note" style="margin-top:8px;font-size:13px;color:#3b4550;">'
                  + esc(total) + '</div>') if total else ""
    note_html = '<div class="src-note">' + esc(note) + '</div>' if note else ""
    head = ('\n  <section>\n    <div class="sec-title"><span class="bar"></span>门票与花费参考</div>\n'
            '    <table class="tk"><tr><th style="width:34%">景点/项目</th>'
            '<th style="width:30%">票价参考</th><th>预约/说明</th></tr>')
    tail = "</table>" + total_html + note_html + "\n  </section>"
    return head + "".join(rows) + tail


def render_clothing(clothing):
    if not clothing:
        return ""
    cards = []
    for c in clothing:
        cards.append('<div class="cloth"><div class="g"><span class="ic"></span>%s</div><div class="it">%s</div></div>'
                     % (esc(c["group"]), esc(c["items"])))
    return '\n  <section>\n    <div class="sec-title"><span class="bar"></span>穿着建议</div>\n%s\n  </section>' % "".join(cards)


def render_tips(tips):
    if not tips:
        return ""
    lis = "\n".join("      <li>%s</li>" % esc(t) for t in tips)
    return ('\n  <section>\n    <div class="sec-title"><span class="bar"></span>注意事项</div>\n'
            '    <ul class="tips">\n%s\n    </ul>\n  </section>' % lis)


def main():
    if len(sys.argv) < 2:
        print("usage: build_roadbook.py roadbook.json [output.html]", file=sys.stderr)
        sys.exit(2)
    json_path = sys.argv[1]
    with open(json_path, "r", encoding="utf-8") as f:
        d = json.load(f)

    if len(sys.argv) >= 3:
        out_path = sys.argv[2]
    else:
        out_path = os.path.splitext(json_path)[0] + ".html"

    amap = d.get("amap_uri", "")
    h1 = "<br>".join(esc(x) for x in d["title_lines"]) if d.get("title_lines") else esc(d.get("title", "旅行路书"))
    page = PAGE.substitute(
        title=esc(d.get("title", "旅行路书")),
        css=CSS,
        js=JS,
        eyebrow=esc(d.get("eyebrow", "旅行路书")),
        h1=h1,
        subtitle=esc(d.get("subtitle", "")),
        amap_uri=esc(amap),
        amap_uri_text=esc(amap),
        weather_block=render_weather(d.get("weather", []), d.get("weather_note", "")),
        stages_block=render_stages(d.get("stages", [])),
        tickets_block=render_tickets(d.get("tickets", []), d.get("tickets_total", ""), d.get("budget_note", "")),
        clothing_block=render_clothing(d.get("clothing", [])),
        tips_block=render_tips(d.get("tips", [])),
        footer=esc(d.get("footer", "")).replace("&lt;br&gt;", "<br>"),
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    print("saved:", out_path)


if __name__ == "__main__":
    main()
