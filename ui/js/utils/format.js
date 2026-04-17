/**
 * 格式化工具集
 * 提供常用的格式化方法
 */

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @param {number} decimals - 小数位数，默认为 2
 * @returns {string} 格式化后的文件大小
 */
export function formatFileSize(bytes, decimals = 2) {
  if (bytes === 0) return '0 B';
  
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
}

/**
 * 格式化日期时间
 * @param {string|Date} date - 日期对象或字符串
 * @param {string} format - 格式化模板，默认为 'YYYY-MM-DD HH:mm:ss'
 * @returns {string} 格式化后的日期时间
 */
export function formatDateTime(date, format = 'YYYY-MM-DD HH:mm:ss') {
  if (!date) return '-';
  
  try {
    const d = typeof date === 'string' ? new Date(date) : date;
    
    if (isNaN(d.getTime())) return '-';
    
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');
    
    return format
      .replace('YYYY', year)
      .replace('MM', month)
      .replace('DD', day)
      .replace('HH', hours)
      .replace('mm', minutes)
      .replace('ss', seconds);
  } catch (e) {
    return '-';
  }
}

/**
 * 格式化相对时间（例如：刚刚、5分钟前、昨天等）
 * @param {string|Date} date - 日期对象或字符串
 * @returns {string} 相对时间描述
 */
export function formatRelativeTime(date) {
  if (!date) return '-';
  
  try {
    const d = typeof date === 'string' ? new Date(date) : date;
    const now = new Date();
    const diff = now - d; // 毫秒差
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (seconds < 60) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 7) return `${days}天前`;
    
    // 超过7天，显示具体日期
    return formatDateTime(d, 'YYYY-MM-DD');
  } catch (e) {
    return '-';
  }
}

/**
 * HTML 转义
 * @param {string} text - 要转义的文本
 * @returns {string} 转义后的文本
 */
export function escapeHtml(text) {
  if (typeof text !== 'string') return '';
  
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * HTML 反转义
 * @param {string} html - 要反转义的 HTML
 * @returns {string} 反转义后的文本
 */
export function unescapeHtml(html) {
  if (typeof html !== 'string') return '';
  
  const div = document.createElement('div');
  div.innerHTML = html;
  return div.textContent;
}

/**
 * 截断文本
 * @param {string} text - 要截断的文本
 * @param {number} length - 最大长度
 * @param {string} suffix - 后缀，默认为 '...'
 * @returns {string} 截断后的文本
 */
export function truncate(text, length, suffix = '...') {
  if (typeof text !== 'string') return '';
  if (text.length <= length) return text;
  
  return text.substring(0, length) + suffix;
}

/**
 * 格式化数字（添加千分位分隔符）
 * @param {number} num - 数字
 * @param {number} decimals - 小数位数
 * @returns {string} 格式化后的数字
 */
export function formatNumber(num, decimals = 0) {
  if (typeof num !== 'number' || isNaN(num)) return '-';
  
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

/**
 * 格式化百分比
 * @param {number} value - 值（0-1之间）
 * @param {number} decimals - 小数位数
 * @returns {string} 百分比字符串
 */
export function formatPercentage(value, decimals = 0) {
  if (typeof value !== 'number' || isNaN(value)) return '-';
  
  return (value * 100).toFixed(decimals) + '%';
}

/**
 * 获取文件图标
 * @param {string} filename - 文件名
 * @returns {string} 图标字符
 */
export function getFileIcon(filename) {
  if (!filename) return '📎';
  
  const ext = filename.split('.').pop().toLowerCase();
  const icons = {
    'pdf': '📄',
    'doc': '📝',
    'docx': '📝',
    'txt': '📃',
    'md': '📝',
    'jpg': '🖼️',
    'jpeg': '🖼️',
    'png': '🖼️',
    'gif': '🖼️',
    'svg': '🖼️',
    'xls': '📊',
    'xlsx': '📊',
    'csv': '📊',
    'zip': '📦',
    'rar': '📦',
    '7z': '📦',
    'mp3': '🎵',
    'mp4': '🎬',
    'json': '📋',
    'js': '💻',
    'ts': '💻',
    'html': '🌐',
    'css': '🎨'
  };
  
  return icons[ext] || '📎';
}

/**
 * 格式化持续时间
 * @param {number} seconds - 秒数
 * @returns {string} 持续时间描述
 */
export function formatDuration(seconds) {
  if (typeof seconds !== 'number' || seconds < 0) return '-';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours}小时${minutes}分钟${secs}秒`;
  } else if (minutes > 0) {
    return `${minutes}分钟${secs}秒`;
  } else {
    return `${secs}秒`;
  }
}

export default {
  formatFileSize,
  formatDateTime,
  formatRelativeTime,
  escapeHtml,
  unescapeHtml,
  truncate,
  formatNumber,
  formatPercentage,
  getFileIcon,
  formatDuration
};
