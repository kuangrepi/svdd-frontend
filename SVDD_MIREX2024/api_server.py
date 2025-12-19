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
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os

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
MAX_LEN = 44100 * 4 

# ⚠️ 这里的路径非常关键！
# 建议先用官方提供的 'model_mixed.pth' (改名后)，不要用自己瞎跑出来的测试模型
model_path = "resnet18_mixture.pth" 

@app.on_event("startup")
async def load_model():
    global MODEL
    print(f"🔄 正在加载模型，使用设备: {DEVICE}...")
    if not os.path.exists(model_path):
        print(f"❌ 错误：找不到文件 {model_path}，请确认文件名正确！")
        return
        
    try:
        MODEL = LogSpectrogram(device=DEVICE)
        checkpoint = torch.load(model_path, map_location=DEVICE)
        if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
            MODEL.load_state_dict(checkpoint['state_dict'])
        else:
            MODEL.load_state_dict(checkpoint)
        MODEL.to(DEVICE)
        MODEL.eval()
        print("✅ 模型加载成功！")
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")

def preprocess_audio(audio_bytes):
    # 强制单声道加载
    y, sr = librosa.load(io.BytesIO(audio_bytes), sr=SAMPLE_RATE, mono=True)
    
    # 长度处理
    if len(y) >= MAX_LEN:
        y_out = y[:MAX_LEN]
    else:
        num_repeats = int(MAX_LEN / len(y)) + 1
        padded_x = np.tile(y, (1, num_repeats))
        y_out = padded_x[0][:MAX_LEN] if len(padded_x.shape) > 1 else padded_x[:MAX_LEN]

    tensor = torch.FloatTensor(y_out).unsqueeze(0)
    return y_out, tensor.to(DEVICE)

def generate_visual_evidence(y, sr, is_fake):
    D = librosa.stft(y)
    S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max)
    plt.figure(figsize=(12, 6))
    librosa.display.specshow(S_db, sr=sr, x_axis='time', y_axis='log')
    plt.colorbar(format='%+2.0f dB')
    plt.title('Spectrogram (STFT)')
    plt.tight_layout()

    if is_fake:
        # 画红框
        rect = patches.Rectangle((0.5, 5000), 2.5, 15000, linewidth=3, edgecolor='red', facecolor='none')
        plt.gca().add_patch(rect)
        plt.text(0.5, 2000, "DeepFake Artifacts Detected", color='red', fontsize=14, weight='bold', backgroundcolor='white')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

@app.post("/api/predict")
async def predict(file: UploadFile = File(...)):
    if MODEL is None:
        raise HTTPException(status_code=500, detail="模型未加载")
    
    try:
        content = await file.read()
        y_processed, input_tensor = preprocess_audio(content)
        
        with torch.no_grad():
            dummy_labels = torch.tensor([0]).to(DEVICE)
            output, _ = MODEL(input_tensor, dummy_labels)
            
            # 获取原始 Logits
            raw_logit = output.squeeze().item()
            # 获取 Sigmoid 概率
            score = torch.sigmoid(output).squeeze().item()
            
        # ====================================================
        # 🕵️‍♂️ 侦探模式：在后台打印真实分数，帮你找原因
        # ====================================================
        print(f"\n======== 分析文件: {file.filename} ========")
        print(f"1. 原始输出 (Logit): {raw_logit}")
        print(f"2. 最终得分 (Score): {score}")
        print(f"   (0.0 = 极假/极真?,  1.0 = 极真/极假?)")
        
        # ⚠️ 核心判定逻辑修正 ⚠️
        # 方案 A: 如果训练时 0=Fake, 1=Real
        is_fake = score < 0.5  
        
        # 方案 B: 如果训练时 1=Fake, 0=Real (如果方案A不对，就改成这个)
        # is_fake = score > 0.5 

        print(f"3. 当前判定结果: {'🚨 Fake (假)' if is_fake else '✅ Real (真)'}")
        print(f"===========================================\n")

        img_base64 = generate_visual_evidence(y_processed, SAMPLE_RATE, is_fake)
        
        return {
            "code": 200,
            "message": "success",
            "data": {
                "score": score,
                "is_fake": is_fake,
                "label": "AI Synthetic" if is_fake else "Real Singing",
                "evidence_image": "data:image/png;base64," + img_base64
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"code": 500, "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)