# 🎵 Singing Voice DeepFake Detection + Singer Identity System

> 基于深度学习的歌声 DeepFake 检测与歌手身份识别系统，支持全曲切片扫描、可视化频谱分析及歌手身份对比。

![Vue 3](https://img.shields.io/badge/Frontend-Vue%203%20%2B%20Element%20Plus-42b883)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2B%20PyTorch-009688)
![License](https://img.shields.io/badge/License-MIT-blue)

## 📖 项目简介

本项目是一个全栈 Web 应用，集成了两项功能：

- **DeepFake 检测**：判断歌声是否由 AI 合成，基于 MIREX 2024 冠军方案 ResNet18 模型。
- **歌手身份识别**：提取歌手声纹嵌入并与参考库对比，识别演唱者身份，基于 Sony CSL Paris 的 [ssl-singer-identity](https://github.com/SonyCSLParis/ssl-singer-identity) 模型。

### ✨ 核心功能

- **全曲扫描**：滑动窗口（4秒/2秒步长）逐片段分析，自动定位 Top 3 高危伪造片段
- **歌手识别**：上传参考音频注册歌手，检测时自动与参考库对比并给出相似度排名
- **可视化证据**：梅尔频谱图直观展示音频频域特征
- **格式支持**：`.wav` / `.mp3` / `.flac`

---

## 📂 目录结构

```text
svdd-frontend/
├── frontend/                    # 前端 (Vue 3 + Element Plus)
│   ├── src/App.vue              # 主界面
│   └── package.json
│
└── backend/                     # 后端 (Python + FastAPI)
    ├── api_server.py            # 核心推理接口
    ├── singer_database.py       # 歌手参考库管理
    ├── singer_references.json   # 歌手声纹数据（自动生成）
    ├── requirements.txt
    ├── SVDD_MIREX2024/          # DeepFake 检测模型
    │   ├── models.py            # ResNet18 模型定义
    │   └── resnet18_mixture.pth # 预训练权重
    └── ssl-singer-identity/     # 歌手身份识别模型 (SonyCSLParis)
        └── singer_identity/     # 模型代码包
```

---

## 🛠️ 环境准备

1. **Node.js** (v18+)
2. **Python** (v3.8+)
3. **FFmpeg**（必须安装并加入 PATH，用于处理 MP3）

---

## 🚀 快速启动

### 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

首次启动会自动从 HuggingFace 下载 ssl-singer-identity 预训练权重（约 20MB）。  
看到 `✅ 深度伪造检测模型加载成功` 和 `✅ 歌手身份模型加载成功` 即为就绪。

### 前端

```bash
cd frontend
npm install
npm run dev
```

打开控制台显示的链接（通常为 `http://localhost:5173`）即可使用。

---

## 🎤 歌手身份识别使用方法

1. 上传一首歌开始检测
2. 结果页点击 **「管理参考歌手」**
3. 切换到「添加歌手」标签，输入歌手名并上传 5–30 秒清晰演唱片段，点击「添加参考」
4. 再次检测同一歌手的歌曲，系统将显示与参考库的相似度排名

---

## 🧠 技术原理

| 模块 | 模型 | 说明 |
|------|------|------|
| DeepFake 检测 | ResNet18 (修改版) | 对数梅尔频谱图 → 二分类（真/假），在 WildSVDD 数据集微调 |
| 歌手识别 | EfficientNet-B0 (ssl-singer-identity) | 梅尔频谱图 → 1000维声纹嵌入，余弦相似度匹配 |

---

## 🙏 致谢

- **SVDD 模型**：[SVDD_MIREX2024](https://github.com/mahyargm/SVDD_MIREX2024) — Mahyar Gohari et al., University of Brescia & Polytechnic University of Milan
- **Singer Identity 模型**：[ssl-singer-identity](https://github.com/SonyCSLParis/ssl-singer-identity) — Sony CSL Paris
