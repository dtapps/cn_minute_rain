# 中国分钟级降水预报 (cn_minute_rain)

Home Assistant 自定义集成，基于[中国天气网分钟级降水 API](https://mpf.weather.com.cn) 提供未来 2 小时临近降雨预报。支持**多地点**，每个地点自动生成两个实体：

- **`<地点>临近降雨`**：状态为预报文案（如“未来2小时不会降雨”），属性含 `values`（强度数组）、`time`、`longitude`、`latitude`。
- **`<地点>降雨提示`**：由强度数组推算的人话状态 —— `无雨` / `🌧️ 正在下雨，预计持续约 X 分钟` / `⏳ 约 Y 分钟后开始下雨`，图标随状态切换。

每个地点会生成两个实体，对象 ID 固定为：

- `sensor.cn_minute_rain_<地点拼音>_nearby` —— **临近降雨**：状态为预报文案，属性含 `values`(强度数组)、`time`、`longitude`、`latitude`。
- `sensor.cn_minute_rain_<地点拼音>_tip` —— **降雨提示**：状态为 `无雨` / `正在下雨…` / `约 Y 分钟后开始下雨`，属性含 `minutes_to_rain`、`rain_minutes`。

> 不确定拼音时，可在「设置 → 设备与服务 → 中国分钟级降水预报 → 设备 → 实体」里直接复制 `entity_id`。

示例卡片（降雨提示为「无雨」时整块自动隐藏，临近降雨用图表展示未来 2 小时强度）：

```yaml
cards:
  - type: conditional
    conditions:
      - condition: state
        entity: sensor.cn_minute_rain_<地点拼音>_tip
        state_not: 无雨
    card:
      type: entity
      entity: sensor.cn_minute_rain_<地点拼音>_tip
      name: 临近降雨提示
  - type: custom:apexcharts-card
    header:
      show: true
      title: 🌧️ 临近降雨预报
      show_states: true
      colorize_states: true
    graph_span: 2h
    span:
      start: minute
    apex_config:
      chart:
        height: 180px
      yaxis:
        - title:
            text: 降雨量 (mm)
          decimalsInFloat: 2
    series:
      - entity: sensor.cn_minute_rain_<地点拼音>_nearby
        name: 降雨量
        data_generator: |
          const values = entity.attributes.values || [];
          const now = new Date();
          return values.map((value, index) => {
            const time = new Date(now.getTime() + index * 6 * 60 * 1000);
            return [time, value];
          });
        type: area
        color: "#03A9F4"
        stroke_width: 2
        show:
          in_header: false
```

---

## 安装

### 方式一：HACS（推荐）

1. 打开 HACS → 右上角「⋮」→「自定义仓库」(Custom repositories)。
2. 仓库地址填入：

   ```
   https://github.com/dtapps/cn_minute_rain
   ```

3. 类别选择 **集成 (Integration)**，点击「添加」。
4. 在 HACS 的「集成」列表里搜索 **中国分钟级降水预报**，点击「下载」并重启 Home Assistant。
5. 「设置 → 设备与服务 → 添加集成」，搜索 **中国分钟级降水预报**，按提示填写地点即可。

### 方式二：手动安装

1. 下载本仓库，把 `custom_components/cn_minute_rain/` 整个目录复制到 Home Assistant 的
   `config/custom_components/cn_minute_rain/`。
2. 重启 Home Assistant。
3. 「设置 → 设备与服务 → 添加集成」，搜索 **中国分钟级降水预报**。

---

## 配置

每个集成条目对应**一个地点**。想监控多个地点，就**重复添加本集成**多次（每次一个地点，互不干扰）。

1. 「设置 → 设备与服务 → 添加集成」，搜索 **中国分钟级降水预报**。
2. 填写「地点名称」「经度」「纬度」（经纬度默认取当前 Home Assistant 所在位置）。
3. 可选填「更新间隔（秒）」，默认 300（5 分钟）。
4. 提交即生成一个集成条目、两个实体。
5. 之后可在该集成条目的「配置」里**修改本条目对应的地点与更新间隔**（改名/挪位置无需删条目）。

> 更新间隔默认 300 秒（5 分钟），单位：秒，可在添加时填写或事后在选项流里调整。

---

## 实体说明

| 实体             | 状态                                         | 关键属性                                                                 |
| ---------------- | -------------------------------------------- | ------------------------------------------------------------------------ |
| `<地点>临近降雨` | 接口返回的 `msg` 文案                        | `values`(强度数组)、`time`、`longitude`、`latitude`                      |
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
