<!-- markdownlint-disable MD033 MD041 -->

<div align="center">

<a href="https://nonebot.dev/store/plugins/">
  <img src="https://raw.githubusercontent.com/A-kirami/nonebot-plugin-template/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo">
</a>

<p>
  <img src="https://raw.githubusercontent.com/lgc-NB2Dev/readme/main/template/plugin.svg" alt="NoneBotPluginText">
</p>

# nonebot-plugin-vortex-lexicon

_✨ 基于 NoneBot2 + ORM 的分群/全局词库插件，支持模板变量、逻辑表达式、随机模板与 API 动作 ✨_

<img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="python">
<img src="https://img.shields.io/badge/NoneBot2-2.0+-green.svg" alt="nonebot2">
<img src="https://img.shields.io/badge/adapter-milky-orange.svg" alt="adapter">

</div>

## 📖 介绍

`nonebot-plugin-vortex-lexicon` 是一个数据库驱动的词库插件，提供：

- 分群词库与全局词库双作用域
- 词条增删改查（Alconna 命令）
- 消息模板匹配与变量渲染
- 逻辑控制符（`or/and/not/xor/nor/nand/xnor/in/not in`）
- 随机模板（随机数、随机选择）
- API 动作模板（先 `call_api` 后发文本）
- 查询结果按阈值自动切换单条消息/合并转发

## 💿 安装

### 使用 pip（本地开发推荐）

在项目根目录执行：

```bash
pip install -e .
```

并确保 `pyproject.toml` 的 `[tool.nonebot]` 中已加载：

```toml
plugins = ["nonebot_plugin_vortex_lexicon"]
```

### 使用 nb-cli（已发布到源时）

```bash
nb plugin install nonebot-plugin-vortex-lexicon
```

## ⚙️ 配置

可在 `.env` 中配置：

```env
# 查询结果阈值：
# <= 该值时单条消息发送；> 该值时尝试合并转发
vortex_lexicon_query_threshold=5
```

## 🎉 使用

### 指令

- `词库 分群 添加 <question> <answer>`
- `词库 分群 修改 <question>`
- `词库 分群 删除 <question>`
- `词库 分群 查询 [keyword]`
- `词库 全局 添加 <question> <answer>`
- `词库 全局 修改 <question>`
- `词库 全局 删除 <question>`
- `词库 全局 查询 [keyword]`

### 作用域规则

- `分群` 指令仅群聊可用。
- 消息匹配时：群聊会按“分群词库优先 + 全局词库兜底”匹配。
- 私聊会落到全局词库（`group_id = 0`）。

## 🧩 模板语法

### 1. 基础变量模板

- `question=你好[text]`
- `answer=输出[text]`
- 输入：`你好世界`
- 输出：`输出世界`

### 2. `question` 随机数匹配模板

- `[随机操作.取随机数]`：匹配任意整数
- `[随机操作.取随机数.1.100]`：匹配 `1~100`
- `[随机操作.取随机数.1.100.5]`：匹配按步长 5 的整数

示例：

- `question=抽[随机操作.取随机数.1.10]`
- 输入 `抽7` 可匹配，输入 `抽11` 不匹配

### 3. `answer` 随机数生成模板

- `[随机操作.取随机数]`：默认随机 `0~100`
- `[随机操作.取随机数.1.100]`
- `[随机操作.取随机数.1.100.5]`

示例：

- `answer=你抽到了[随机操作.取随机数.1.100]`

### 4. 赋值模板

`question` 侧赋值（表达式当前支持 `随机操作.取随机数.*`）：

- `question=抽[number=随机操作.取随机数.1.100]`
- `answer=你抽到了[number]`

`answer` 侧赋值：

- `answer=[msg=怎么做是对.怎么做都不对][随机操作.从列表.msg]`

### 5. 随机选择模板

- 语法：`[随机操作.从列表.<变量名>]`
- 变量内容按 `.` 切分为候选项后随机选一项

示例：

- `answer=[msg=A.B.C][随机操作.从列表.msg]`
- 可能输出：`A` / `B` / `C`

### 6. 逻辑控制符

支持：

- `[or] [and] [not] [xor] [nor] [nand] [xnor] [in] [not in]`

示例：

- `question=你好[or]我好`
- `answer=世界`
- 输入 `你好` 或 `我好` 时触发

## 🔌 API 动作模板

### 基础格式

在 `answer` 最前面写 API 块：

```text
[api.<api_name>.<arg1>=<v1>.<arg2>=<v2>]后续文本
```

执行流程：

- 先调用 `bot.call_api(...)`
- 再发送方括号后的剩余文本

### 返回字段提取

可用 `.get(...)` 提取 API 返回字段：

```text
[api.get_group_member_info.group_id=850717100.user_id=2401128923.get(user_id,nickname)]
```

### 参数类型转换

参数会自动识别：

- 整数：`123`
- 布尔：`true/false`、`yes/no`、`on/off`（含中英文常见写法）
- 空值：`null/none`

### 常量与自动填充

支持常量引用（示例）：

- `group_id`
- `user_id`
- `message_id`
- `reply_user_id`
- `reply_message_id`

自动填充（参数存在且为空时）当前支持：

- `group_id`
- `user_id`
- `message_id`
- `message_seq`

## 📦 数据模型

词条表字段：

- `id`
- `group_id`
- `question`
- `answer`

唯一约束：`(group_id, question)`

## 📝 说明

- 当前适配 Milky 生态，查询结果在超阈值时优先尝试合并转发。
- `template_engine.py` 已重构为兼容导出层，具体实现位于 `template_engine_parts/`。
