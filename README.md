# 中国分钟级降水预报 (cn_minute_rain)

Home Assistant 自定义集成，基于[中国天气网分钟级降水 API](https://mpf.weather.com.cn) 提供未来 2 小时临近降雨预报。支持**多地点**，每个地点自动生成两个实体：

- **`<地点>临近降雨`**：状态为预报文案（如“未来2小时不会降雨”），属性含 `values`（强度数组）、`time`、`longitude`、`latitude`。
- **`<地点>降雨提示`**：由强度数组推算的人话状态 —— `无雨` / `🌧️ 正在下雨，预计持续约 X 分钟` / `⏳ 约 Y 分钟后开始下雨`，图标随状态切换。

示例卡片（无雨时状态为“无雨”，可用 `state` 条件让卡片自动隐藏）：

```yaml
type: entities
entities:
  - entity: sensor.shen_zhen_zhan_yuan_ge_lin_jin_jiang_yu
  - entity: sensor.shen_zhen_zhan_yuan_ge_jiang_yu_ti_shi
```

---

## 安装

### 方式一：HACS（推荐）

1. 打开 HACS → 右上角「⋮」→「自定义仓库」(Custom repositories)。
2. 仓库地址填入：

   ```
   https://cnb.cool/dtapp/cn_minute_rain
   ```

3. 类别选择 **集成 (Integration)**，点击「添加」。
4. 在 HACS 的「集成」列表里搜索 **中国分钟级降水预报**，点击「下载」并重启 Home Assistant。
5. 「设置 → 设备与服务 → 添加集成」，搜索 **中国分钟级降水预报**，按提示填写地点即可。

> 若你的 HACS 版本仅对接 GitHub，无法直接添加 cnb.cool 仓库，请改用下方的**手动安装**方式。

### 方式二：手动安装

1. 下载本仓库，把 `custom_components/cn_minute_rain/` 整个目录复制到 Home Assistant 的
   `config/custom_components/cn_minute_rain/`。
2. 重启 Home Assistant。
3. 「设置 → 设备与服务 → 添加集成」，搜索 **中国分钟级降水预报**。

---

## 配置

集成通过 UI 配置流添加，**可一次性录入多个地点**：

1. 添加集成后，填写「地点名称」「经度」「纬度」。
2. 提交后会询问「是否继续添加地点？」：
   - 选「是」→ 继续添加下一个地点；
   - 选「否」→ 完成，所有地点归入同一个集成条目。
3. 后续可在集成条目的「配置」(选项流) 中选择「重新设置地点」来增删地点。

> 每个地点每 5 分钟请求一次接口（与原始 `rest` 传感器一致）。

---

## 实体说明

| 实体 | 状态 | 关键属性 |
|---|---|---|
| `<地点>临近降雨` | 接口返回的 `msg` 文案 | `values`(强度数组)、`time`、`longitude`、`latitude` |
| `<地点>降雨提示` | `无雨` / `正在下雨…` / `约 Y 分钟后开始下雨` | `minutes_to_rain`(距降雨分钟, 无雨为 null)、`rain_minutes`(预计持续分钟) |

`降雨提示` 的推算逻辑（移植自原始 Jinja 模板）：用 `120 / n`（向上取整）把离散强度点折算成分钟数，取首个/末个大于 0 的索引算出「多久后下雨」与「持续多久」。

---

## 数据来源与致谢

- 降水数据来自[中国天气网分钟级降水](https://www.weather.com.cn/)（mpf.weather.com.cn）。
- 本集成仅做数据抓取与展示，不保证数据准确性，请以官方预警为准。

## 常见问题

- **状态一直「无雨」？** 先检查 `<地点>临近降雨` 的 `values` 属性是否为空；空数组会被判定为「无雨」。
- **想换接口的返回字段？** 若接口实际返回结构与 `msg / values / time` 不同，调整 `coordinator.py` 的 `parse_values` 与 `_async_update_data` 即可。
- **HACS 添加失败？** 确认仓库地址、类别选「集成」；若平台不兼容可走手动安装。
