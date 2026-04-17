/**
 * ProgressDisplay - 进度显示组件
 * 负责管理进度列表的显示和更新
 */

import Store from '../core/Store.js';
import { escapeHtml } from '../utils/format.js';

// 进度显示状态
const progressStore = new Store({
  items: []
});

/**
 * 添加进度项
 * @param {string} type - 类型 (tool, assistant, error, result, session, info)
 * @param {string} icon - 图标
 * @param {string} message - 消息
 * @param {boolean} isLast - 是否是最后一项
 */
export function addProgressItem(type, icon, message, isLast = false) {
  const progressContent = document.getElementById('progress-content');
  if (!progressContent) return;

  const item = document.createElement('div');
  item.className = `progress-item progress-item-${type} ${isLast ? 'progress-item-last' : ''}`;
  item.innerHTML = `
    <span class="progress-icon">${icon}</span>
    <span class="progress-message">${escapeHtml(message)}</span>
    <span class="progress-time">${new Date().toLocaleTimeString()}</span>
  `;
  progressContent.appendChild(item);

  // 更新状态
  progressStore.state.items = [...progressStore.state.items, { type, icon, message, isLast }];

  console.log(`[Progress] 添加进度项 [${type}]:`, message);

  // 自动滚动到最新进度
  setTimeout(() => {
    item.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, 100);
}

/**
 * 清空进度列表
 */
export function clearProgress() {
  const progressContent = document.getElementById('progress-content');
  if (progressContent) {
    progressContent.innerHTML = '';
  }
  
  // 重置状态
  progressStore.state.items = [];
  console.log('[Progress] 进度已清空');
}

/**
 * 获取进度状态
 * @returns {Object} 进度状态快照
 */
export function getProgressState() {
  return progressStore.getState();
}

/**
 * 订阅进度变化
 * @param {Function} callback - 回调函数
 * @returns {Function} 取消订阅函数
 */
export function subscribeProgress(callback) {
  return progressStore.subscribe('items', callback);
}

export default {
  addProgressItem,
  clearProgress,
  getProgressState,
  subscribeProgress
};
