/**
 * FileManager - 文件管理组件
 * 负责文件选择、上传和显示
 */

import Store from '../core/Store.js';
import { formatFileSize, getFileIcon, escapeHtml } from '../utils/format.js';
import config from '../config.js';

// 文件管理状态
const fileStore = new Store({
  files: [],
  isUploading: false
});

/**
 * FileManager 类
 */
class FileManager {
  constructor() {
    // DOM 元素
    this.fileUploadArea = null;
    this.fileInput = null;
    this.selectedFiles = null;
    this.selectedFilesList = null;
    this.clearFilesBtn = null;

    console.log('[FileManager] 初始化');
  }

  /**
   * 初始化文件管理器
   */
  init() {
    this.cacheElements();
    this.bindEvents();
    console.log('[FileManager] 初始化完成');
  }

  /**
   * 缓存 DOM 元素
   */
  cacheElements() {
    this.fileUploadArea = document.getElementById('file-upload-area');
    this.fileInput = document.getElementById('file-input');
    this.selectedFiles = document.getElementById('selected-files');
    this.selectedFilesList = document.getElementById('selected-files-list');
    this.clearFilesBtn = document.getElementById('clear-files-btn');
  }

  /**
   * 绑定事件
   */
  bindEvents() {
    if (!this.fileInput) {
      console.error('[FileManager] fileInput 元素未找到');
      return;
    }

    // 文件选择事件
    this.fileInput.addEventListener('change', (e) => {
      console.log('[FileManager] 文件选择事件触发');
      this.handleFileSelect(e.target.files);
      e.target.value = ''; // 清空 input，允许重复选择
    });

    // 拖拽事件
    if (this.fileUploadArea) {
      this.fileUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.fileUploadArea.classList.add('dragover');
      });

      this.fileUploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.fileUploadArea.classList.remove('dragover');
      });

      this.fileUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.fileUploadArea.classList.remove('dragover');
        this.handleFileSelect(e.dataTransfer.files);
      });

      // 点击上传区域触发文件选择
      this.fileUploadArea.addEventListener('click', (e) => {
        if (e.target === this.fileInput || e.target.closest('.file-item-remove')) {
          return;
        }
        this.fileInput.click();
      });
    }

    // 清空文件按钮
    if (this.clearFilesBtn) {
      this.clearFilesBtn.addEventListener('click', () => {
        this.clearSelectedFiles();
      });
    }
  }

  /**
   * 处理文件选择
   * @param {FileList} files - 选择的文件列表
   */
  handleFileSelect(files) {
    if (!files || files.length === 0) {
      console.log('[FileManager] 没有选择文件');
      return;
    }

    console.log('[FileManager] 处理文件选择，文件数量:', files.length);

    const currentFiles = fileStore.state.files;

    Array.from(files).forEach(file => {
      // 检查文件大小
      if (file.size > config.MAX_FILE_SIZE) {
        this.showToast(`文件 ${file.name} 超过50MB限制`, 'warning');
        return;
      }

      // 检查是否已存在
      const exists = currentFiles.some(f => f.name === file.name && f.size === file.size);
      if (!exists) {
        currentFiles.push(file);
        console.log('[FileManager] 添加新文件:', file.name);
      }
    });

    fileStore.state.files = [...currentFiles];
    this.renderSelectedFiles();
  }

  /**
   * 渲染已选文件列表
   */
  renderSelectedFiles() {
    if (!this.selectedFiles || !this.selectedFilesList) {
      console.error('[FileManager] 元素未找到');
      return;
    }

    const files = fileStore.state.files;
    console.log('[FileManager] 渲染文件列表，数量:', files.length);

    if (files.length === 0) {
      this.selectedFiles.style.display = 'none';
      this.selectedFilesList.innerHTML = '';
      return;
    }

    this.selectedFiles.style.display = 'block';

    const filesHtml = files.map((file, index) => {
      return `<div class="file-item">
        <div class="file-item-info">
          <span class="file-item-icon">${getFileIcon(file.name)}</span>
          <span class="file-item-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
          <span class="file-item-size">${formatFileSize(file.size)}</span>
        </div>
        <button class="file-item-remove" data-index="${index}" title="移除文件">×</button>
      </div>`;
    }).join('');

    this.selectedFilesList.innerHTML = filesHtml;

    // 绑定移除按钮事件
    const removeButtons = this.selectedFilesList.querySelectorAll('.file-item-remove');
    removeButtons.forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const index = parseInt(btn.dataset.index);
        if (!isNaN(index)) {
          this.removeFile(index);
        }
      });
    });
  }

  /**
   * 移除文件
   * @param {number} index - 文件索引
   */
  removeFile(index) {
    const files = fileStore.state.files;
    if (index < 0 || index >= files.length) {
      console.error('[FileManager] 无效的索引:', index);
      return;
    }

    console.log('[FileManager] 移除文件:', files[index].name);
    files.splice(index, 1);
    fileStore.state.files = [...files];
    this.renderSelectedFiles();
  }

  /**
   * 清空已选文件
   */
  clearSelectedFiles() {
    fileStore.state.files = [];
    this.renderSelectedFiles();
    console.log('[FileManager] 文件已清空');
  }

  /**
   * 上传文件
   * @param {string} threadId - 会话 ID
   * @returns {Promise<string>} - 返回 thread_id
   */
  async uploadFiles(threadId) {
    const files = fileStore.state.files;
    if (files.length === 0) {
      throw new Error('没有选择文件');
    }

    fileStore.state.isUploading = true;

    const effectiveThreadId = threadId || crypto.randomUUID();
    const formData = new FormData();

    files.forEach(file => {
      formData.append('files', file);
    });
    formData.append('thread_id', effectiveThreadId);

    const uploadUrl = `${config.API_BASE_URL}/api/upload`;
    console.log('[FileManager] 上传文件到:', uploadUrl);

    try {
      const token = localStorage.getItem(config.TOKEN_KEY);
      const headers = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(uploadUrl, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`上传失败: ${response.status} ${errorText}`);
      }

      const result = await response.json();
      console.log('[FileManager] 上传结果:', result);

      // 上传成功后清空文件列表
      this.clearSelectedFiles();

      return effectiveThreadId;
    } finally {
      fileStore.state.isUploading = false;
    }
  }

  /**
   * 显示 Toast 提示（由外部提供）
   * @param {string} message - 消息
   * @param {string} type - 类型
   */
  showToast(message, type) {
    // 触发事件，由外部处理
    window.dispatchEvent(new CustomEvent('filemanager:toast', {
      detail: { message, type }
    }));
  }

  /**
   * 获取当前文件列表
   * @returns {Array} 文件列表
   */
  getFiles() {
    return [...fileStore.state.files];
  }

  /**
   * 获取文件数量
   * @returns {number} 文件数量
   */
  getFileCount() {
    return fileStore.state.files.length;
  }

  /**
   * 是否正在上传
   * @returns {boolean}
   */
  isUploading() {
    return fileStore.state.isUploading;
  }
}

// 创建单例
const fileManager = new FileManager();

/**
 * 初始化文件管理器
 */
export function initFileManager() {
  fileManager.init();
}

/**
 * 处理文件选择
 * @param {FileList} files - 文件列表
 */
export function handleFileSelect(files) {
  fileManager.handleFileSelect(files);
}

/**
 * 移除文件
 * @param {number} index - 文件索引
 */
export function removeFile(index) {
  fileManager.removeFile(index);
}

/**
 * 上传文件
 * @param {string} threadId - 会话 ID
 * @returns {Promise<string>}
 */
export function uploadFiles(threadId) {
  return fileManager.uploadFiles(threadId);
}

/**
 * 清空已选文件
 */
export function clearSelectedFiles() {
  fileManager.clearSelectedFiles();
}

/**
 * 获取文件列表
 * @returns {Array}
 */
export function getFiles() {
  return fileManager.getFiles();
}

/**
 * 获取文件状态
 * @returns {Object}
 */
export function getFileState() {
  return fileStore.getState();
}

/**
 * 订阅文件状态变化
 * @param {Function} callback - 回调函数
 * @returns {Function} 取消订阅函数
 */
export function subscribeFiles(callback) {
  return fileStore.subscribe('files', callback);
}

export default {
  initFileManager,
  handleFileSelect,
  removeFile,
  uploadFiles,
  clearSelectedFiles,
  getFiles,
  getFileState,
  subscribeFiles,
  FileManager
};
