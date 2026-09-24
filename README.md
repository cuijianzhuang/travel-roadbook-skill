# Travel Roadbook Skill · 旅行路书规划（国内 + 欧洲 + 实时数据）

一个面向 AI Agent 的旅行规划 Skill：把一句“帮我规划国庆自驾”或“12 天法瑞意怎么玩”变成**经过核实的行程**，并产出手机可打开的路书网页；天气、汇率、出行提醒由每日定时任务自动刷新。

基于 [SpaceZephyr/travel-roadbook-skill](https://github.com/SpaceZephyr/travel-roadbook-skill)（MIT）改写。

## 能力

| 分支 | 核实重点 | 地图 |
|---|---|---|
| 国内（高德） | 逐段驾车实测里程、单日时长、过夜中点、高原海拔阶梯、节假日错峰、“绕开 vs 过境”对比 | 高德 `amapuri://` 一键打开行程 |
| 欧洲 / 国外 | Google Maps 实测里程时长、城市数量与节奏、开口程、火车订座、申根主申请国与行程单一致、热门景点开售时间、ZTL/Crit'Air/Vignette | 每日 Google Maps 路线链接 + 全程总览 |

**实时数据**：静态行程写死在页面；天气（含日出日落）、汇率、罢工/预警存在页面数据库里，由每日 07:00 的定时任务更新，行程结束后任务自动停用。同行者没有同组织账号时，改为每日重新发布整页。

## 工作流

1. 需求询问（一次问齐）
2. 核实与质疑（给替代方案和数字对比，由用户拍板）
3. 信息采集（高德 MCP / 官网 / 可追溯来源，不编造）
4. 生成地图链接
5. 构建手机路书网页并发布
6. 接入实时更新（写初始数据 + 建每日任务）
7. 交付

## 目录结构

```
travel-roadbook/
├── SKILL.md                    # 技能入口：分流、通用流程、国内/欧洲分支规则、实时数据方案、附带脚本
├── references/                 # 上游参考文档：高德工具、规划规则、路书规范
├── assets/
│   ├── roadbook.sample.json        # 路书数据模板（国内 · 高德）
│   └── roadbook.google.sample.json # 路书数据模板（国外 · Google Maps）
└── scripts/
    ├── build_roadbook.py       # JSON → 静态路书 HTML（高德 / Google Maps）
    ├── deploy.sh               # 发布到 Cloudflare Pages / Vercel
    └── make_qr.py              # 发布链接 → 二维码 PNG
```

## 安装

把 `travel-roadbook/` 目录放入 Agent 的技能目录，新会话中说“帮我做旅行/自驾路书”“X 天去 Y 地怎么玩”即触发。

## 运行依赖

- 国内分支：高德地图 MCP（地理编码、驾车规划、天气、POI、行程地图）
- 欧洲 / 国外分支：Google Maps MCP（地点、路线、距离矩阵，可选；未接入时里程标注“参考”）+ Web 搜索 / 网页读取
- 公开发布（可选）：Node.js + Cloudflare（`CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`）或 Vercel（`VERCEL_TOKEN`）令牌
- 实时数据：支持 Artifact 运行时能力（`db`）与定时任务的 Claude 环境；其他环境退化为静态页面并注明数据查询日期

## 设计原则

- 里程、天气、门票价格、开售时间必须来自工具或可追溯来源；查不到写“以官方为准”。
- 当地美食推荐：按城市列代表菜，推荐店必须经高德 / Google Maps 检索查实，附人均、营业时间与一键导航。
- 签证、驾照、入境政策只给“需核实要点 + 官方入口”，不下法律结论。

## License

[MIT](LICENSE)
