# 附带脚本

路径相对于本技能目录（`travel-roadbook/`）；运行前先确认 `python3` 可用。

## build_roadbook.py：JSON → 静态路书 HTML

```bash
python3 scripts/build_roadbook.py <data.json> [输出.html]
```

- **适用**：静态版路书（无 Artifact 环境、用户只要 HTML 文件、或模式 B 每日重新生成整页）。页面自带：地图“一键打开行程”按钮、封面关键标签、航班、抢票日历、出行提醒、天气速览、逐站时间轴、当地美食、住宿、门票花费表、穿着建议、拍摄设备、注意事项；没填的模块不显示；自动适配深色模式。
- **地图二选一**：
  - 国内填 `amap_uri`（高德 amapuri 链接），模板 `assets/roadbook.sample.json`。页面另有复制备用链接卡片（amapuri 在部分浏览器点了没反应时复制到别的浏览器打开）、只在微信/QQ 等 App 内显示的“用浏览器打开”提示、点按钮后没跳转时的兜底提示。
  - 国外填 `gmaps_url`（Google Maps 全程总览 https 链接），模板 `assets/roadbook.google.sample.json`；按钮自动切换为“在 Google 地图中打开行程”，不附加打开提示，也不设备用卡片。
- **不适用**：欧洲完整版的签证清单、城际交通表、汇率换算等模块，以及模式 A（不接 db）；需要这些时按分支文档手写页面。
- **用法**：复制对应模板为本次数据文件，把字段全部替换成本次采集的真实数据：`amap_uri` 填 `maps_schema_personal_map` 返回的原始链接，`gmaps_url`/`map_url` 按分支文档拼接，里程、天气、票价按“内容口径”填写。不传输出路径时，输出到 JSON 同目录同名 `.html`。
- **构建前自动校验**，不通过就报错退出（退出码 2）并列出字段路径，按提示改 JSON 后重跑：
  - 未知字段（多半是拼错，会提示最接近的字段名）、缺必填字段、枚举值不合法；
  - 链接协议：`amap_uri` 只收 `amapuri://`，其余链接只收 `https://`，两种地图链接必须二选一；
  - 时间格式：`updated_at`、`bookings[].on_sale` 须为带时区的 ISO 8601；
  - 模板占位内容：`REPLACE_WITH…`、`YYYY-MM-DD`、`HH:MM`、`LNG,LAT`、`YY`、“替换为…”“按…实查”“示例”。`--allow-placeholders` 只用于构建示例，成品不能用。
- 所有文本字段会做 HTML 转义；`footer` 里只有 `<br>` 会保留为换行。以 `_` 开头的字段当注释，不渲染也不校验。
- 给了 `updated_at` 时，天气与出行提醒旁显示“更新于 MM-DD HH:mm”，页面打开时距更新超过 36 小时会标“可能已过期”。
- 生成后按下面的 `check_page.py` 自检，再发布或交付文件。

### JSON 字段

| 字段 | 说明 |
|---|---|
| `title` / `eyebrow` / `title_lines` / `subtitle` | 网页标题（发布后也用它核对线上页面）、页眉小字、主标题（数组，逐行）、一句话摘要（出发日、总里程、节奏） |
| `tags[]` | 封面关键标签，如“主申请国：意大利”“节庆：威尼斯狂欢节 2/7–2/17”“最高海拔 4600m” |
| `flights[]` | 航班：`date`、`no`（航班号，都必填）、`from`/`to`（机场与航站楼）、`dep`/`arr`（起降时间）、`note`（转机偏紧、凌晨出门等提醒）；`flights_note` 写总提醒 |
| `bookings[]` | 抢票日历：`item`（必填）、`on_sale`（开售时间，必填，ISO 8601 带当地时区，如 `2026-03-15T09:00:00+01:00`）、`visit`（参观日）、`rule`（放票规则）、`url`（官方预约）。按开售时间排序，非北京时区自动附北京时间，页面打开时显示“还有 N 天/24 小时内/已开售”；`bookings_note` 写查询日期 |
| `amap_uri` | 国内：`maps_schema_personal_map` 返回的原始 amapuri 链接 |
| `gmaps_url` | 国外：Google Maps 全程总览 https 链接 |
| `updated_at` | 天气、提醒等易变数据的查询时间，ISO 8601 带时区，如 `2026-09-24T07:00:00+08:00` |
| `alerts[]` | 出行提醒：`level`（`info` 提示 / `warn` 注意 / `severe` 严重，缺省 `info`）、`date`、`city`、`text`（必填）、`url`（来源）。按严重程度排序显示；空数组显示“暂无已公告的预警、罢工或临时关闭”，不写这个字段则不显示模块 |
| `weather[]` | `city`（必填）、`label`（如“10/1 宿”，缺省用 `date`）、`day`/`night`、`text`、`kind`（`forecast` 预报 / `climate` 气候参考）、`sunrise`/`sunset` |
| `weather_note` | 查询日期、预报窗口说明、温差穿衣总提示 |
| `stages[]` | 分段（去程/游玩/返程）：`name`（必填）、`color`（`blue` / `green` / `orange`）、`stops[]` |
| `stops[]` | `name`（必填）、`date`、`time`（出发/夜宿/到达/游玩）、`km`（里程或班次）、`weather`/`spots`/`food`/`tickets`/`tips`（缺省不渲染）、`map_url`（当日路线，蓝色“地图”按钮）、`map_label`（按钮文字，≤12 字，过长省略） |
| `food[]` | 当地美食推荐：`city`（必填）、`items[]`：`name`（必填）、`tags[]`、`desc`、`shops[]`：`name`（必填）、`note`、`map_url`；`food_note` 写来源与查询日期 |
| `stays[]` | 住宿：`city`、`name`（都必填）、`dates`（如“3/10–3/13 · 3 晚”）、`status`（`booked` 已订 / `first` 首选 / `backup` 备选）、`price`（起价，注明床位/整间与查询日期）、`note`（理由、入住截止、寄存、城市税、免费取消）、`map_url`；`stays_note` 写来源 |
| `tickets[]` | `name`（必填）、`price`、`book`（预约/区间车说明）；`tickets_total` 人均合计；`budget_note` 价格时效声明 |
| `clothing[]` | `group`（场景 + 温度）、`items`（分层穿搭与装备），都必填 |
| `gear[]` | 拍摄与记录设备：`group`、`items`，都必填（用户要求时才加） |
| `tips[]` | 注意事项条目 |
| `footer` | 数据来源与查询日期 |

## check_page.py：页面自检

```bash
python3 scripts/check_page.py <路书.html> [--shots 截图目录]
python3 scripts/check_page.py <路书.html> --js-only    # 只查脚本语法
```

- **脚本语法**（不需要浏览器）：每个内联 `<script>` 跑 `node --check`，报出第几个脚本、第几行、出错代码；最常见的是单引号字符串里的撇号没转义（'Wombat's'、'All'Arco'）。`<script type="application/json">` 数据块用 JSON 解析校验。没装 node 时跳过并提示。`deploy.sh` 发布前会自动跑 `--js-only`。
- **页面检查**：用 Playwright + Chromium 以 375px 手机宽度，在浅色、深色模式各打开一次：检查横向滚动（列出超出屏幕的元素）、控制台报错、链接协议（只允许 https、amapuri、tel、mailto、页内锚点），并保存两张整页截图（默认与 HTML 同目录）。
- 退出码 0 通过、1 有问题（按输出修）、3 没装 Playwright 或浏览器（脚本语法已查，页面检查跳过，按第 5 步清单人工自检）。浏览器装在别处时用环境变量 `CHROMIUM_PATH` 指定。
- 看一眼两张截图：排版、深色模式可读、按钮文字没被截断。手写的 Artifact 页面也能用它检查。

## deploy.sh：发布到 Cloudflare Pages / Vercel

```bash
bash scripts/deploy.sh cloudflare <路书.html> <项目名>   # → https://<项目名>.pages.dev（名字被占用时见输出）
bash scripts/deploy.sh vercel     <路书.html> <项目名>   # → https://<项目名>.vercel.app（名字被占用时见输出）
```

- **何时用**：用户要不登录就能打开的公开链接、同行者没有 claude.ai 账号、或要绑自定义域名。能用 Artifact 且用户没提这些需求时，仍优先 Artifact。
- **选平台**：用户已有哪个账号就用哪个；都没有时推荐 Cloudflare Pages（免费额度够用）。
- **令牌**：只从环境变量读取——Cloudflare 需 `CLOUDFLARE_API_TOKEN`（权限 Cloudflare Pages: Edit）与 `CLOUDFLARE_ACCOUNT_ID`；Vercel 需 `VERCEL_TOKEN`，团队账号加 `VERCEL_SCOPE`。缺少时告诉用户去哪里创建，并配置为运行环境的密钥；**不要让用户把令牌贴进对话，不要写进文件或提交到仓库**。
- **项目名**：小写字母、数字、连字符，如 `trip-2026-chuanxi`；同名重复发布即覆盖更新，链接不变。行程改版时用原项目名。
- **正式链接以脚本输出为准**：`pages.dev`、`vercel.app` 子域名全球唯一，名字被别的账号占用时实际链接会不同。Cloudflare 由脚本通过 API 查出真实子域名；Vercel 以输出里的 Production 链接为准。
- **发布前**：先跑 `check_page.py --js-only`，页面脚本有语法错误就不发布（退出码 1）。
- **自动验证**：发布后脚本抓取正式链接、比对 `<title>` 与本地页面。退出码 0 且输出“已验证”才交付；退出码 3 表示这个链接是别人的站，改用输出里的链接；提示“访问不到”时（多为运行环境网络限制）在手机上打开确认后再交付。`VERIFY=0` 可跳过。
- **只发布 `index.html`**：脚本在临时目录里只放路书页面，JSON 等源文件不会公开。
- **隐私提醒**：公开链接任何人拿到都能打开，发布前提醒用户页面里有日期、住宿、人员等信息，敏感内容可删减或改用 Artifact。
- **国内访问**：`*.vercel.app`、`*.pages.dev` 在中国大陆访问可能不稳定；同行者在国内时建议绑定自定义域名，或改用 Artifact。
- 先用 `DRY_RUN=1 bash scripts/deploy.sh ...` 可只打印命令不联网，用来检查参数。要扫码时对正式链接运行 `make_qr.py`。

## make_qr.py：发布链接 → 二维码 PNG

```bash
pip3 install 'qrcode[pil]'   # 首次使用
python3 scripts/make_qr.py <已发布的https链接> <输出.png>
```

- 只编码发布后的 **路书网页 https 链接**，不要编码 `amapuri://`（iOS 相机无法可靠识别），也不要编码 Google Maps 链接。
- 二维码 PNG 随交付一起给用户，注明对应的链接。
