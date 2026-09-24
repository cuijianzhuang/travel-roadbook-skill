# 实时数据（每日自动更新）

通用流程第 6 步读本文（第 5 步构建页面前也要先定好模式）；用户改行程时看末尾“行程变更”。

## 原则：静态与动态分离

| 数据 | 放哪 | 为什么 |
|---|---|---|
| 行程、景点、美食、穿着、签证清单、门票规则 | 写死在 HTML | 不会变 |
| 天气（含日出日落）、汇率、出行提醒 | 实时数据 | 每天会变 |
| amapuri / Google Maps 链接 | 写死 | 链接不变，打开即实时导航 |
| 门票余量 | 不做 | 无可靠来源，只放官网链接 + 开售时间 |

禁止在页面脚本里直接 fetch 第三方天气/汇率接口：发布后的页面会拦截外部请求，不可靠。

## 选模式

- **模式 A：页面数据库 + 每日任务（默认）**。页面声明 `db` 能力，易变数据存在 db 里，页面订阅后自动刷新。限制：声明 db 的页面**只能在组织内分享、不能公开链接**，看的人需登录同组织 claude.ai 账号。
- **模式 B：每日重新发布整页**。同行者没有同组织账号、需要公开链接时用。页面不声明 db，每日任务把最新数据写进 HTML 后重新发布到同一链接。发布目标二选一：
  - **Artifact**（默认）：原链接重新发布。
  - **Cloudflare Pages / Vercel**：用户要完全公开、无需任何账号、或要绑自定义域名时用；每日任务更新路书 JSON → `build_roadbook.py` 重新生成 → `deploy.sh` 以同一项目名重新发布，链接不变。前提：定时任务的运行环境能拿到路书 JSON（放在用户的 Git 仓库里）、Node.js 和部署令牌（配置为环境密钥），否则退回 Artifact。

需求询问阶段已问过同行者账号情况；没问到就默认模式 A，并在交付时说明分享限制与模式 B 的切换方式。

## 数据结构（两种模式共用）

- `weather` 条目：`{city, date, day, night, text, sunrise?, sunset?, kind:"forecast"|"climate"}`
- `alerts` 条目：`{level:"info"|"warn"|"severe", date, city, text, url}`
- `fx`（欧洲/境外）：`{base:"CNY", rates:{EUR, CHF, GBP, ...}}`
- 更新时间一律 ISO 8601 带时区。

模式 A 存进 db 文档；模式 B（Cloudflare / Vercel）直接写进路书 JSON 的 `weather[]`、`alerts[]` 和 `updated_at`，字段相同（静态版天气可多一个显示用的 `label`，缺省用 `date`）。静态页不做汇率换算，预算表写明汇率日期。

## 模式 A 实现

**构建前先加载 artifact-capabilities 技能**，读 db 的类型定义后再写代码；以下为约定，API 细节以技能为准。

1. **声明能力**（只允许编辑者写，所有人可读）：
```json
{"db": {"rules": [{"path": "", "read": "view", "write": "admin"}]}}
```
2. **文档结构**（集合 `live`）：
   - `live/meta`：`{tripStart, tripEnd, timezone, lastRun, lastStatus}`
   - `live/weather`：`{updatedAt, source, items:[weather 条目]}`
   - `live/fx`（欧洲/境外）：`{updatedAt, source, base:"CNY", rates:{...}}`
   - `live/alerts`：`{updatedAt, items:[alerts 条目]}`
3. **页面行为**：
   - HTML 内嵌一份构建时的数据作为兜底，先渲染兜底，`claude.use("db")` 返回后再用 db 数据覆盖；返回 `null` 时保持兜底并显示“离线快照 · 查询于 X”。
   - 每个文档**只订阅一次**（`onSnapshot`），不在渲染函数里订阅。
   - 每个实时模块旁显示“更新于 MM-DD HH:mm”；`updatedAt` 超过 36 小时显示“数据可能过期”。
   - 预算表的人民币金额由外币金额 × `live/fx` 汇率在页面里计算，不写死。
   - 天气项按 `kind` 区分样式：`climate` 标“气候参考”，`forecast` 标“预报”。
4. **写入初始数据**：发布后用 ArtifactData 的 batch 写入 `live/*` 四个文档（数据来自本次采集）。
5. **功能校验**：ArtifactData list 一次 `live` 集合，确认四个文档都在、字段正确；一句话告诉用户验证了什么。

## 每日定时任务

用 create_trigger 建一个定时任务（先 ToolSearch 查看可用的定时工具与参数）：
- **时间**：每天 07:00 用户本地时间（北京时间换算 UTC 为前一天 23:00，cron `0 23 * * *`）。
- **周期**：从现在到行程最后一天；超出后任务自行停用。
- **名称**：`路书数据更新 · <行程名>`
- **prompt 必须独立完整**（每次运行是全新会话，看不到本次对话），包含：
  1. 路书 Artifact 链接与模式（A 写 db / B 重新发布）。
  2. 行程节点清单：`日期 · 城市 · 国内用高德 city 名 / 境外用英文名 + 国家`。
  3. 数据来源：国内天气用高德 `maps_weather`（先 ToolSearch 取 schema）；境外天气优先用已连接的 Google Maps 天气工具（先 ToolSearch 确认存在），没有则 WebSearch；日出日落、汇率、罢工与预警用 WebSearch/WebFetch 查官方或权威来源。
  4. 更新规则：
     - 只把进入预报窗口的日期从 `climate` 换成 `forecast`，其余保留原值不动。
     - 查不到的数据保留旧值，不编造；`alerts` 只收已公告、有来源链接的事项，过期的移除。
     - 模式 A：用 ArtifactData batch 更新 `live/weather`、`live/fx`、`live/alerts`、`live/meta`（写 `lastRun`、`lastStatus`）。
     - 模式 B（Artifact）：读取 Artifact 当前页面，只替换内嵌数据块与更新时间后原链接重新发布，不改其他内容。
     - 模式 B（Cloudflare / Vercel）：写明仓库、JSON 路径、平台与项目名；只改 JSON 中的 `weather`、`alerts`、`updated_at` → `build_roadbook.py`（校验不过就按报错修 JSON）→ `deploy.sh <平台> <html> <项目名>` → 提交 JSON 改动。deploy.sh 发布后会比对线上页面标题，退出码非 0 按失败处理。
  5. **推送条件**：新增 `severe` 预警、行程日天气出现暴雨/暴雪/高温红色等、抢票日历里有项目在未来 24 小时内开售（写明项目、当地与北京时间、官网链接），或连续 2 天更新失败时，用 SendUserMessage 简短告诉用户；否则静默。prompt 里要附上抢票日历（项目 · 开售时间 · 官网）。
  6. **自行停用**：当前日期晚于 `tripEnd` 时，用 list_triggers 找到本任务并 update_trigger 设 `enabled:false`，然后结束。
- **地图工具必须是连接器**：高德 / Google Maps 必须是用户在 claude.ai 添加的连接器，定时任务的新会话才能用；否则任务改用 WebSearch 查天气并在 `source` 注明。
- 任务建好后告诉用户：运行时间、截止日、需要“自动批准”才能无人值守写数据。

## 行程变更

用户改了行程（日期、城市）时：更新页面静态部分并重新发布 → 同步 `live/meta` 与节点 → 用 update_trigger 更新任务 prompt 中的节点清单和截止日，不要删了重建。
