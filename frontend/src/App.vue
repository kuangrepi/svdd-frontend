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

        <!-- 歌手身份分析 -->
        <div v-if="result.singer_identity" class="singer-section">
          <div class="section-title-singer">🎤 歌手身份分析</div>
          <div v-if="!result.singer_identity.has_references" class="singer-empty">
            尚未添加参考歌手，无法进行身份匹配
          </div>
          <div v-else class="singer-matches">
            <div
              v-for="(match, idx) in result.singer_identity.top_matches"
              :key="idx"
              class="singer-match-row"
            >
              <span class="singer-rank">{{ ['最佳', '第二', '第三'][idx] }}</span>
              <span class="singer-name">{{ match.name }}</span>
              <el-progress
                :percentage="Math.max(0, match.similarity) * 100"
                :format="() => simPercent(match.similarity)"
                :color="idx === 0 ? '#409EFF' : '#909399'"
                style="flex: 1; margin: 0 12px;"
              />
            </div>
          </div>
          <el-button size="small" style="margin-top: 12px;" @click="openSingerDialog">
            管理参考歌手
          </el-button>
        </div>

        <!-- ⚠️ Top 3 伪造片段展示 -->
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

        <!-- 整体概览图 -->
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

    <!-- 歌手管理对话框 -->
    <el-dialog
      v-model="singerReferenceDialog"
      title="管理参考歌手"
      width="500px"
      destroy-on-close
    >
      <el-tabs v-model="singerDialogTab">

        <!-- 已有歌手列表 -->
        <el-tab-pane label="已有歌手" name="list">
          <div v-if="singerList.length === 0" class="singer-dialog-empty">
            暂无参考歌手，请在「添加歌手」页面添加
          </div>
          <el-table v-else :data="singerList" style="width: 100%">
            <el-table-column prop="name" label="歌手名称" />
            <el-table-column prop="clips_count" label="片段数" width="80" />
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button type="danger" size="small" @click="deleteSinger(row.name)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 添加新歌手 -->
        <el-tab-pane label="添加歌手" name="add">
          <el-form label-position="top" style="padding: 10px 0;">
            <el-form-item label="歌手名称">
              <el-input
                v-model="newSingerName"
                placeholder="例如：Taylor Swift"
                clearable
              />
            </el-form-item>
            <el-form-item label="参考音频（建议 5–30 秒清晰演唱片段）">
              <el-upload
                :auto-upload="false"
                :on-change="handleSingerFileChange"
                :show-file-list="true"
                :limit="1"
                :on-exceed="() => ElMessage.warning('只能上传一个文件，请先移除已有文件')"
                accept=".wav,.mp3,.flac"
              >
                <el-button>选择音频文件</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                :loading="addingSinger"
                @click="addSingerReference"
              >
                添加参考
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

      </el-tabs>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { WarningFilled, CircleCheckFilled, UploadFilled, Picture as IconPicture } from '@element-plus/icons-vue'

const BASE_URL = 'http://127.0.0.1:8000'

// --- Deepfake detection state ---
const file = ref(null)
const loading = ref(false)
const progress = ref(0)
const result = ref(null)

// --- Singer identity state ---
const singerReferenceDialog = ref(false)
const singerDialogTab = ref('list')
const singerList = ref([])
const newSingerName = ref('')
const newSingerFile = ref(null)
const addingSinger = ref(false)

// ---- Deepfake detection ----

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

  const timer = setInterval(() => {
    if (progress.value < 40) {
      progress.value += Math.floor(Math.random() * 6 + 3)
    } else if (progress.value < 70) {
      progress.value += Math.floor(Math.random() * 5 + 1)
    } else if (progress.value < 95) {
      progress.value += 1
    } else if (progress.value < 99) {
      progress.value += 0.1
    }
    if (progress.value > 99) progress.value = 99
  }, 800)

  try {
    const formData = new FormData()
    formData.append('file', file.value)

    const response = await axios.post(`${BASE_URL}/api/predict`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000
    })

    const resData = response.data

    if (resData.code === 200) {
      progress.value = 100
      setTimeout(() => {
        result.value = resData.data
        ElMessage.success('检测完成')
        loading.value = false
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
    clearInterval(timer)
  }
}

const reset = () => {
  file.value = null
  result.value = null
  loading.value = false
  progress.value = 0
}

// ---- Singer identity ----

const simPercent = (sim) => (Math.max(0, sim) * 100).toFixed(0) + '%'

const openSingerDialog = async () => {
  singerDialogTab.value = 'list'
  singerReferenceDialog.value = true
  await refreshSingerList()
}

const refreshSingerList = async () => {
  try {
    const resp = await axios.get(`${BASE_URL}/api/singer/list`)
    if (resp.data.code === 200) {
      singerList.value = resp.data.data.singers
    }
  } catch {
    ElMessage.error('无法获取歌手列表')
  }
}

const handleSingerFileChange = (uploadFile) => {
  newSingerFile.value = uploadFile.raw
}

const addSingerReference = async () => {
  if (!newSingerName.value.trim()) {
    ElMessage.warning('请输入歌手名称')
    return
  }
  if (!newSingerFile.value) {
    ElMessage.warning('请上传音频片段')
    return
  }

  addingSinger.value = true
  try {
    const formData = new FormData()
    formData.append('name', newSingerName.value.trim())
    formData.append('file', newSingerFile.value)

    const resp = await axios.post(`${BASE_URL}/api/singer/add`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000
    })

    if (resp.data.code === 200) {
      ElMessage.success(resp.data.message)
      newSingerName.value = ''
      newSingerFile.value = null
      await refreshSingerList()
      singerDialogTab.value = 'list'
    } else {
      ElMessage.error('添加失败: ' + resp.data.message)
    }
  } catch {
    ElMessage.error('请求失败，请检查后端是否运行')
  } finally {
    addingSinger.value = false
  }
}

const deleteSinger = async (name) => {
  try {
    const encoded = encodeURIComponent(name)
    const resp = await axios.delete(`${BASE_URL}/api/singer/${encoded}`)
    if (resp.data.code === 200) {
      ElMessage.success(`已删除: ${name}`)
      await refreshSingerList()
    }
  } catch (e) {
    if (e.response?.status === 404) {
      ElMessage.error('歌手不存在')
    } else {
      ElMessage.error('删除失败')
    }
  }
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

/* 歌手身份分析 */
.singer-section {
  background: #f0f7ff;
  border: 1px solid #d0e8ff;
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 20px;
}
.section-title-singer {
  font-weight: bold;
  color: #409EFF;
  margin-bottom: 12px;
  font-size: 15px;
}
.singer-empty {
  color: #909399;
  font-size: 14px;
  padding: 4px 0;
}
.singer-matches {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.singer-match-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.singer-rank {
  width: 36px;
  font-size: 12px;
  color: #606266;
  text-align: right;
  flex-shrink: 0;
}
.singer-name {
  width: 130px;
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}
.singer-dialog-empty {
  text-align: center;
  padding: 20px;
  color: #909399;
}

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
