/**
 * main.js - 应用入口点
 * ES6 模块入口，负责初始化应用
 */

import App from './core/App.js';
import { isLoggedIn } from './services/Auth.js';
import { logger } from './utils/logger.js';
import config from './config.js';

/**
 * 初始化应用
 */
function init() {
  logger.group('DeepSearchAgent 应用初始化');
  logger.log('API_BASE_URL:', config.API_BASE_URL);
  logger.log('当前页面 URL:', window.location.href);
  logger.groupEnd();

  // 初始化主应用
  const app = new App();
  app.init();
}

/**
 * 检查登录状态并初始化
 */
function checkAuthAndInit() {
  logger.group('检查登录状态');

  if (!isLoggedIn()) {
    logger.log('未登录，跳转到登录页面');
    window.location.href = '/ui/auth.html';
    return;
  }

  logger.log('用户已登录，初始化应用');
  logger.groupEnd();

  // 初始化应用
  init();
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', checkAuthAndInit);

// 导出（用于调试）
export { init, checkAuthAndInit };
