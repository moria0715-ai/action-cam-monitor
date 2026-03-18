# Action Camera Monitor — 自动化看板

每日自动更新的行动相机品牌舆情监控看板（DJI / Insta360 / GoPro × 欧洲五国）。

**公开链接：** https://moria0715-ai.github.io/action-cam-monitor/

---

## 目录结构

```
├── template.html          # 看板 HTML 模板（不含真实数据）
├── index.html             # 最终输出（由 CI 自动生成，勿手动编辑）
├── fetch_data.py          # 从 Brandwatch / Meltwater 拉取数据
├── generate_dashboard.py  # 将数据注入 HTML 模板
├── data/
│   └── latest.json        # 最新一天的 API 数据
└── .github/
    └── workflows/
        └── daily-update.yml  # GitHub Actions 自动化配置
```

---

## 如何配置 API Key

### 1. 打开仓库 Settings

`https://github.com/moria0715-ai/action-cam-monitor/settings/secrets/actions`

### 2. 点击「New repository secret」，添加以下 Secrets

#### 使用 Brandwatch：

| Secret 名称              | 值                          |
|-------------------------|-----------------------------|
| `BRANDWATCH_API_KEY`    | 你的 Brandwatch API Bearer Token |
| `BRANDWATCH_PROJECT_ID` | 你的 Brandwatch 项目 ID      |

#### 使用 Meltwater：

| Secret 名称         | 值                      |
|--------------------|-------------------------|
| `MELTWATER_API_KEY` | 你的 Meltwater API Key  |

### 3. 设置数据源变量

`https://github.com/moria0715-ai/action-cam-monitor/settings/variables/actions`

添加 Variable：

| Variable 名称 | 值                          |
|--------------|------------------------------|
| `DATA_SOURCE` | `brandwatch` 或 `meltwater` |

---

## 手动触发更新

1. 进入 https://github.com/moria0715-ai/action-cam-monitor/actions
2. 左侧选择「Daily Dashboard Update」
3. 右侧点击「Run workflow」→「Run workflow」

---

## 自动更新时间

每天 **北京时间 09:00**（UTC 01:00）自动拉取前一天数据并更新看板。

---

## 获取 API Key

### Brandwatch
- 官网：https://www.brandwatch.com
- API 文档：https://developers.brandwatch.com/docs
- 登录后：Settings → API Access → 生成 Bearer Token

### Meltwater
- 官网：https://www.meltwater.com
- API 文档：https://developer.meltwater.com
- 登录后：Settings → API → Generate API Key
