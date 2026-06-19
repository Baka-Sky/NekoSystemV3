# 🐱 NekoSystem v3

> 一个为《我的世界》树莓派版（MCPI）打造的智能助手插件，集成系统监控、AI 对话、实时热搜、自定义公告等功能。

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![MCPI](https://img.shields.io/badge/MCPI-1.0+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![讯飞星火](https://img.shields.io/badge/讯飞星火-Lite-red)

---

# 📌 简介

NekoSystem 是一个基于 Python + MCPI（Minecraft Pi Edition API）的 Minecraft 外部脚本插件，用来扩展游戏功能：

- 📊 系统监控（CPU / 内存 / 网络）
- 🧠 AI 对话（讯飞星火 Spark Lite）
- 🔥 热搜社会报（自动筛选）
- 📢 大事报公告系统
- ⏰ 定时系统播报
- 💬 游戏内聊天控制

---

# 🎯 功能一览

| 模块 | 命令 | 说明 |
|------|------|------|
| 系统监控 | `neko per` | CPU / 内存 / 网络状态 |
| 定时报告 | `nekopertime X 密码` | 每 X 分钟自动播报 |
| 社会报 | `neko soc` | 热搜筛选 |
| 大事报 | `neko big` | 查看公告 |
| 修改大事报 | `nekobig 内容 密码` | 修改公告 |
| AI 问答 | `nekoai 问题` | AI 回复（带喵） |
| 每日一言 | `nekodaysay` | 随机语录 |
| 帮助 | `neko` | 帮助菜单 |
| 重启 | `neko reboot` | 重启服务 |
| 关闭 | `neko off` | 关闭服务 |

---

# 🛠 安装依赖

pip install mcpi psutil ping3 openai

---

## 国内镜像（推荐）

pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mcpi psutil ping3 openai

---

# 🌐 API 准备

- 讯飞星火 API（需要 APIPassword）
- UapiPro 热搜 API（无需密钥）

---

# 📦 下载脚本

将 `Neko.py` 放入任意目录，确保 Minecraft 已启动。

---

# ⚙️ 配置

在 `Neko.py` 中修改：

XFYUN_API_KEY = "你的APIPassword"
XFYUN_BASE_URL = "https://spark-api-open.xf-yun.com/v1/"
XFYUN_MODEL = "lite"

self.admin_password = "your_password"

address = "127.0.0.1"
port = 4711

---

# 🚀 使用方法

1. 启动 Minecraft
2. 运行脚本：

python Neko.py

3. 在游戏聊天框输入：

neko per
nekoai 你好
neko soc

---

# 📁 文件结构

NekoSystem/
├── Neko.py
└── py/
    └── bigboard.txt

---

# ❓ 常见问题

## Q1：Connection refused？
确认 Minecraft 已启动，端口 4711 未被占用。

## Q2：AI 报错 400？
检查 API Key 是否为正确格式：xxxx:yyyy

## Q3：社会报无内容？
检查网络是否正常访问热搜 API

## Q4：大事报在哪？
py/bigboard.txt

## Q5：定时不生效？
检查密码或执行 neko reboot

---

# 🤝 开发与贡献

欢迎：

- 新增命令 → process_command
- 扩展监控 → GPU / FPS
- 扩展平台 → B站 / 知乎

---

# 📄 许可证

MIT License

---

# 🐱 结语

由 Wells & jiang 开发  
基于 讯飞星火 Spark Lite  
来自异世界的猫猫智能体 NekoAI
