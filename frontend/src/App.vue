<!-- 文件路径: src/App.vue -->
<template>
  <div class="main-container">
    <el-card class="box-card">
      
      <!-- 1. 标题头 -->
      <template #header>
        <div class="header-box">
          <h2>🎤 歌声 DeepFake 检测系统</h2>
          <p class="subtitle">请上传音频文件进行分析</p>
        </div>
      </template>

      <!-- 2. 上传区域 -->
      <div class="upload-area" v-if="!loading && !result">
        <el-upload
          class="upload-demo"
          drag
          action="#"
          :auto-upload="false"
          :on-change="handleFileChange"
          :show-file-list="false"
          accept=".wav,.mp3,.flac"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            拖拽音频到此处，或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持长音频自动切片分析
            </div>
          </template>
        </el-upload>
      </div>

      <!-- 3. 选中文件后的状态 -->
      <div v-if="file && !result" class="file-status">
        <el-alert
          :title="`已选择: ${file.name}`"
          type="info"
          show-icon
          :closable="false"
        />
        <div class="btn-group">
          <el-button type="primary" size="large" @click="startAnalysis" :loading="loading">
            🚀 开始检测
          </el-button>
          <el-button size="large" @click="reset">重置</el-button>
        </div>
      </div>

      <!-- 4. 检测中动画 -->
      <div v-if="loading" class="loading-box">
        <el-progress type="circle" :percentage="progress" />
        <p>正在进行全曲切片扫描...</p>
      </div>

      <!-- 5. 结果展示页 -->
      <div v-if="result" class="result-container">
        
        <!-- 头部：文件名 -->
        <div class="result-header">
          <div class="filename-tag">🎵 分析对象: {{ result.filename }}</div>
        </div>

        <!-- 结论 -->
        <div class="verdict-box" :class="result.is_fake ? 'fake-style' : 'real-style'">
          <div class="icon">
            <el-icon v-if="result.is_fake"><WarningFilled /></el-icon>
            <el-icon v-else><CircleCheckFilled /></el-icon>
          </div>
          <div class="info">
            <h3>{{ result.label }}</h3>
            <p>综合置信度: <strong>{{ (result.score * 100).toFixed(1) }}%</strong></p>
          </div>
        </div>

        <!-- ⚠️ 重点：Top 3 伪造片段展示 (点击放大) -->
        <div v-if="result.is_fake && result.suspicious_segments.length > 0" class="segments-section">
          <div class="section-title">⚠️ 发现高危伪造片段 (Top 3) - 点击图片放大</div>
          <div class="segments-grid">
            <div 
              v-for="(seg, idx) in result.suspicious_segments" 
              :key="idx" 
              class="segment-card"
            >
              <div class="seg-img-wrapper">
                <el-image 
                  :src="seg.image" 
                  class="seg-img"
                  :preview-src-list="[seg.image]"
                  fit="contain"
                  hide-on-click-modal
                  preview-teleported
                >
                  <template #error>
                    <div class="image-slot"><el-icon><icon-picture /></el-icon></div>
                  </template>
                </el-image>
              </div>
              <div class="seg-info">
                <span class="time-badge">{{ seg.start }}s - {{ seg.end }}s</span>
                <span class="score-badge">真实度: {{ (seg.score * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 整体概览图 (点击放大) -->
        <div class="evidence-box">
          <div class="evidence-header">
            <span>📊 整体频谱概览 (前10秒)</span>
          </div>
          <div class="image-wrapper">
            <el-image 
              :src="result.evidence_image" 
              class="evidence-img"
              :preview-src-list="[result.evidence_image]"
              fit="contain"
              hide-on-click-modal
              preview-teleported
            />
          </div>
          <p class="desc">
            * 上图为音频的梅尔频谱图 (Mel-Spectrogram)，展示了声音在频域上的能量分布特征。
          </p>
        </div>

        <el-button class="re-upload-btn" @click="reset">检测下一首</el-button>
      </div>

    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { WarningFilled, CircleCheckFilled, UploadFilled, Picture as IconPicture } from '@element-plus/icons-vue'

const file = ref(null)
const loading = ref(false)
const progress = ref(0)
const result = ref(null)

const handleFileChange = (uploadFile) => {
  file.value = uploadFile.raw
  result.value = null
}

const startAnalysis = async () => {
  if (!file.value) {
    ElMessage.warning('请先选择音频文件！')
    return
  }
  
  loading.value = true
  progress.value = 0
  
  // ✨✨✨ 优化后的进度条逻辑：渐近式增长，不会死卡 ✨✨✨
  // 每 800 毫秒动一次 (变慢一点)
  const timer = setInterval(() => {
    if (progress.value < 40) {
      // 第一阶段：快速冲到 40% (模拟上传)
      progress.value += Math.floor(Math.random() * 6 + 3)
    } else if (progress.value < 70) {
      // 第二阶段：中速处理
      progress.value += Math.floor(Math.random() * 5 + 1)
    } else if (progress.value < 95) {
      // 第三阶段：龟速蠕动 (给后端留足时间)
      progress.value += 1
    } else if (progress.value < 99) {
      // 第四阶段：卡在 99% 等结果，绝不到 100%
      progress.value += 0.1
    }
    // 限制最大 99%，防止溢出
    if (progress.value > 99) progress.value = 99
  }, 800)

  try {
    const formData = new FormData()
    formData.append('file', file.value) 

    // 发送请求
    const response = await axios.post('http://127.0.0.1:8000/api/predict', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000 // ⚠️ 将超时设为 5分钟 (防止大文件处理慢导致断开)
    })

    const resData = response.data
    
    if (resData.code === 200) {
      // 拿到结果瞬间，进度条拉满
      progress.value = 100
      // 稍微延迟一点点显示结果，让用户看到 100% 的瞬间
      setTimeout(() => {
        result.value = resData.data
        ElMessage.success('检测完成')
        loading.value = false // 停止加载动画
      }, 500)
    } else {
      ElMessage.error('后端处理失败: ' + resData.message)
      loading.value = false
    }

  } catch (error) {
    console.error(error)
    ElMessage.error('连接失败：请确认后端是否启动，或文件是否过大！')
    loading.value = false
  } finally {
    clearInterval(timer) // 清除定时器
  }
}

const reset = () => {
  file.value = null
  result.value = null
  loading.value = false
  progress.value = 0
}
</script>

<style scoped>
.main-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', sans-serif;
  padding: 20px;
}

.box-card {
  width: 750px;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}

.header-box { text-align: center; }
.subtitle { color: #909399; font-size: 14px; margin-top: 5px; }
.upload-area { padding: 20px; }
.file-status { text-align: center; margin: 20px 0; }
.btn-group { margin-top: 20px; }
.loading-box { text-align: center; padding: 40px; }
.loading-box p { margin-top: 15px; color: #409EFF; }

/* 结果区域 */
.result-container { padding: 10px; }

.filename-tag {
  background: #ecf5ff;
  color: #409eff;
  padding: 8px 12px;
  border-radius: 4px;
  font-weight: bold;
  display: inline-block;
  margin-bottom: 15px;
  border: 1px solid #d9ecff;
}

.verdict-box {
  display: flex;
  align-items: center;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}
.fake-style { background-color: #fef0f0; border: 2px solid #ffdede; color: #f56c6c; }
.real-style { background-color: #f0f9eb; border: 2px solid #e1f3d8; color: #67c23a; }
.icon { font-size: 40px; margin-right: 15px; display: flex; align-items: center; }

/* 伪造片段展示区 */
.segments-section {
  margin-bottom: 25px;
  background: #fffafa;
  padding: 15px;
  border-radius: 8px;
  border: 1px dashed #ffcccc;
}
.section-title {
  color: #f56c6c;
  font-weight: bold;
  margin-bottom: 10px;
  font-size: 15px;
}
.segments-grid {
  display: flex;
  gap: 15px;
  justify-content: space-between;
}
.segment-card {
  flex: 1;
  background: white;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.seg-img-wrapper {
  width: 100%;
  height: 90px;
  background: #f5f7fa;
  display: flex;
  justify-content: center;
  align-items: center;
}
.seg-img {
  width: 100%;
  height: 100%;
}
.seg-info {
  padding: 8px;
  text-align: center;
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.time-badge { background: #909399; color: white; padding: 2px 6px; border-radius: 10px; font-size: 11px;}
.score-badge { color: #f56c6c; font-weight: bold; }

/* 概览图 */
.evidence-box {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 15px;
  background-color: #fff;
}
.evidence-header { margin-bottom: 10px; font-weight: bold; color: #303133; }
.image-wrapper { width: 100%; background-color: #f5f7fa; border-radius: 4px; overflow: hidden; }
.evidence-img { width: 100%; display: block; }

.desc { font-size: 12px; color: #909399; margin-top: 10px; line-height: 1.4; }
.re-upload-btn { width: 100%; margin-top: 20px; padding: 20px; }
</style>