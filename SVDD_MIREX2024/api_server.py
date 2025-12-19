import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import torch
import librosa
import librosa.display 
import numpy as np
import io
import base64
import matplotlib
import os
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# === 导入模型 ===
from models import LogSpectrogram 

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 全局配置 ===
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL = None
SAMPLE_RATE = 44100
CHUNK_DURATION = 4         # 每次分析 4 秒
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_DURATION
STRIDE = 2                 # 步长 2 秒 (重叠 50% 扫描，防止漏掉边界特征)

# 确保这里的路径是对的
MODEL_PATH = "resnet18_mixture.pth" 

@app.on_event("startup")
async def load_model():
    global MODEL
    print(f"🔄 正在加载模型，使用设备: {DEVICE}...")
    if not os.path.exists(MODEL_PATH):
        print(f"❌ 错误：找不到文件 {MODEL_PATH}")
        return
    try:
        MODEL = LogSpectrogram(device=DEVICE)
        checkpoint = torch.load(MODEL_PATH, map_location=DEVICE)
        if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
            MODEL.load_state_dict(checkpoint['state_dict'])
        else:
            MODEL.load_state_dict(checkpoint)
        MODEL.to(DEVICE)
        MODEL.eval()
        print("✅ 模型加载成功！")
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")

# === 核心逻辑修改：把整首歌切成很多个 4s 片段 ===
def chunk_audio(audio_bytes):
    # 1. 读取完整音频
    y, sr = librosa.load(io.BytesIO(audio_bytes), sr=SAMPLE_RATE, mono=True)
    
    # 如果音频短于 4秒，强制填充到 4秒
    if len(y) < CHUNK_SAMPLES:
        pad_len = CHUNK_SAMPLES - len(y)
        y = np.pad(y, (0, pad_len), mode='wrap')
    
    # 2. 切片 (Sliding Window)
    # 使用步长 (STRIDE * sr) 进行滑动切割
    chunks = []
    stride_samples = int(STRIDE * SAMPLE_RATE)
    
    # 从头切到尾
    for start in range(0, len(y) - CHUNK_SAMPLES + 1, stride_samples):
        chunk = y[start : start + CHUNK_SAMPLES]
        chunks.append(chunk)
    
    # 如果最后剩下一截不够步长，但也凑够4s的，也加上
    if len(chunks) == 0: # 只有一段的情况
        chunks.append(y[:CHUNK_SAMPLES])
        
    print(f"🔪 音频切片完成：共生成 {len(chunks)} 个片段")
    
    # 3. 转成 Tensor Batch [N, 176400]
    # 也就是一次性把 N 个片段都堆在一起
    batch_tensor = torch.FloatTensor(np.array(chunks)).to(DEVICE)
    
    return y, batch_tensor # 返回原始音频(画图用) 和 切片后的Tensor(推理用)

def generate_visual_evidence(y, sr, is_fake):
    # 画图只画前 10 秒或者整首，不然图太长了
    # 这里我们只取前 4 秒画图，或者取一个典型的片段
    display_len = min(len(y), SAMPLE_RATE * 10) 
    y_display = y[:display_len]
    
    D = librosa.stft(y_display)
    S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max)
    
    plt.figure(figsize=(12, 6))
    librosa.display.specshow(S_db, sr=sr, x_axis='time', y_axis='log')
    plt.colorbar(format='%+2.0f dB')
    plt.title('Spectrogram Analysis (First 10s)')
    plt.tight_layout()

    if is_fake:
        # 画红框 (示意图)
        rect = patches.Rectangle((0.5, 5000), 2.0, 15000, linewidth=3, edgecolor='red', facecolor='none')
        plt.gca().add_patch(rect)
        plt.text(0.5, 2000, "DeepFake Artifacts Detected", color='red', fontsize=14, weight='bold', backgroundcolor='white')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

# === 4. 接口入口 (修复版) ===
@app.post("/api/predict")
async def predict(file: UploadFile = File(...)):
    if MODEL is None:
        raise HTTPException(status_code=500, detail="模型未加载")
    
    try:
        content = await file.read()
        
        # 1. 获取 切片Batch
        y_full, input_batch = chunk_audio(content)
        
        # 2. 批量推理
        all_scores = []
        with torch.no_grad():
            batch_size = 8 
            for i in range(0, len(input_batch), batch_size):
                batch_x = input_batch[i : i+batch_size]
                dummy_labels = torch.zeros(len(batch_x)).to(DEVICE)
                output, _ = MODEL(batch_x, dummy_labels)
                
                scores = torch.sigmoid(output).squeeze().cpu().numpy()
                if scores.ndim == 0:
                    all_scores.append(scores.item())
                else:
                    all_scores.extend(scores.tolist())
        
        # 3. 统计全曲得分
        avg_score = np.mean(all_scores)
        min_score = np.min(all_scores)
        
        print(f"📊 分析详情: 共有 {len(all_scores)} 个片段")
        print(f"   平均分: {avg_score:.4f}")
        print(f"   最低分: {min_score:.4f}")
        
        # === ⚠️ 关键修改点：类型转换 ⚠️ ===
        
        # 将 numpy.float 转为 python float
        final_score = float(avg_score) 
        
        # 将 numpy.bool_ 转为 python bool
        is_fake = bool(final_score < 0.5)
        
        # ===================================
        
        # 生成图片
        img_base64 = generate_visual_evidence(y_full, SAMPLE_RATE, is_fake)
        
        return {
            "code": 200,
            "message": "success",
            "data": {
                "score": final_score, # 现在是原生 float
                "is_fake": is_fake,   # 现在是原生 bool
                "label": "AI Synthetic (DeepFake)" if is_fake else "Real Singing Voice",
                "evidence_image": "data:image/png;base64," + img_base64
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"code": 500, "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)