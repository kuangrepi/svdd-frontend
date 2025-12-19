import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np

audio_path = 'test.wav' # 请替换为你的音频文件路径

y, sr = librosa.load(audio_path, sr=None) 

# 2. 计算短时傅里叶变换 (STFT)
# 这一步将音频从时域转换到频域
D = librosa.stft(y)

# 3. 将幅度转换为分贝 (dB)
# 原始幅度数据的动态范围非常大，转换为对数刻度(dB)更符合人耳听觉且易于可视化
# ref=np.max 表示以最大值为参考，最高点为 0 dB
S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max)

# 4. 绘图
plt.figure(figsize=(12, 6))

# 使用 librosa 的 specshow 辅助绘图，它可以自动处理坐标轴
librosa.display.specshow(S_db, sr=sr, x_axis='time', y_axis='log')

plt.colorbar(format='%+2.0f dB') # 添加颜色条
plt.title('Spectrogram (STFT)')
plt.xlabel('Time')
plt.ylabel('Frequency (Log Scale)')
plt.tight_layout()
plt.show()