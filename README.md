

# 🎵 Singing Voice DeepFake Detection System (SVDD-Web)

> 一个基于深度学习的歌声 DeepFake 检测系统，支持全曲切片扫描、可视化频谱分析及高危片段定位。

![Vue 3](https://img.shields.io/badge/Frontend-Vue%203%20%2B%20Element%20Plus-42b883)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2B%20PyTorch-009688)
![License](https://img.shields.io/badge/License-MIT-blue)

## 📖 项目简介

本项目是一个全栈 Web 应用，旨在检测歌声音频是否由 AI 合成（DeepFake）。系统采用了 **前后端分离** 架构：

*   **前端**：构建于 Vue 3 和 Element Plus，提供现代化的文件上传、音频预览及可视化的检测报告。
*   **后端**：基于 PyTorch 和 FastAPI，集成了 SVDD 2024 挑战赛冠军方案的 ResNet18 模型。

### ✨ 核心功能
*   **全曲扫描**：采用滑动窗口机制（Sliding Window），将长音频切分为多个 4秒 片段进行逐一检测，避免遗漏。
*   **精准定位**：自动筛选出得分最低（最假）的 Top 3 片段，帮助用户快速定位伪造痕迹。
*   **可视化证据**：生成梅尔频谱图（Mel-Spectrogram），直观展示音频的频域特征。
*   **格式支持**：完美支持 `.wav`, `.mp3`, `.flac` 等常见音频格式。

---

## 📂 目录结构

```text
DeepFake_Project/
├── frontend/            # 前端项目 (Vue 3)
│   ├── src/             # 页面源代码
│   └── package.json     # 前端依赖
│
└── SVDD_MIREX2024/      # 后端项目 (Python)
    ├── api_server.py    # 核心推理接口服务
    ├── models.py        # ResNet18 模型定义
    ├── resnet18_mixture.pth   # 预训练权重文件
    └── requirements.txt # 后端依赖
```

---

## 🛠️ 环境准备

在运行项目前，请确保你的电脑已安装以下环境：

1.  **Node.js** (v18+): 用于运行前端。
2.  **Python** (v3.8+): 用于运行后端。
3.  **FFmpeg**: 用于处理 MP3 音频流 (必须安装并加入环境变量)。

---

## 🚀 快速启动指南

### 第一步：配置后端 (Backend)

1.  进入后端目录：
    ```bash
    cd SVDD_MIREX2024
    ```

2.  安装 Python 依赖：
    ```bash
    pip install -r requirements.txt
    ```

4.  启动后端服务：
    ```bash
    python api_server.py
    ```
    *当看到 `✅ 模型加载成功！` 且服务运行在 `http://0.0.0.0:8000` 时，即代表后端就绪。*

### 第二步：启动前端 (Frontend)

1.  打开新的终端窗口，进入前端目录：
    ```bash
    cd frontend
    ```

2.  安装 NPM 依赖：
    ```bash
    npm install
    ```

3.  启动开发服务器：
    ```bash
    npm run dev
    ```

4.  浏览器访问：
    打开控制台显示的链接（通常是 `http://localhost:5173`）即可使用系统。

---

## 🧠 技术原理

1.  **预处理**：音频被重采样为 44.1kHz，并转换为对数梅尔频谱图 (Log-Mel Spectrogram)。
2.  **模型推理**：使用修改版 **ResNet18** 骨干网络，该模型在 ImageNet 上预训练并在 WildSVDD 数据集上进行了微调。
3.  **评分逻辑**：
    *   模型输出 Logits，经过 Sigmoid 转换为 0~1 的分数。
    *   **Label 0 = Fake (假)**, **Label 1 = Real (真)**。
    *   系统计算全曲所有切片的平均分，若 `Average Score < 0.5`，则判定为 **AI 合成音乐**。

---

## 🙏 致谢 (Acknowledgements)

本项目是基于 **MIREX 2024 SVDD Challenge 冠军方案** 的二次开发与 Web化实现。

我们诚挚感谢原作者团队的开源贡献：

*   **Original Repository**: [SVDD_MIREX2024](https://github.com/mahyargm/SVDD_MIREX2024)
*   **Authors**: Mahyar Gohari, Davide Salvi, Paolo Bestagini, Nicola Adami (University of Brescia & Polytechnic University of Milan).
*   **Paper**: *Singing Voice DeepFake Detection* (ISMIR 2024).

如果不使用他们的预训练模型和核心算法，本项目无法完成。请大家支持原作者的工作！

