/**
 * ResultFormatter - 结果格式化组件
 * 负责将搜索结果格式化为 HTML
 */

import { escapeHtml } from '../utils/format.js';
import config from '../config.js';

/**
 * 格式化结果
 * @param {string|object} result - 原始结果
 * @returns {string} - 格式化后的 HTML
 */
export function formatResult(result) {
  console.log('[ResultFormatter] 格式化结果:', result);

  if (typeof result === 'string') {
    // 纯文本结果
    return formatText(result);
  } else if (typeof result === 'object' && result !== null) {
    // 结构化结果
    return formatObject(result);
  }

  return `<p>${escapeHtml(String(result))}</p>`;
}

/**
 * 格式化文本
 * @param {string} text - 文本
 * @returns {string} - 格式化后的 HTML
 */
export function formatText(text) {
  // 使用占位符策略：先用占位符替换文件路径，Markdown 处理完后再恢复
  // 这样可以防止 Markdown 正则（加粗/斜体/代码）破坏已生成的 <a> 标签
  const placeholders = [];
  let html = extractFilePaths(text, placeholders);

  // Markdown 基本格式转换
  // 加粗: **text**
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // 代码: `text`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // 处理换行
  html = html.split('\n').map(line => {
    line = line.trim();
    return line ? `<p>${line}</p>` : '';
  }).join('');

  // 恢复占位符为下载链接
  placeholders.forEach(({ placeholder, link }) => {
    html = html.replace(placeholder, link);
  });

  return html;
}

/**
 * 提取文件路径并替换为占位符（防止 Markdown 正则污染链接）
 * @param {string} text - 包含文件路径的文本
 * @param {Array} placeholders - 占位符收集数组
 * @returns {string} - 替换后的文本（路径变为占位符）
 */
export function extractFilePaths(text, placeholders) {
  const fileExts = 'pdf|md|doc|docx|txt|jpg|jpeg|png|gif|xls|xlsx|csv|zip|rar';

  // 1. 匹配 Windows 绝对路径
  const windowsPathRegex = new RegExp(
    `([A-Za-z]:\\\\(?:[^\\\\/:*?"<>|\\r\\n]+\\\\)*[^\\\\/:*?"<>|\\r\\n]+\\.(?:${fileExts}))`,
    'gi'
  );

  // 2. 匹配 updated/ 开头的相对路径
  const updatedRelativeRegex = new RegExp(
    `(updated[\\\\/](?:session_[\\w-]+[\\\\/])?(?:[^\\s]+[\\\\/])*[^\\s]+\\.(?:${fileExts}))`,
    'gi'
  );

  // 3. 匹配 output/ 开头的相对路径
  const outputRelativeRegex = new RegExp(
    `(output[\\\\/](?:[^\\s]+[\\\\/])*[^\\s]+\\.(?:${fileExts}))`,
    'gi'
  );

  // 替换函数：生成占位符和下载链接
  const replaceWithPath = (match) => {
    const normalizedPath = match.replace(/\\/g, '/');
    const fileName = normalizedPath.split('/').pop();
    const downloadUrl = `${config.API_BASE_URL}/api/download?path=${encodeURIComponent(normalizedPath)}`;
    const link = `<a href="${downloadUrl}" target="_blank" class="file-download-link" title="点击下载文件：${fileName}">📥 ${fileName}</a>`;
    const placeholder = `__FILE_LINK_${placeholders.length}__`;
    console.log('[ResultFormatter] 路径转换:', match, '->', normalizedPath);
    placeholders.push({ placeholder, link });
    return placeholder;
  };

  // 先替换 Windows 绝对路径（优先级最高）
  text = text.replace(windowsPathRegex, replaceWithPath);

  // 再替换 updated/ 开头的相对路径
  text = text.replace(updatedRelativeRegex, replaceWithPath);

  // 最后替换 output/ 开头的相对路径
  text = text.replace(outputRelativeRegex, (match) => {
    const normalizedPath = match.replace(/\\/g, '/');
    // output/xxx -> updated/xxx
    const correctedPath = normalizedPath.replace(/^output\//, 'updated/');
    const fileName = correctedPath.split('/').pop();
    const downloadUrl = `${config.API_BASE_URL}/api/download?path=${encodeURIComponent(correctedPath)}`;
    const link = `<a href="${downloadUrl}" target="_blank" class="file-download-link" title="点击下载文件：${fileName}">📥 ${fileName}</a>`;
    const placeholder = `__FILE_LINK_${placeholders.length}__`;
    console.log('[ResultFormatter] output相对路径转换:', match, '->', correctedPath);
    placeholders.push({ placeholder, link });
    return placeholder;
  });

  return text;
}

/**
 * 格式化对象
 * @param {object} obj - 对象
 * @returns {string} - 格式化后的 HTML
 */
export function formatObject(obj) {
  let html = '';

  // 尝试多种可能的搜索结果位置
  const searchResults = obj.search_results || obj.result?.search_results || obj.items || obj.results;

  if (searchResults && Array.isArray(searchResults) && searchResults.length > 0) {
    html += '<div class="search-results"><h3>🔍 搜索结果</h3><ul>';
    searchResults.forEach((item, index) => {
      const title = item.title || item.name || `结果 ${index + 1}`;
      const content = item.content || item.snippet || item.description || item.body || '无内容';
      const url = item.url || item.link || item.href;
      html += `
        <li class="result-item">
          <h4>${escapeHtml(title)}</h4>
          <p>${escapeHtml(content)}</p>
          ${url ? `<a href="${url}" target="_blank" class="result-link">📎 查看详情</a>` : ''}
        </li>
      `;
    });
    html += '</ul></div>';
  }

  // 尝试多种可能的答案位置
  const answer = obj.answer || obj.result?.answer || obj.content || obj.output || obj.message || obj.text;

  if (answer && typeof answer === 'string') {
    html += `<div class="ai-summary"><h3>🤖 AI 回答</h3>${formatText(answer)}</div>`;
  }

  // 如果没有内容，显示原始结果
  if (html === '' || obj.error) {
    html += '<div class="raw-result"><h3>📋 原始结果</h3><pre>' +
      escapeHtml(JSON.stringify(obj, null, 2)) + '</pre></div>';
  }

  return html;
}

/**
 * 根据文件扩展名提供文件大小提示
 * @param {string} filename - 文件名
 * @returns {string} - 文件大小提示
 */
export function getFileSizeInfo(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  const sizeHints = {
    'pdf': 'PDF文档',
    'doc': 'Word文档',
    'docx': 'Word文档',
    'md': 'Markdown文档',
    'txt': '文本文件'
  };
  return sizeHints[ext] || '';
}

export default {
  formatResult,
  formatText,
  formatObject,
  extractFilePaths,
  getFileSizeInfo
};
