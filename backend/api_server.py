import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

# Both repos live inside backend/ at the same level
sys.path.insert(0, os.path.join(_HERE, "ssl-singer-identity"))
sys.path.insert(0, os.path.join(_HERE, "SVDD_MIREX2024"))

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import torch
import torch.nn.functional as F
import librosa
import librosa.display
import numpy as np
import io
import base64
import matplotlib
import tempfile
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from models import LogSpectrogram
from singer_identity import load_model
from singer_database import SingerDatabase

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

MODEL_PATH = os.path.join(_HERE, "SVDD_MIREX2024", "resnet18_mixture.pth")

SINGER_MODEL = None
SINGER_DB: SingerDatabase = None
SINGER_CHUNK = SAMPLE_RATE * 4
SINGER_STRIDE = SAMPLE_RATE * 2


@app.on_event("startup")
async def load_models():
    global MODEL, SINGER_MODEL, SINGER_DB

    # --- Load deepfake detection model ---
    print(f"[INFO] Loading deepfake detection model on {DEVICE}...")
    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] Model file not found: {MODEL_PATH}")
    else:
        try:
            MODEL = LogSpectrogram(device=DEVICE)
            checkpoint = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False)
            if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
                MODEL.load_state_dict(checkpoint['state_dict'])
            else:
                MODEL.load_state_dict(checkpoint)
            MODEL.to(DEVICE)
            MODEL.eval()
            print("[OK] Deepfake detection model loaded.")
        except Exception as e:
            print(f"[ERROR] Failed to load deepfake model: {e}")

    # --- Load singer identity model (ssl-singer-identity) ---
    print("[INFO] Loading singer identity model (ssl-singer-identity)...")
    try:
        SINGER_MODEL = load_model("contrastive")
        SINGER_MODEL.to(DEVICE)
        SINGER_MODEL.eval()
        SINGER_DB = SingerDatabase()
        print("[OK] Singer identity model loaded.")
    except Exception as e:
        print(f"[WARN] Singer identity model failed to load (deepfake detection still works): {e}")
        import traceback
        traceback.print_exc()


# === 切片逻辑 ===
def chunk_audio(audio_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_file_path = tmp_file.name

    try:
        y, sr = librosa.load(tmp_file_path, sr=SAMPLE_RATE, mono=True)
    except Exception as e:
        print(f"音频读取失败: {e}")
        raise e
    finally:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

    if len(y) < CHUNK_SAMPLES:
        pad_len = CHUNK_SAMPLES - len(y)
        y = np.pad(y, (0, pad_len), mode='wrap')

    chunks = []
    stride_samples = int(STRIDE * SAMPLE_RATE)

    for start in range(0, len(y) - CHUNK_SAMPLES + 1, stride_samples):
        chunk = y[start: start + CHUNK_SAMPLES]
        chunks.append(chunk)

    if len(chunks) == 0:
        chunks.append(y[:CHUNK_SAMPLES])

    batch_tensor = torch.FloatTensor(np.array(chunks)).to(DEVICE)
    return y, batch_tensor


def embed_waveform(y: np.ndarray) -> np.ndarray:
    """Extract singer identity embedding from a 44100 Hz mono waveform.
    Returns (1000,) unit-norm float32 array.
    """
    y = y[:SAMPLE_RATE * 30]
    if len(y) < SINGER_CHUNK:
        y = np.pad(y, (0, SINGER_CHUNK - len(y)), mode='wrap')

    windows = [y[s:s + SINGER_CHUNK]
               for s in range(0, len(y) - SINGER_CHUNK + 1, SINGER_STRIDE)]
    if not windows:
        windows = [y[:SINGER_CHUNK]]

    batch = torch.FloatTensor(np.stack(windows)).to(DEVICE)
    with torch.no_grad():
        embs = SINGER_MODEL(batch)      # (N, 1000)
    mean_emb = embs.mean(dim=0)
    mean_emb = F.normalize(mean_emb, dim=0)
    return mean_emb.cpu().numpy()


# === 生成整体全景图 ===
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

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# === 生成单个片段的图 ===
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


# === 主检测接口 ===
@app.post("/api/predict")
async def predict(file: UploadFile = File(...)):
    if MODEL is None:
        raise HTTPException(status_code=500, detail="模型未加载")

    try:
        content = await file.read()
        y_full, input_batch = chunk_audio(content)

        # --- Deepfake detection ---
        all_scores = []
        with torch.no_grad():
            batch_size = 8
            for i in range(0, len(input_batch), batch_size):
                batch_x = input_batch[i: i + batch_size]
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
                chunk_y = y_full[sample_start: sample_end]
                img_str = generate_segment_image(chunk_y)
                suspicious_segments_result.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "score": seg["score"],
                    "image": "data:image/png;base64," + img_str
                })

        overview_img = generate_overview_image(y_full)

        # --- Singer identity ---
        singer_identity_result = {
            "has_references": False,
            "top_matches": [],
            "top_match": None,
            "top_similarity": None,
        }
        if SINGER_MODEL is not None and SINGER_DB is not None and SINGER_DB.has_references():
            try:
                query_emb = embed_waveform(y_full)
                matches = SINGER_DB.query(query_emb, top_k=3)
                singer_identity_result = {
                    "has_references": True,
                    "top_matches": matches,
                    "top_match": matches[0]["name"] if matches else None,
                    "top_similarity": matches[0]["similarity"] if matches else None,
                }
            except Exception as e:
                print(f"Singer identity error (non-fatal): {e}")

        return {
            "code": 200,
            "message": "success",
            "data": {
                "filename": file.filename,
                "score": avg_score,
                "is_fake": is_fake,
                "label": "AI Synthetic (DeepFake)" if is_fake else "Real Singing Voice",
                "evidence_image": "data:image/png;base64," + overview_img,
                "suspicious_segments": suspicious_segments_result,
                "singer_identity": singer_identity_result,
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"code": 500, "message": str(e)}


# === 歌手身份管理接口 ===

@app.post("/api/singer/add")
async def add_singer_reference(
    name: str = Form(...),
    file: UploadFile = File(...)
):
    if SINGER_MODEL is None or SINGER_DB is None:
        raise HTTPException(status_code=500, detail="歌手识别模型未加载")

    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="歌手名称不能为空")

    try:
        audio_bytes = await file.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            y, _ = librosa.load(tmp_path, sr=SAMPLE_RATE, mono=True)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        embedding = embed_waveform(y)
        clips_count = SINGER_DB.add_embedding(name, embedding)

        return {
            "code": 200,
            "message": f"歌手 '{name}' 已添加（共 {clips_count} 个片段）",
            "data": {
                "name": name,
                "clips_count": clips_count,
                "total_singers": len(SINGER_DB.list_singers())
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"code": 500, "message": str(e)}


@app.get("/api/singer/list")
async def list_singers():
    if SINGER_DB is None:
        return {"code": 200, "data": {"singers": [], "total": 0}}
    try:
        singers = SINGER_DB.list_singers()
        return {"code": 200, "data": {"singers": singers, "total": len(singers)}}
    except Exception as e:
        return {"code": 500, "message": str(e)}


@app.delete("/api/singer/{name}")
async def delete_singer(name: str):
    if SINGER_DB is None:
        raise HTTPException(status_code=500, detail="数据库未初始化")

    from urllib.parse import unquote
    name = unquote(name)

    deleted = SINGER_DB.delete_singer(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"未找到歌手: {name}")
    return {
        "code": 200,
        "message": f"歌手 '{name}' 已删除",
        "data": {"remaining": len(SINGER_DB.list_singers())}
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
