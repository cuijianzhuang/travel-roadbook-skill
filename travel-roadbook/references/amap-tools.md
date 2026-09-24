# 高德地图工具链（旅行路书专用）

> 调用任何高德 MCP 工具前，若其参数 schema 不在当前上下文，先用 `tool_search` 搜工具名取回真实 schema，禁止凭记忆构造参数。本文记录的字段以实战返回为准，若与 schema 冲突以 schema 为准。

## 工具总览

| 用途 | 工具 | 关键入参（约） | 取什么 |
|---|---|---|---|
| 地名→坐标 | `maps_geo` | `address`，可选 `city` | `geocodes[].location`，形如 `"114.05,22.54"`（GCJ-02 经纬度，逗号分隔） |
| 驾车里程/时长 | `maps_direction_driving` | `origin`、`destination`，均为 `"经度,纬度"` | `route.paths[0]` 的 `distance`（米）、`duration`（秒），换算 km/h |
| 城市天气 | `maps_weather` | `city`（城市名或 adcode） | `forecasts[]`：`date`、`dayweather`/`nightweather`、`daytemp`/`nighttemp` |
| POI 检索 | `maps_text_search` | `keywords`、`city`、可选 `citylimit` | `pois[].id`（即 poiId）、`name`、`address` |
| 生成行程地图 | `maps_schema_personal_map` | `orgName`、`lineList` | 一段 `amapuri://workInAmap/createWithToken?polymericId=...` 链接 |

## 标准作业顺序

1. **列节点**：从行程草案提取全部过夜城市/景区节点（去程、游玩、返程按时间顺序）。
2. **取坐标**：对每个节点调 `maps_geo`（城市锚点优先用"XX市人民政府"，景区用全称，如"香格里拉虎跳峡景区"）。
3. **取 poiId**：对每个节点调 `maps_text_search`，取 `pois[0].id`。注意 text_search **不返回坐标**，坐标必须另调 geo；geo 与 text_search 是两条独立数据。
4. **逐段实测里程**：对相邻节点依次调 `maps_direction_driving`，把 km 与小时数写进路书 JSON 的 `km` 字段（格式 `"643km · 约6.7h"`）。多节点可并行调用。
5. **查天气**：对沿途城市调 `maps_weather`，组装天气卡片。
6. **生成行程地图**：见下。

## maps_schema_personal_map 的 lineList 结构

```json
{
  "orgName": "深圳→香格里拉14天自驾",
  "lineList": [
    {
      "title": "去程",
      "pointInfoList": [
        {"name": "深圳", "lon": 114.057951, "lat": 22.543550, "poiId": "B02F300691"}
      ]
    }
  ]
}
```

- `lon`/`lat` 是**数字**（不是字符串），`poiId` 来自 text_search。
- 可按去程/游玩/返程拆多条 line，也可一条线串全程；节点顺序必须与行程一致。
- 返回的 `amapuri://...` 链接**直接给用户、不要改写或二次编码**。

## 已知坑（实测）

1. **天气只有未来约 4 天预报**。行程更长时，覆盖不到的日期用"同期气候参考"（可搜索历年同期气温），并在 `weather_note` 显式注明查询日期与"出发前再更新"。
2. **amapuri 是自定义协议，不是 http(s)**：交付工具 `present_files` 会拒绝（invalid-link）。正确做法是把它写进路书网页的按钮 href（HTML 中 `&` 要转义为 `&amp;`，构建脚本已自动处理），发布网页后交付 https 链接。
3. **里程不要信用户给的表格或直线估算**，必须逐段驾车实测。真实案例：用户表"丽江→广南 480km"，实测 863km（低估 80%）；"广南→阳朔 380km"，实测 804km（低估 112%）。
4. 景区节点 geo 不到时，改用景区大门/游客中心全称或就近城镇锚点。
5. 驾车时长是理想路况，节假日需人工上浮（拥堵省界、热门景区周边按 +20%~40% 估）。
