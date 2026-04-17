/**
 * 日志工具
 * 统一的日志管理，支持 DEBUG 模式
 */

import config from '../config.js';

/**
 * 日志工具对象
 */
export const logger = {
  /**
   * 调试日志（仅 DEBUG 模式）
   */
  log: (...args) => {
    if (config.DEBUG) {
      console.log('[DEBUG]', ...args);
    }
  },
  
  /**
   * 错误日志（始终输出）
   */
  error: (...args) => {
    console.error('[ERROR]', ...args);
  },
  
  /**
   * 警告日志（仅 DEBUG 模式）
   */
  warn: (...args) => {
    if (config.DEBUG) {
      console.warn('[WARN]', ...args);
    }
  },
  
  /**
   * 信息日志（仅 DEBUG 模式）
   */
  info: (...args) => {
    if (config.DEBUG) {
      console.info('[INFO]', ...args);
    }
  },
  
  /**
   * 调试分组开始
   */
  group: (title) => {
    if (config.DEBUG) {
      console.group(title);
    }
  },
  
  /**
   * 调试分组结束
   */
  groupEnd: () => {
    if (config.DEBUG) {
      console.groupEnd();
    }
  },
  
  /**
   * 时间追踪开始
   */
  time: (label) => {
    if (config.DEBUG) {
      console.time(label);
    }
  },
  
  /**
   * 时间追踪结束
   */
  timeEnd: (label) => {
    if (config.DEBUG) {
      console.timeEnd(label);
    }
  }
};

export default logger;
