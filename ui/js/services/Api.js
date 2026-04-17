/**
 * Api - API 请求服务
 * 封装所有 HTTP 请求
 */

import config from '../config.js';

/**
 * 获取认证请求头
 * @returns {Object} 请求头对象
 */
function getAuthHeaders() {
  const token = localStorage.getItem(config.TOKEN_KEY);
  const headers = {
    'Content-Type': 'application/json'
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * 发起搜索任务
 * @param {string} query - 搜索查询
 * @param {string} threadId - 会话 ID（可选）
 * @returns {Promise<Object>} 响应结果
 */
export async function searchTask(query, threadId = null) {
  try {
    const body = { query };
    if (threadId) {
      body.thread_id = threadId;
    }

    const response = await fetch(`${config.API_BASE_URL}/api/task`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`请求失败: ${response.status} ${errorText}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error('[Api] 搜索任务失败:', error);
    throw error;
  }
}

/**
 * 上传文件
 * @param {FileList|Array} files - 文件列表
 * @param {string} threadId - 会话 ID
 * @returns {Promise<Object>} 响应结果
 */
export async function uploadFiles(files, threadId) {
  const formData = new FormData();
  
  Array.from(files).forEach(file => {
    formData.append('files', file);
  });
  formData.append('thread_id', threadId);

  try {
    const token = localStorage.getItem(config.TOKEN_KEY);
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${config.API_BASE_URL}/api/upload`, {
      method: 'POST',
      headers,
      body: formData
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`上传失败: ${response.status} ${errorText}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error('[Api] 文件上传失败:', error);
    throw error;
  }
}

/**
 * 下载文件
 * @param {string} path - 文件路径
 * @returns {Promise<void>}
 */
export async function downloadFile(path) {
  const encodedPath = encodeURIComponent(path);
  const url = `${config.API_BASE_URL}/api/download?path=${encodedPath}`;

  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`下载失败: ${response.status}`);
    }

    // 创建下载链接
    const blob = await response.blob();
    const downloadUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = path.split('/').pop();
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(downloadUrl);
  } catch (error) {
    console.error('[Api] 文件下载失败:', error);
    throw error;
  }
}

/**
 * 获取文件列表
 * @param {string} path - 目录路径
 * @returns {Promise<Object>} 文件列表
 */
export async function listFiles(path) {
  const encodedPath = encodeURIComponent(path);
  const url = `${config.API_BASE_URL}/api/files?path=${encodedPath}`;

  try {
    const response = await fetch(url, {
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error(`获取文件列表失败: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error('[Api] 获取文件列表失败:', error);
    throw error;
  }
}

/**
 * 获取当前用户信息
 * @returns {Promise<Object>} 用户信息
 */
export async function getCurrentUser() {
  try {
    const response = await fetch(`${config.API_BASE_URL}/api/auth/me`, {
      method: 'GET',
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error(`获取用户信息失败: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error('[Api] 获取用户信息失败:', error);
    throw error;
  }
}

/**
 * 检查服务器状态
 * @returns {Promise<boolean>} 服务器是否正常
 */
export async function checkServerStatus() {
  try {
    const response = await fetch(`${config.API_BASE_URL}/api/task`, {
      method: 'OPTIONS'
    });
    return response.ok;
  } catch (error) {
    console.error('[Api] 服务器状态检查失败:', error);
    return false;
  }
}

export default {
  searchTask,
  uploadFiles,
  downloadFile,
  listFiles,
  getCurrentUser,
  checkServerStatus,
  getAuthHeaders
};
