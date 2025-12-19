# 文件名: backend/api_server.py

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
# 移除了 patches 引用，不再需要画框

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
CHUNK_DURATION = 4
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_DURATION
STRIDE = 2

# ⚠️ 确保文件名正确
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

# === 切片逻辑 ===
def chunk_audio(audio_bytes):
    # 读取完整音频
    y, sr = librosa.load(io.BytesIO(audio_bytes), sr=SAMPLE_RATE, mono=True)
    
    # 填充
    if len(y) < CHUNK_SAMPLES:
        pad_len = CHUNK_SAMPLES - len(y)
        y = np.pad(y, (0, pad_len), mode='wrap')
    
    # 切片
    chunks = []
    stride_samples = int(STRIDE * SAMPLE_RATE)
    
    for start in range(0, len(y) - CHUNK_SAMPLES + 1, stride_samples):
        chunk = y[start : start + CHUNK_SAMPLES]
        chunks.append(chunk)
    
    if len(chunks) == 0:
        chunks.append(y[:CHUNK_SAMPLES])
        
    batch_tensor = torch.FloatTensor(np.array(chunks)).to(DEVICE)
    return y, batch_tensor

# === 生成整体全景图 (纯净版，无红框) ===
def generate_overview_image(y):
    display_len = min(len(y), SAMPLE_RATE * 10) 
    y_display = y[:display_len]
    D = librosa.stft(y_display)
    S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max)
    
    plt.figure(figsize=(10, 4))
    librosa.display.specshow(S_db, sr=SAMPLE_RATE, x_axis='time', y_axis='log')
    plt.colorbar(format='%+2.0f dB')
    plt.title('Audio Overview (Mel-Spectrogram)')
    plt.tight_layout()

    # ❌ 删除了这里的红框绘制代码 ❌

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

# === 生成单个片段的图 (纯净版) ===
def generate_segment_image(chunk_y):
    D = librosa.stft(chunk_y)
    S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max)
    
    plt.figure(figsize=(6, 3))
    librosa.display.specshow(S_db, sr=SAMPLE_RATE, x_axis='time', y_axis='log')
    plt.title('Segment Spectrogram')
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

# === 接口入口 ===
@app.post("/api/predict")
async def predict(file: UploadFile = File(...)):
    if MODEL is None:
        raise HTTPException(status_code=500, detail="模型未加载")
    
    try:
        content = await file.read()
        y_full, input_batch = chunk_audio(content)
        
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
        
        avg_score = float(np.mean(all_scores))
        is_fake = bool(avg_score < 0.5)
        
        segment_data = []
        for i, score in enumerate(all_scores):
            start_time = i * STRIDE
            segment_data.append({
                "index": i,
                "start": start_time,
                "end": start_time + CHUNK_DURATION,
                "score": float(score)
            })
            
        suspicious_segments_result = []
        
        if is_fake:
            sorted_segments = sorted(segment_data, key=lambda x: x["score"])
            top3 = sorted_segments[:3]
            
            for seg in top3:
                sample_start = seg["start"] * SAMPLE_RATE
                sample_end = sample_start + CHUNK_SAMPLES
                chunk_y = y_full[sample_start : sample_end]
                img_str = generate_segment_image(chunk_y)
                
                suspicious_segments_result.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "score": seg["score"],
                    "image": "data:image/png;base64," + img_str
                })

        # 生成概览图 (不再传 is_fake 参数，因为不需要画框了)
        overview_img = generate_overview_image(y_full)
        
        return {
            "code": 200,
            "message": "success",
            "data": {
                "filename": file.filename,
                "score": avg_score,
                "is_fake": is_fake,
                "label": "AI Synthetic (DeepFake)" if is_fake else "Real Singing Voice",
                "evidence_image": "data:image/png;base64," + overview_img,
                "suspicious_segments": suspicious_segments_result
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"code": 500, "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)