/**
 * DeepSearchAgent 配置文件
 * 统一管理所有配置常量
 */

const config = {
  // API 基础配置
  API_BASE_URL: 'http://127.0.0.1:8088',
  WS_BASE_URL: 'ws://127.0.0.1:8088/ws',
  
  // 文件上传配置
  MAX_FILE_SIZE: 50 * 1024 * 1024, // 50MB
  
  // Token 存储键
  TOKEN_KEY: 'access_token',
  REFRESH_TOKEN_KEY: 'refresh_token',
  
  // JWT 配置
  JWT_ALGORITHM: 'HS256',
  ACCESS_TOKEN_EXPIRE_MINUTES: 30,
  REFRESH_TOKEN_EXPIRE_MINUTES: 10080, // 7天
  
  // 调试模式
  DEBUG: false, // 生产环境设为 false
  
  // WebSocket 重连配置
  WS_MAX_RECONNECT_ATTEMPTS: 5,
  WS_RECONNECT_DELAY: 2000, // 初始重连延迟（毫秒）
  WS_MAX_RECONNECT_DELAY: 10000, // 最大重连延迟
  
  // 用户界面配置
  HISTORY_MAX_ITEMS: 20, // 历史记录最大条数
  TOAST_DURATION: 3000, // Toast 显示时长（毫秒）
};

export default config;
