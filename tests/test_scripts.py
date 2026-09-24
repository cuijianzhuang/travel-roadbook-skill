# -*- coding: utf-8 -*-
"""
附带脚本的回归测试：python3 -m unittest discover -s tests -v

- build_roadbook.py：示例构建、字段校验与占位符拦截、转义、提醒/天气/更新时间渲染
- deploy.sh：参数校验、DRY_RUN，以及用假 npx / curl 跑通 Cloudflare 查真实子域名与标题校验
- make_qr.py、tools/package.py
- check_page.py：装了 Playwright 时对两份示例做页面自检，否则跳过
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "travel-roadbook")
SCRIPTS = os.path.join(SKILL, "scripts")
BUILD = os.path.join(SCRIPTS, "build_roadbook.py")
DEPLOY = os.path.join(SCRIPTS, "deploy.sh")
SAMPLES = [os.path.join(SKILL, "assets", n) for n in ("roadbook.sample.json", "roadbook.google.sample.json")]

MINIMAL = {
    "title": "测试路书",
    "amap_uri": "amapuri://workInAmap/createWithToken?polymericId=abc&from=MCP",
    "stages": [{"name": "去程", "stops": [{"name": "康定"}]}],
}


def run(cmd, **kw):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, **kw)


def tmpdir(case):
    path = tempfile.mkdtemp()
    case.addCleanup(shutil.rmtree, path)
    return path


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tmpdir(self)

    def build(self, data, *args):
        src = os.path.join(self.tmp, "data.json")
        with open(src, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        out = os.path.join(self.tmp, "out.html")
        if os.path.exists(out):
            os.remove(out)
        r = run([sys.executable, BUILD, src, out] + list(args))
        page = ""
        if r.returncode == 0:
            with open(out, encoding="utf-8") as f:
                page = f.read()
        return r, page

    def data(self, **kw):
        d = json.loads(json.dumps(MINIMAL))
        d.update(kw)
        return d

    def assertRejected(self, data, *fragments):
        r, _ = self.build(data)
        self.assertEqual(r.returncode, 2, r.stderr)
        for frag in fragments:
            self.assertIn(frag, r.stderr)

    def test_samples_need_flag(self):
        for sample in SAMPLES:
            out = os.path.join(self.tmp, "sample.html")
            r = run([sys.executable, BUILD, sample, out])
            self.assertEqual(r.returncode, 2)
            self.assertIn("模板占位内容", r.stderr)
            r = run([sys.executable, BUILD, sample, out, "--allow-placeholders"])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.getsize(out) > 0)

    def test_amap_page(self):
        r, page = self.build(self.data())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('id="btnOpen" href="amapuri://workInAmap/createWithToken?polymericId=abc&amp;from=MCP"', page)
        self.assertIn('id="linkBox"', page)
        self.assertIn('id="wechatTip" hidden', page)
        self.assertNotIn("出行提醒", page)
        self.assertIn('name="color-scheme" content="light dark"', page)

    def test_google_page(self):
        d = self.data(gmaps_url="https://www.google.com/maps/dir/?api=1&origin=A&destination=B")
        del d["amap_uri"]
        r, page = self.build(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('target="_blank"', page)
        self.assertNotIn('id="linkBox"', page)
        self.assertNotIn('id="wechatTip"', page)

    def test_typo_gets_suggestion(self):
        d = self.data(stages=[{"name": "去程", "stops": [{"name": "康定", "tip": "早睡"}]}])
        self.assertRejected(d, "stages[0].stops[0] 未知字段 tip（是不是 tips？）")
        self.assertRejected(self.data(ticket=[]), "未知字段 ticket（是不是 tickets？）")

    def test_required_fields(self):
        self.assertRejected(self.data(stages=[{"name": "去程", "stops": [{"km": "10km"}]}]),
                            "stages[0].stops[0] 缺少必填字段 name")
        self.assertRejected(self.data(weather=[{"text": "晴"}]), "weather[0] 缺少必填字段 city")

    def test_map_link_rules(self):
        d = self.data()
        del d["amap_uri"]
        self.assertRejected(d, "缺少地图链接")
        self.assertRejected(self.data(gmaps_url="https://www.google.com/maps"), "只能填一个")
        self.assertRejected(self.data(amap_uri="javascript:alert(1)"), "amapuri://")

    def test_https_only_links(self):
        self.assertRejected(self.data(stages=[{"name": "去程", "stops": [{"name": "A", "map_url": "http://x.com"}]}]),
                            "stages[0].stops[0].map_url 只收 https://")
        food = [{"city": "康定", "items": [{"name": "汤锅", "shops": [{"name": "店", "map_url": "amapuri://x"}]}]}]
        self.assertRejected(self.data(food=food), "food[0].items[0].shops[0].map_url")
        self.assertRejected(self.data(alerts=[{"text": "x", "url": "http://x"}]), "alerts[0].url")

    def test_enums(self):
        self.assertRejected(self.data(stages=[{"name": "去程", "color": "red"}]), "blue / green / orange")
        self.assertRejected(self.data(weather=[{"city": "成都", "kind": "guess"}]), "forecast / climate")
        self.assertRejected(self.data(alerts=[{"text": "x", "level": "high"}]), "severe / warn / info")

    def test_types(self):
        self.assertRejected(self.data(tips="只有一条"), "tips 应为数组")
        self.assertRejected(self.data(weather=[{"city": "成都", "day": True}]), "weather[0].day 应为文本或数字")

    def test_placeholders(self):
        d = self.data(weather_note="YYYY-MM-DD 查询", tips=["替换为实际贴士"])
        r, _ = self.build(d)
        self.assertEqual(r.returncode, 2)
        self.assertIn("weather_note：YYYY-MM-DD", r.stderr)
        self.assertIn("tips[0]：替换为…", r.stderr)
        r, _ = self.build(d, "--allow-placeholders")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_escaping(self):
        d = self.data(title='<script>alert(1)</script>', footer="来源<br>日期<i>x</i>",
                      stages=[{"name": "去程", "stops": [{"name": '"><img src=x onerror=alert(1)>'}]}])
        r, page = self.build(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("<script>alert(1)", page)
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertIn("来源<br>日期&lt;i&gt;x&lt;/i&gt;", page)

    def test_alerts(self):
        alerts = [{"level": "info", "text": "周日商店关门"},
                  {"level": "severe", "date": "10/2", "city": "稻城", "text": "暴雪封路", "url": "https://example.com/a"}]
        r, page = self.build(self.data(alerts=alerts))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(page.index("暴雪封路"), page.index("周日商店关门"))
        self.assertIn('class="alert severe"', page)
        self.assertIn('href="https://example.com/a"', page)
        r, page = self.build(self.data(alerts=[]))
        self.assertIn("暂无已公告的预警", page)

    def test_weather(self):
        weather = [{"city": "成都", "date": "10/1", "day": 24, "night": 17, "text": "多云", "kind": "forecast",
                    "sunrise": "06:30", "sunset": "18:40"},
                   {"city": "稻城", "text": "气候参考 晴", "kind": "climate"},
                   {"city": "理塘", "night": -5}]
        r, page = self.build(self.data(weather=weather))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("<small>10/1<span class=\"kind forecast\">预报</span></small>", page)
        self.assertIn("<b>24°</b>/17° 多云", page)
        self.assertIn("日出 06:30 · 日落 18:40", page)
        self.assertIn('class="kind climate">气候参考', page)
        self.assertIn("夜 -5°", page)

    def test_updated_at(self):
        r, page = self.build(self.data(updated_at="2026-09-24T07:00:00+08:00", alerts=[]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('<span class="upd" data-ts="1790204400000">更新于 09-24 07:00</span>', page)
        self.assertRejected(self.data(updated_at="2026-09-24 07:00"), "updated_at 需为带时区的 ISO 8601")
        r, page = self.build(self.data(updated_at="YYYY-MM-DDTHH:MM:00+08:00"), "--allow-placeholders")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('class="upd"', page)

    def test_underscore_fields_are_comments(self):
        r, _ = self.build(self.data(_comment="替换为说明，不渲染"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_default_output_and_bad_json(self):
        src = os.path.join(self.tmp, "trip.json")
        with open(src, "w", encoding="utf-8") as f:
            json.dump(MINIMAL, f, ensure_ascii=False)
        r = run([sys.executable, BUILD, src])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "trip.html")))
        with open(src, "w", encoding="utf-8") as f:
            f.write('{"title": "x",}')
        r = run([sys.executable, BUILD, src])
        self.assertEqual(r.returncode, 2)
        self.assertIn("JSON 格式错误", r.stderr)


FAKE_NPX = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_STATE/npx.log"
case "$*" in *"project create"*) touch "$FAKE_STATE/project" ;; esac
"""

FAKE_CURL = """#!/usr/bin/env bash
out=/dev/stdout fmt="" url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out=$2; shift 2 ;;
    -w) fmt=$2; shift 2 ;;
    -H|--max-time) shift 2 ;;
    -*) shift ;;
    *) url=$1; shift ;;
  esac
done
case "$url" in
  *api.cloudflare.com*)
    if [ -n "${FAKE_API_CODE:-}" ]; then code=$FAKE_API_CODE; body='{"success":false,"errors":[{"code":10000}]}'
    elif [ -f "$FAKE_STATE/project" ]; then code=200; body='{"success":true,"result":{"name":"demo","subdomain":"'"$FAKE_SUBDOMAIN"'"}}'
    else code=404; body='{"success":false,"errors":[{"code":8000007,"message":"Project not found"}]}'
    fi
    printf '%s' "$body" > "$out"
    [ -n "$fmt" ] && printf '%s' "$code"
    exit 0 ;;
  *)
    [ -f "${FAKE_PAGE:-/nonexistent}" ] || exit 7
    cat "$FAKE_PAGE" ;;
esac
"""


class DeployTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tmpdir(self)
        self.html = os.path.join(self.tmp, "trip.html")
        with open(self.html, "w", encoding="utf-8") as f:
            f.write("<html><head><title>川西 6 天自驾路书</title></head><body></body></html>\n")
        self.state = os.path.join(self.tmp, "state")
        os.mkdir(self.state)
        self.bin = os.path.join(self.tmp, "bin")
        os.mkdir(self.bin)
        for name, body in (("npx", FAKE_NPX), ("curl", FAKE_CURL), ("sleep", "#!/bin/sh\nexit 0\n")):
            path = os.path.join(self.bin, name)
            with open(path, "w") as f:
                f.write(body)
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def deploy(self, *args, **env):
        e = dict(os.environ)
        for k in ("DRY_RUN", "VERIFY", "VERCEL_SCOPE"):
            e.pop(k, None)
        e.update(PATH=self.bin + os.pathsep + e["PATH"], FAKE_STATE=self.state,
                 CLOUDFLARE_API_TOKEN="t", CLOUDFLARE_ACCOUNT_ID="a", VERCEL_TOKEN="v")
        e.update(env)
        return run(["bash", DEPLOY] + list(args), env=e)

    def page(self, title):
        path = os.path.join(self.tmp, "remote.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write("<html><head><title>%s</title></head></html>\n" % title)
        return path

    def npx_log(self):
        path = os.path.join(self.state, "npx.log")
        if not os.path.exists(path):
            return ""
        with open(path) as f:
            return f.read()

    def test_syntax_and_args(self):
        self.assertEqual(run(["bash", "-n", DEPLOY]).returncode, 0)
        self.assertEqual(self.deploy("cloudflare", self.html).returncode, 2)
        self.assertEqual(self.deploy("cloudflare", self.html, "Bad_Name").returncode, 2)
        self.assertEqual(self.deploy("cloudflare", "/nonexistent.html", "demo").returncode, 2)
        self.assertEqual(self.deploy("ftp", self.html, "demo").returncode, 2)

    def test_dry_run(self):
        r = self.deploy("cloudflare", self.html, "demo", DRY_RUN="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("+ npx --yes wrangler@4 pages deploy", r.stdout)
        r = self.deploy("vercel", self.html, "demo", DRY_RUN="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("--scope", r.stdout)
        r = self.deploy("vercel", self.html, "demo", DRY_RUN="1", VERCEL_SCOPE="team")
        self.assertIn("--scope team", r.stdout)
        self.assertEqual(self.npx_log(), "")

    def test_missing_token(self):
        r = self.deploy("cloudflare", self.html, "demo", CLOUDFLARE_API_TOKEN="")
        self.assertEqual(r.returncode, 1)
        self.assertIn("缺少环境变量 CLOUDFLARE_API_TOKEN", r.stderr)

    def test_cloudflare_existing_project_uses_real_subdomain(self):
        open(os.path.join(self.state, "project"), "w").close()
        r = self.deploy("cloudflare", self.html, "demo", FAKE_SUBDOMAIN="demo-x1y.pages.dev",
                        FAKE_PAGE=self.page("川西 6 天自驾路书"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("正式链接: https://demo-x1y.pages.dev", r.stdout)
        self.assertIn("已验证", r.stdout)
        self.assertNotIn("project create", self.npx_log())
        self.assertIn("pages deploy", self.npx_log())

    def test_cloudflare_creates_missing_project(self):
        r = self.deploy("cloudflare", self.html, "demo", FAKE_SUBDOMAIN="demo.pages.dev",
                        FAKE_PAGE=self.page("川西 6 天自驾路书"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pages project create demo", self.npx_log())
        self.assertIn("正式链接: https://demo.pages.dev", r.stdout)

    def test_cloudflare_lookup_error_does_not_create(self):
        # 令牌无权读取等非“项目不存在”的错误：不创建项目，退回项目名并靠标题校验兜底
        r = self.deploy("cloudflare", self.html, "demo", FAKE_API_CODE="403",
                        FAKE_PAGE=self.page("川西 6 天自驾路书"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("project create", self.npx_log())
        self.assertIn("正式链接: https://demo.pages.dev", r.stdout)

    def test_title_mismatch_exits_3(self):
        r = self.deploy("vercel", self.html, "demo", FAKE_PAGE=self.page("别人的网站"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("不是本次页面", r.stderr)

    def test_unreachable_only_warns(self):
        r = self.deploy("vercel", self.html, "demo")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("访问不到", r.stderr)
        r = self.deploy("vercel", self.html, "demo", VERIFY="0", FAKE_PAGE=self.page("别人的网站"))
        self.assertEqual(r.returncode, 0, r.stderr)


def importable(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


class ToolsTest(unittest.TestCase):
    def test_make_qr_args(self):
        r = run([sys.executable, os.path.join(SCRIPTS, "make_qr.py")])
        self.assertEqual(r.returncode, 2)

    @unittest.skipUnless(importable("qrcode"), "未安装 qrcode")
    def test_make_qr_png(self):
        out = os.path.join(tmpdir(self), "qr.png")
        r = run([sys.executable, os.path.join(SCRIPTS, "make_qr.py"), "https://trip-demo.pages.dev", out])
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")

    def test_package(self):
        tmp = tmpdir(self)
        stray = os.path.join(SCRIPTS, "__pycache__")
        created = not os.path.exists(stray)
        os.makedirs(stray, exist_ok=True)
        if created:
            self.addCleanup(shutil.rmtree, stray)
        open(os.path.join(stray, "junk.pyc"), "w").close()
        out = os.path.join(tmp, "skill.zip")
        r = run([sys.executable, os.path.join(ROOT, "tools", "package.py"), out])
        self.assertEqual(r.returncode, 0, r.stderr)
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
        for must in ("travel-roadbook/SKILL.md", "travel-roadbook/references/domestic.md",
                     "travel-roadbook/scripts/build_roadbook.py", "travel-roadbook/assets/roadbook.sample.json"):
            self.assertIn(must, names)
        self.assertFalse([n for n in names if "__pycache__" in n or n.endswith(".pyc")])


@unittest.skipUnless(importable("playwright"), "未安装 Playwright")
class CheckPageTest(unittest.TestCase):
    def test_samples_pass(self):
        tmp = tmpdir(self)
        for sample in SAMPLES:
            out = os.path.join(tmp, os.path.basename(sample).replace(".json", ".html"))
            r = run([sys.executable, BUILD, sample, out, "--allow-placeholders"])
            self.assertEqual(r.returncode, 0, r.stderr)
            r = run([sys.executable, os.path.join(SCRIPTS, "check_page.py"), out, "--shots", tmp])
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
