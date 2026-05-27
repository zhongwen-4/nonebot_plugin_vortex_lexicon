<!-- markdownlint-disable MD013 MD033 MD036 MD041 MD060 -->

<div align="center">

<a href="https://nonebot.dev/store/plugins/">
  <img src="https://raw.githubusercontent.com/A-kirami/nonebot-plugin-template/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo">
</a>

<p>
  <img src="https://raw.githubusercontent.com/lgc-NB2Dev/readme/main/template/plugin.svg" alt="NoneBotPluginText">
</p>

# nonebot-plugin-vortex-lexicon

_✨ 支持分群/全局作用域、逻辑模板与 API 动作的 NoneBot2 词库插件 ✨_

<img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="python">
<img src="https://img.shields.io/badge/NoneBot2-2.0+-green.svg" alt="nonebot2">
<img src="https://img.shields.io/badge/adapter-milky-orange.svg" alt="adapter">

</div>

## 介绍

`nonebot-plugin-vortex-lexicon` 是一个基于 `NoneBot2 + ORM` 的词库插件，核心能力如下：

- 🧭 分群词库与全局词库双作用域（群聊优先匹配分群词库）
- 🛠️ 词条增删改查（Alconna 指令）
- 🧩 模板变量、随机模板、时间模板、等待输入模板
- 🧠 逻辑表达式匹配（`if/and/or/not/xor/in/not in/==/!=/<=/>=`）
- 🔌 API 动作模板（先调用 API 再发送文本）
- 📦 查询结果按阈值自动切换单条消息/合并转发

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-vortex-lexicon

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-vortex-lexicon
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-vortex-lexicon
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-vortex-lexicon
</details>
<details>
<summary>conda</summary>

    conda install nonebot-plugin-vortex-lexicon
</details>

如果你在本地开发本项目, 建议使用可编辑安装

    pip install -e .

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_vortex_lexicon"]

</details>

## ⚙️ 配置

在 NoneBot2 项目的 `.env` 文件中添加下表中的配置：

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| vortex_lexicon_query_threshold | 否 | 5 | 查询结果条数阈值；小于等于阈值逐条发送，大于阈值尝试合并转发 |

## 🎉 使用

### 指令表

| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:-----:|:----:|:----:|:----:|:----:|
| `词库 分群 添加 <question> <answer> [permission] [allow_users]` | 群员 | 否 | 群聊 | 新增或覆盖分群词条 |
| `词库 分群 修改 <question>` | 群员 | 否 | 群聊 | 交互式修改分群词条答案（60 秒超时） |
| `词库 分群 删除 <question>` | 群员 | 否 | 群聊 | 删除分群词条 |
| `词库 分群 查询 [keyword]` | 群员 | 否 | 群聊 | 查询分群词条 |
| `词库 全局 添加 <question> <answer> [permission] [allow_users]` | 群员 | 否 | 全部 | 新增或覆盖全局词条 |
| `词库 全局 修改 <question>` | 群员 | 否 | 全部 | 交互式修改全局词条答案（60 秒超时） |
| `词库 全局 删除 <question>` | 群员 | 否 | 全部 | 删除全局词条 |
| `词库 全局 查询 [keyword]` | 群员 | 否 | 全部 | 查询全局词条 |

### 模板语法速览

- 变量模板：`你好[name]` → `answer` 可用 `[name]`
- 随机数模板：`[随机操作.取随机数.1.100]`
- 随机选择模板：`[随机操作.从列表.msg]`（`msg` 以 `||` 分割候选）
- 时间模板：`[时间.取时间戳_秒]`、`[时间.格式化.%Y-%m-%d]`、`[时间.休眠.1]`
- await 模板：`[await.10.text]`（等待 10 秒输入并写入 `text`）
- 事件字段简写：`event.peer_id` 会自动回退到 `event.data.peer_id`
- 逻辑判断规则：比较判断必须在逻辑表达式中使用，并且需显式使用 `[if]`
  - 推荐写法：`[if][event.event_type][==]message_recall[and][event.type][==]notice`
- API 动作模板：`answer` 以 `[api....]` 开头时先调用 API，再发送剩余文本
  - 现已支持 API 参数中的嵌套方括号，如 `[group_id]`

### 权限字段说明

- `permission` 支持：`all / admin / owner / superuser / allowlist_admin`（含中文别名）
- `allow_users` 支持：`123,456` 或 `123|456`
- `allowlist_admin` 表示：白名单成员 + 管理员 + 群主 + 超管可触发

### 效果图

如果你有实际运行截图，可以放在这里，方便使用者快速理解插件效果。📸
