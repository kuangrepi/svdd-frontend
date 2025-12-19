<!-- 文件路径: src/App.vue -->
<template>
  <div class="main-container">
    <el-card class="box-card">
      
      <!-- 1. 标题头 -->
      <template #header>
        <div class="header-box">
          <h2>🎤 歌声 DeepFake 检测系统</h2>
          <p class="subtitle">请上传音频文件 (.wav / .mp3) 进行分析</p>
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
          accept=".wav,.mp3"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            拖拽音频到此处，或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              建议上传时长 4秒 以上的音频片段
            </div>
          </template>
        </el-upload>
      </div>

      <!-- 3. 选中文件后的状态 -->
      <div v-if="file && !result" class="file-status">
        <el-alert
          :title="`已准备就绪: ${file.name}`"
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
        <p>正在进行频谱特征分析...</p>
      </div>

      <!-- 5. 结果展示页 (带图片) -->
      <div v-if="result" class="result-container">
        <el-divider>检测报告</el-divider>

        <!-- 结果结论 -->
        <div class="verdict-box" :class="result.is_fake ? 'fake-style' : 'real-style'">
          <div class="icon">
            <el-icon v-if="result.is_fake"><WarningFilled /></el-icon>
            <el-icon v-else><CircleCheckFilled /></el-icon>
          </div>
          <div class="info">
            <h3>{{ result.label }}</h3>
            <p>置信度: <strong>{{ (result.score * 100).toFixed(1) }}%</strong></p>
          </div>
        </div>

        <!-- 可视化证据图片 -->
        <div class="evidence-box">
          <div class="evidence-header">
            <span>📊 频谱特征分析图</span>
            <el-tag v-if="result.is_fake" type="danger" size="small">发现异常高频伪影</el-tag>
          </div>
          
          <div class="image-wrapper">
            <!-- 直接显示后端返回的 Base64 图片 -->
            <img :src="result.evidence_image" alt="Evidence" class="evidence-img" />
          </div>
          
          <p class="desc">
            * <span v-if="result.is_fake">红框区域标记了模型识别到的 DeepFake 生成痕迹（常见于高频部分）。</span>
            <span v-else>频谱图纹理自然，未发现明显的合成特征。</span>
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

// --- 变量定义 ---
const file = ref(null)         // 存放当前文件
const loading = ref(false)     // 是否正在加载
const progress = ref(0)        // 进度条数字
const result = ref(null)       // 存放最终结果

// --- 方法定义 ---

// 1. 文件被选择时触发
const handleFileChange = (uploadFile) => {
  file.value = uploadFile.raw
  result.value = null
}

// 2. 点击开始检测 (连接真实后端)
const startAnalysis = async () => {
  if (!file.value) {
    ElMessage.warning('请先选择音频文件！')
    return
  }
  
  loading.value = true
  progress.value = 0
  
  // 搞个虚假的进度条动画 (为了体验好)
  const timer = setInterval(() => {
    if (progress.value < 80) progress.value += 5
  }, 300)

  try {
    // A. 准备表单数据
    const formData = new FormData()
    // 这里的 key 'file' 必须对应后端 api_server.py 里的参数名
    formData.append('file', file.value) 

    // B. 发送真实请求给后端
    // 假设后端地址是 127.0.0.1:8000
    const response = await axios.post('http://127.0.0.1:8000/api/predict', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000 // 超时时间设为60秒
    })

    // C. 处理结果
    const resData = response.data
    
    if (resData.code === 200) {
      // 成功！保存数据
      result.value = resData.data
      progress.value = 100
      ElMessage.success('检测完成')
    } else {
      // 后端报错 (比如文件损坏)
      ElMessage.error('后端处理失败: ' + resData.message)
    }

  } catch (error) {
    console.error(error)
    // 网络错误 (后端没开，或者跨域问题)
    ElMessage.error('连接失败：请确认后端黑窗口是否已启动！')
  } finally {
    // 无论成功失败，都停止加载动画
    clearInterval(timer)
    loading.value = false
  }
}

// 3. 重置页面
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
}

.box-card {
  width: 600px;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}

.header-box {
  text-align: center;
}

.subtitle {
  color: #909399;
  font-size: 14px;
  margin-top: 5px;
}

.upload-area {
  padding: 20px;
}

.file-status {
  text-align: center;
  margin: 20px 0;
}

.btn-group {
  margin-top: 20px;
}

.loading-box {
  text-align: center;
  padding: 40px;
}
.loading-box p {
  margin-top: 15px;
  color: #409EFF;
}

/* 结果区域样式 */
.result-container {
  padding: 10px;
}

.verdict-box {
  display: flex;
  align-items: center;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.fake-style {
  background-color: #fef0f0;
  border: 2px solid #ffdede;
  color: #f56c6c;
}

.real-style {
  background-color: #f0f9eb;
  border: 2px solid #e1f3d8;
  color: #67c23a;
}

.icon {
  font-size: 40px;
  margin-right: 15px;
  display: flex;
  align-items: center;
}

/* 证据图样式 */
.evidence-box {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 15px;
  background-color: #fff;
}

.evidence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-weight: bold;
  color: #303133;
}

.image-wrapper {
  width: 100%;
  height: 200px;
  background-color: #f5f7fa;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  border-radius: 4px;
}

.evidence-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.desc {
  font-size: 12px;
  color: #909399;
  margin-top: 10px;
  line-height: 1.4;
}

.re-upload-btn {
  width: 100%;
  margin-top: 20px;
  padding: 20px;
}
</style>