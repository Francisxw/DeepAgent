/**
 * Toast 通知组件
 * 统一的 Toast 提示功能
 */

/**
 * 显示 Toast 提示
 * @param {string} message - 提示消息
 * @param {string} type - 提示类型: 'success' | 'error' | 'warning' | 'info'
 * @param {number} duration - 显示时长（毫秒）
 */
export function showToast(message, type = 'info', duration = 3000) {
  removeToast();
  
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span class="toast-icon">${getToastIcon(type)}</span> ${message}`;
  document.body.appendChild(toast);
  
  // 自动移除
  setTimeout(() => {
    if (toast.parentNode) {
      document.body.removeChild(toast);
    }
  }, duration);
}

/**
 * 获取 Toast 图标
 * @param {string} type - 提示类型
 * @returns {string} - 图标字符
 */
export function getToastIcon(type) {
  const icons = {
    'success': '✅',
    'error': '❌',
    'warning': '⚠️',
    'info': 'ℹ️'
  };
  return icons[type] || 'ℹ️';
}

/**
 * 移除所有 Toast
 */
export function removeToast() {
  const toasts = document.querySelectorAll('.toast');
  toasts.forEach(toast => {
    if (toast.parentNode) {
      document.body.removeChild(toast);
    }
  });
}
