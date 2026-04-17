/**
 * App - 主应用控制器
 * 负责协调所有组件和服务，管理全局状态
 */

import Store from './Store.js';
import { logger } from '../utils/logger.js';
import config from '../config.js';

// 导入组件
import { initSidebar } from '../components/Sidebar.js';
import { initFileManager, uploadFiles, getFiles, clearSelectedFiles } from '../components/FileManager.js';
import { addProgressItem, clearProgress } from '../components/ProgressDisplay.js';
import { formatResult } from '../components/ResultFormatter.js';

// 导入服务
import { isLoggedIn, getCurrentUser, logout, getAuthHeaders } from '../services/Auth.js';
import { searchTask, checkServerStatus } from '../services/Api.js';
import { WebSocketManager, wsManager } from '../services/WebSocketManager.js';

// 应用状态 Store
const appStore = new Store({
  threadId: null,
  isLoading: false,
  currentQuery: '',
  user: null
});

/**
 * App 类 - 主应用控制器
 */
class App {
  constructor() {
    // DOM 元素引用
    this.queryInput = null;
    this.submitBtn = null;
    this.resultSection = null;
    this.resultContent = null;
    this.progressSection = null;
    this.progressContent = null;
    this.statusIndicator = null;
    this.connectionStatus = null;

    logger.log('[App] 类初始化');
  }

  /**
   * 初始化应用
   */
  init() {
    logger.group('DeepSearchAgent 应用初始化');
    logger.log('API_BASE_URL:', config.API_BASE_URL);
    logger.log('当前页面 URL:', window.location.href);

    // 缓存 DOM 元素
    this.cacheElements();

    // 如果元素不存在，说明 DOM 还没完全加载
    if (!this.queryInput) {
      logger.error('DOM 元素未找到，等待 DOMContentLoaded');
      return;
    }

    // 初始化组件
    this.initComponents();

    // 初始化 WebSocket 监听器
    this.initWebSocketListeners();

    // 绑定事件
    this.bindEvents();

    // 检查服务器状态
    this.checkServerStatus();

    // 加载用户信息
    this.loadUserInfo();

    logger.groupEnd();
  }

  /**
   * 缓存 DOM 元素
   */
  cacheElements() {
    this.queryInput = document.getElementById('query-input');
    this.submitBtn = document.getElementById('submit-btn');
    this.resultSection = document.getElementById('result-section');
    this.resultContent = document.getElementById('result-content');
    this.progressSection = document.getElementById('progress-section');
    this.progressContent = document.getElementById('progress-content');
    this.statusIndicator = document.getElementById('status-indicator');
    this.connectionStatus = document.getElementById('connection-status');

    logger.log('[App] DOM 元素缓存完成');
  }

  /**
   * 初始化组件
   */
  initComponents() {
    // 初始化侧边栏
    initSidebar();

    // 初始化文件管理器
    initFileManager();

    // 监听文件管理器事件
    window.addEventListener('filemanager:toast', (e) => {
      this.showToast(e.detail.message, e.detail.type);
    });

    // 监听侧边栏事件
    window.addEventListener('sidebar:loadProfile', () => {
      this.loadUserInfo();
    });

    // 监听登出事件
    window.addEventListener('auth:logout', async () => {
      await this.handleLogout();
    });

    logger.log('[App] 组件初始化完成');
  }

  /**
   * 初始化 WebSocket 监听器
   */
  initWebSocketListeners() {
    logger.log('[App] 初始化 WebSocket 监听器');

    // 连接事件
    wsManager.on('connected', () => {
      logger.log('[App] WebSocket 连接成功');
    });

    // 消息事件
    wsManager.on('message', (data) => {
      logger.log('[App] 收到 WebSocket 消息:', data);
      this.handleWebSocketMessage(data);
    });

    // 错误事件
    wsManager.on('error', (error) => {
      logger.error('[App] WebSocket 错误:', error);
      this.showToast('连接错误，请检查后端服务', 'error');
    });

    // 断开事件
    wsManager.on('disconnected', (event) => {
      logger.log('[App] WebSocket 断开:', event);
    });
  }

  /**
   * 绑定 DOM 事件
   */
  bindEvents() {
    logger.log('[App] 绑定 DOM 事件');

    // 提交按钮
    if (this.submitBtn) {
      this.submitBtn.addEventListener('click', () => this.handleSubmit());
    }

    // 输入框快捷键（Ctrl+Enter）
    if (this.queryInput) {
      this.queryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
          e.preventDefault();
          this.handleSubmit();
        }
      });
    }

    logger.log('[App] DOM 事件绑定完成');
  }

  /**
   * 处理搜索提交
   */
  async handleSubmit() {
    const query = this.queryInput.value.trim();

    if (!query) {
      this.showToast('请输入搜索内容', 'warning');
      return;
    }

    if (appStore.state.isLoading) {
      logger.log('[App] 正在加载中，忽略重复提交');
      return;
    }

    appStore.state.currentQuery = query;
    await this.executeSearch(query);
  }

  /**
   * 执行搜索
   * @param {string} query - 搜索查询
   */
  async executeSearch(query) {
    logger.group('执行搜索');
    logger.log('查询内容:', query);

    appStore.state.isLoading = true;
    this.setLoading(true);

    // 清空之前的结果
    this.clearResults();

    // 显示进度区域
    if (this.progressSection) {
      this.progressSection.style.display = 'block';
    }

    // 添加初始进度项
    addProgressItem('start', '🚀', `开始搜索: ${query.substring(0, 50)}${query.length > 50 ? '...' : ''}`);

    // 如果有文件，先上传文件
    let threadId = null;
    const files = getFiles();
    
    if (files.length > 0) {
      try {
        addProgressItem('info', '📤', `正在上传 ${files.length} 个文件...`);
        this.showToast('正在上传文件...', 'info');

        threadId = await uploadFiles(appStore.state.threadId);

        if (threadId) {
          addProgressItem('success', '✅', '文件上传成功');
          this.showToast('文件上传成功', 'success');
        }
      } catch (error) {
        logger.error('[App] 文件上传失败:', error);
        addProgressItem('error', '❌', `文件上传失败: ${error.message}`);
        this.showToast(`文件上传失败: ${error.message}`, 'error');
        appStore.state.isLoading = false;
        this.setLoading(false);
        return;
      }
    }

    try {
      logger.log('[App] 发送搜索请求...');
      
      const result = await searchTask(query, threadId || appStore.state.threadId);
      logger.log('[App] API 响应:', result);

      if (result.thread_id) {
        appStore.state.threadId = result.thread_id;
        addProgressItem('session', '📁', '会话已创建');

        // 连接 WebSocket
        logger.log('[App] 连接 WebSocket, thread_id:', result.thread_id);
        wsManager.connect(result.thread_id);
      }

      // 保存历史
      this.saveHistory(query);

    } catch (error) {
      logger.error('[App] 搜索失败:', error);
      addProgressItem('error', '❌', `搜索失败: ${error.message}`);
      this.showToast(`搜索失败: ${error.message}`, 'error');
    } finally {
      appStore.state.isLoading = false;
      this.setLoading(false);
      logger.groupEnd();
    }
  }

  /**
   * 处理 WebSocket 消息
   * @param {Object} data - 消息数据
   */
  handleWebSocketMessage(data) {
    logger.log('[App] 处理 WebSocket 消息:', data);

    // 处理 monitor_event 格式
    if (data.type === 'monitor_event') {
      const eventType = data.event;
      const message = data.message || '';
      const eventData = data.data || {};

      logger.log(`[App] Monitor 事件: ${eventType}`, eventData);

      switch (eventType) {
        case 'session_created': {
          appStore.state.threadId = eventData.thread_id || appStore.state.threadId;
          addProgressItem('session', '📁', message || '会话已创建');
          break;
        }

        case 'assistant_call': {
          const assistantName = eventData.assistant_name || '未知助手';
          addProgressItem('assistant', '🤖', `调用助手: ${assistantName}`);
          this.showToast(`正在调用: ${assistantName}`, 'info');
          break;
        }

        case 'tool_start': {
          const toolName = eventData.tool_name || '未知工具';
          addProgressItem('tool', '🔧', `执行工具: ${toolName}`);
          this.showToast(`执行工具: ${toolName}`, 'info');
          break;
        }

        case 'task_result': {
          addProgressItem('result', '✅', message || '任务执行完成', true);
          const result = eventData.result || data.result;
          logger.log('[App] 任务结果:', result);
          this.showResult(result);
          break;
        }

        default: {
          logger.log('[App] 未知事件类型:', eventType);
          addProgressItem('info', 'ℹ️', message || eventType);
        }
      }
      return;
    }

    // 处理其他消息类型（向后兼容）
    switch (data.type) {
      case 'session_created':
        appStore.state.threadId = data.thread_id;
        addProgressItem('session', '📁', '会话已创建');
        break;

      case 'assistant_call':
        addProgressItem('assistant', '🤖', `调用助手: ${data.assistant}`);
        this.showToast(`正在调用: ${data.assistant}`, 'info');
        break;

      case 'tool_start':
        addProgressItem('tool', '🔧', `执行工具: ${data.tool}`);
        this.showToast(`执行工具: ${data.tool}`, 'info');
        break;

      case 'task_result':
        addProgressItem('result', '✅', '任务执行完成', true);
        logger.log('[App] 任务结果:', data.result);
        this.showResult(data.result || data);
        break;

      case 'error':
        addProgressItem('error', '❌', data.message || '发生错误');
        logger.error('[App] 错误:', data.message);
        this.showToast(`错误: ${data.message}`, 'error');
        break;

      case 'pong':
        logger.log('[App] 收到心跳');
        break;

      default:
        logger.log('[App] 未知消息类型:', data.type);
        addProgressItem('unknown', '❓', JSON.stringify(data));
    }
  }

  /**
   * 显示搜索结果
   * @param {string|object} result - 结果内容
   */
  showResult(result) {
    if (!this.resultSection || !this.resultContent) return;

    logger.log('[App] 显示结果:', result);
    this.resultSection.style.display = 'block';

    // 使用 ResultFormatter 格式化结果
    const formattedResult = formatResult(result);
    this.resultContent.innerHTML = formattedResult;

    // 滚动到结果区域
    setTimeout(() => {
      this.resultSection.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }

  /**
   * 清空结果
   */
  clearResults() {
    clearProgress();
    
    if (this.resultContent) {
      this.resultContent.innerHTML = '';
    }
    if (this.progressSection) {
      this.progressSection.style.display = 'none';
    }
    if (this.resultSection) {
      this.resultSection.style.display = 'none';
    }
  }

  /**
   * 设置加载状态
   * @param {boolean} loading - 是否加载中
   */
  setLoading(loading) {
    if (this.submitBtn) {
      this.submitBtn.disabled = loading;
      this.submitBtn.textContent = loading ? '搜索中...' : '搜索';
    }
  }

  /**
   * 显示 Toast 提示
   * @param {string} message - 消息内容
   * @param {string} type - 类型 (success, error, warning, info)
   * @param {number} duration - 持续时间（毫秒）
   */
  showToast(message, type = 'info', duration = 3000) {
    // 移除已有的 toast
    const existingToasts = document.querySelectorAll('.toast');
    existingToasts.forEach(toast => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    });

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span class="toast-icon">${this.getToastIcon(type)}</span> ${message}`;
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
   * @param {string} type - 类型
   * @returns {string} - 图标
   */
  getToastIcon(type) {
    const icons = {
      'success': '✅',
      'error': '❌',
      'warning': '⚠️',
      'info': 'ℹ️'
    };
    return icons[type] || 'ℹ️';
  }

  /**
   * 检查服务器状态
   */
  async checkServerStatus() {
    try {
      logger.log('[App] 检查服务器状态...');
      const isOnline = await checkServerStatus();

      if (isOnline && this.statusIndicator && this.connectionStatus) {
        this.statusIndicator.classList.remove('status-disconnected');
        this.statusIndicator.classList.add('status-connected');
        this.connectionStatus.textContent = '服务器在线';
      }
    } catch (error) {
      logger.warn('[App] 服务器状态检查失败:', error);
    }
  }

  /**
   * 保存历史记录
   * @param {string} query - 搜索查询
   */
  saveHistory(query) {
    try {
      const historyKey = 'deepsearch_history';
      let history = localStorage.getItem(historyKey);
      const queries = history ? JSON.parse(history) : [];

      // 移除重复，保留最近条数
      const uniqueQueries = [...new Set([query, ...queries])].slice(0, config.HISTORY_MAX_ITEMS);

      localStorage.setItem(historyKey, JSON.stringify(uniqueQueries));
      logger.log('[App] 历史记录已保存，共', uniqueQueries.length, '条');
    } catch (e) {
      logger.error('[App] 保存历史失败:', e);
    }
  }

  /**
   * 加载用户信息
   */
  async loadUserInfo() {
    try {
      const result = await getCurrentUser();
      
      if (result.success && result.user) {
        appStore.state.user = result.user;
        this.updateUserInfo(result.user);
      } else {
        // 获取用户信息失败，可能 token 过期
        logger.error('[App] 获取用户信息失败');
        this.handleLogout();
      }
    } catch (error) {
      logger.error('[App] 加载用户信息失败:', error);
    }
  }

  /**
   * 更新用户信息显示
   * @param {Object} userInfo - 用户信息
   */
  updateUserInfo(userInfo) {
    // 更新侧边栏用户信息
    const sidebarUserName = document.getElementById('sidebar-user-name');
    const sidebarUserEmail = document.getElementById('sidebar-user-email');
    const sidebarUserAvatar = document.getElementById('sidebar-user-avatar');

    if (sidebarUserName) {
      sidebarUserName.textContent = userInfo.name || '未设置姓名';
    }
    if (sidebarUserEmail) {
      sidebarUserEmail.textContent = userInfo.email || '';
    }
    if (sidebarUserAvatar && userInfo.avatar) {
      sidebarUserAvatar.src = userInfo.avatar;
    }

    // 更新个人资料页面信息
    const profileName = document.getElementById('profile-name');
    const profileEmail = document.getElementById('profile-email');
    const profileEmployeeId = document.getElementById('profile-employee-id');
    const profileDepartment = document.getElementById('profile-department');
    const profilePhone = document.getElementById('profile-phone');
    const profileStatus = document.getElementById('profile-status');
    const profileLastLogin = document.getElementById('profile-last-login');
    const profileRoleBadge = document.getElementById('profile-role-badge');
    const profileAvatar = document.getElementById('profile-avatar');

    if (profileName) {
      profileName.textContent = userInfo.name || '未设置姓名';
    }
    if (profileEmail) {
      profileEmail.textContent = userInfo.email || '-';
    }
    if (profileEmployeeId) {
      profileEmployeeId.textContent = userInfo.employee_id || '-';
    }
    if (profileDepartment) {
      profileDepartment.textContent = userInfo.department || '-';
    }
    if (profilePhone) {
      profilePhone.textContent = userInfo.phone || '-';
    }
    if (profileStatus) {
      profileStatus.textContent = this.getStatusText(userInfo.status);
      profileStatus.className = `status-badge ${userInfo.status}`;
    }
    if (profileLastLogin) {
      profileLastLogin.textContent = this.formatDateTime(userInfo.last_login_at);
    }
    if (profileRoleBadge) {
      profileRoleBadge.textContent = userInfo.is_admin ? '管理员' : '普通用户';
    }
    if (profileAvatar && userInfo.avatar) {
      profileAvatar.src = userInfo.avatar;
    }
  }

  /**
   * 获取状态文本
   * @param {string} status - 状态
   * @returns {string} 状态文本
   */
  getStatusText(status) {
    const statusMap = {
      'active': '正常',
      'locked': '已锁定',
      'disabled': '已禁用',
      'deleted': '已删除'
    };
    return statusMap[status] || status;
  }

  /**
   * 格式化日期时间
   * @param {string} dateTimeStr - 日期时间字符串
   * @returns {string} 格式化后的日期时间
   */
  formatDateTime(dateTimeStr) {
    if (!dateTimeStr) return '-';
    try {
      const date = new Date(dateTimeStr);
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateTimeStr;
    }
  }

  /**
   * 处理登出
   */
  async handleLogout() {
    try {
      await logout();
      this.showToast('退出成功', 'success');
      setTimeout(() => {
        window.location.href = '/ui/auth.html';
      }, 1000);
    } catch (error) {
      logger.error('[App] 退出登录失败:', error);
      this.showToast('退出失败', 'error');
    }
  }
}

// 导出
export { App, appStore };
export default App;
