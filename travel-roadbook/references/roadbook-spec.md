# 路书内容规范与发布流程

## 一、需求询问（动手前一次问清）

用 `interaction.ask` 一次性问齐关键项（最多 4 个问题，可多选），不要边做边问：

1. **出发地、目的地**（单一目的地/环线/多目的地）、**具体出发日期与总天数**。
2. **出行方式**：自驾（车型、能否接受单日 700km+ 赶路日、几位司机）/ 高铁或飞机+当地租车 / 公共交通。
3. **人数与构成**：成人、老人、小孩；是否有人未上高原、慢性病或行动限制。
4. **旅行目的与偏好**：自然风光/人文古迹/美食/摄影/亲子/休闲；必去清单、**明确不想去的地方**（并澄清是"可过境"还是"完全绕开"，见 planning-rules.md）；住宿档次与总预算。

用户给了现成行程表/文档时，先完整读取，再进入核实环节，不要让用户重述。

## 二、路书 JSON 字段规范

模板示例：`assets/roadbook.sample.json`。构建：`python3 scripts/build_roadbook.py <data.json> [out.html]`。

| 字段 | 说明 |
|---|---|
| `title` / `eyebrow` / `title_lines` / `subtitle` | 网页标题、页眉小字、主标题（数组，逐行）、一句话摘要（含出发日、总里程、节奏） |
| `amap_uri` | maps_schema_personal_map 返回的完整 amapuri 链接 |
| `weather[]` | `city`、`label`（如"10/1 宿"）、`day`/`night`（数字）、`text` |
| `weather_note` | 天气数据查询日期、4 天预报窗口说明、温差穿衣总提示 |
| `stages[]` | 分段（去程/游玩/返程），`name`、`color`（blue/green/orange）、`stops[]` |
| `stops[]` | `date`、`time`（出发/夜宿/到达/游玩）、`name`、`km`（里程或班次）、`weather`/`spots`/`food`/`tickets`/`tips`（均可选，缺省不渲染） |
| `tickets[]` | `name`、`price`、`book`（预约/区间车说明）；`tickets_total` 人均合计；`budget_note` 价格时效声明 |
| `clothing[]` | `group`（场景+温度）、`items`（分层穿搭与装备） |
| `tips[]` | 注意事项条目（行车、高反、车况、预约、应急） |
| `footer` | 数据来源与查询日期；可用 `<br>` 换行 |

内容口径（硬要求）：

- **不编造**：天气、里程、门票价格必须来自工具或可追溯来源；查不到就写"以官方为准"或留空，禁止杜撰具体数字。
- 门票价格标注查询年份/日期与"节假日可能浮动"；区间车、索道、骑马等二次消费单列。
- 美食按当地真实特色与**当季**写（不要把季节限定写反）；每站 3–4 项即可。
- 穿着按**最低夜温 + 场景**给分层建议（速干内层/抓绒/冲锋衣/羽绒），并给防晒、雨具、鞋履。
- 每站贴士覆盖：当日驾驶风险、海拔、预约、停车、体力分配。

## 三、构建与自检

1. 在工作区建语义化任务目录（如 `sichuan-roadtrip/`），JSON 与输出 HTML 放其中。
2. 运行 `build_roadbook.py` 生成单文件自包含 HTML（文件名语义化，如 `稻城亚丁自驾路书.html`，不要用 index.html）。
3. 用 html 技能的截图脚本自检（桌面+移动）：
   `python3 <html技能目录>/scripts/shot.py <html路径>`
   - 关注 `consoleErrors`、`horizontalOverflow`、`timelineBrokenAxis`；移动端是主要使用场景，必看移动截图。
   - 脚本失败可跳过自检直接交付，但不得另写截图脚本或用浏览器自动化替代。

## 四、发布成手机可打开的链接

1. `cd` 到 HTML 所在目录（路径只接受相对路径）。
2. 首发：`lark-cli apps +deploy --file-path ./xxx.html`；记住返回的 `app_id`。
   迭代：加 `--app-id app_xxx` 复发布到同一应用（链接不变）。
3. 返回 `release_id` 后用 `lark-cli apps +release-get --app-id <id> --release-id <rid>` 轮询（间隔 ≥3s）到 `status=finished`，取 `online_url`；再用 `curl -sL -o /dev/null -w "%{http_code}"` 验证 200。
4. 详细发布规则见 html 技能 `references/lark-apps-publish.md`。

## 五、二维码（可选，用户要手机扫码时）

`python3 scripts/make_qr.py <online_url> 二维码.png`（依赖 `pip3 install 'qrcode[pil]'`）。
**编码发布后的 https 链接**，不要编码 amapuri（手机相机扫自定义协议不可靠）。

## 六、交付

- 用 `present_files` 交付发布后的 https 链接（和二维码 PNG，如有）。amapuri 原始链接只能写在网页按钮里，不能作为交付链接。
- 最终回复 ≤300 字、≤8 行，简述页面包含的模块与数据查询日期；远期天气、价格等不确定项要一句话提示。
