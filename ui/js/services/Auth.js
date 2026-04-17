/**
 * Auth - 认证服务
 * 管理用户登录、注册、登出等认证功能
 */

import Store from '../core/Store.js';
import config from '../config.js';

// 认证状态
const authStore = new Store({
  isLoggedIn: false,
  user: null,
  isLoading: false
});

/**
 * Auth 类
 */
class Auth {
  constructor() {
    // 初始化时检查登录状态
    authStore.state.isLoggedIn = this.isLoggedIn();
    console.log('[Auth] 初始化，登录状态:', authStore.state.isLoggedIn);
  }

  /**
   * 检查是否已登录
   * @returns {boolean}
   */
  isLoggedIn() {
    return !!localStorage.getItem(config.TOKEN_KEY);
  }

  /**
   * 获取当前 Access Token
   * @returns {string|null}
   */
  getAccessToken() {
    return localStorage.getItem(config.TOKEN_KEY);
  }

  /**
   * 获取当前 Refresh Token
   * @returns {string|null}
   */
  getRefreshToken() {
    return localStorage.getItem(config.REFRESH_TOKEN_KEY);
  }

  /**
   * 获取认证请求头
   * @returns {Object} 请求头对象
   */
  getAuthHeaders() {
    const token = this.getAccessToken();
    const headers = {
      'Content-Type': 'application/json'
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  /**
   * 获取 Refresh Token 请求头
   * @returns {Object} 请求头对象
   */
  getRefreshHeaders() {
    const refreshToken = this.getRefreshToken();
    const headers = {
      'Content-Type': 'application/json'
    };
    if (refreshToken) {
      headers['Authorization'] = `Bearer ${refreshToken}`;
    }
    return headers;
  }

  /**
   * 保存 Token
   * @param {string} accessToken - Access Token
   * @param {string} refreshToken - Refresh Token（可选）
   */
  saveToken(accessToken, refreshToken = null) {
    localStorage.setItem(config.TOKEN_KEY, accessToken);
    if (refreshToken) {
      localStorage.setItem(config.REFRESH_TOKEN_KEY, refreshToken);
    }
    authStore.state.isLoggedIn = true;
    console.log('[Auth] Token 已保存');
  }

  /**
   * 清除 Token
   */
  clearTokens() {
    localStorage.removeItem(config.TOKEN_KEY);
    localStorage.removeItem(config.REFRESH_TOKEN_KEY);
    authStore.state.isLoggedIn = false;
    authStore.state.user = null;
    console.log('[Auth] Token 已清除');
  }

  /**
   * 密码登录
   * @param {string} email - 邮箱
   * @param {string} password - 密码
   * @returns {Promise<Object>} 登录结果
   */
  async login(email, password) {
    authStore.state.isLoading = true;

    try {
      const response = await fetch(`${config.API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      const result = await response.json();

      if (result.code === 200 && result.data) {
        this.saveToken(result.data.access_token, result.data.refresh_token);
        authStore.state.user = result.data.user || null;
        return { success: true, data: result.data };
      } else {
        return { success: false, message: result.message || '登录失败' };
      }
    } catch (error) {
      console.error('[Auth] 登录失败:', error);
      return { success: false, message: '登录失败，请稍后重试' };
    } finally {
      authStore.state.isLoading = false;
    }
  }

  /**
   * 验证码登录
   * @param {string} email - 邮箱
   * @param {string} code - 验证码
   * @returns {Promise<Object>} 登录结果
   */
  async loginWithCode(email, code) {
    authStore.state.isLoading = true;

    try {
      const response = await fetch(`${config.API_BASE_URL}/api/auth/login/code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code })
      });

      const result = await response.json();

      if (result.code === 200 && result.data) {
        this.saveToken(result.data.access_token, result.data.refresh_token);
        authStore.state.user = result.data.user || null;
        return { success: true, data: result.data };
      } else {
        return { success: false, message: result.message || '登录失败' };
      }
    } catch (error) {
      console.error('[Auth] 验证码登录失败:', error);
      return { success: false, message: '登录失败，请稍后重试' };
    } finally {
      authStore.state.isLoading = false;
    }
  }

  /**
   * 发送验证码
   * Security: Backend no longer returns verification_code in response.
   * @param {string} email - 邮箱
   * @returns {Promise<Object>} 发送结果
   */
  async sendVerificationCode(email) {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/auth/send-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });

      const result = await response.json();

      if (result.code === 200) {
        // Security: Backend no longer returns verification_code in any mode
        // The code is only sent via email or logged server-side in debug mode
        return {
          success: true,
          message: result.message || '验证码已发送'
        };
      } else {
        return { success: false, message: result.message || '发送验证码失败' };
      }
    } catch (error) {
      console.error('[Auth] 发送验证码失败:', error);
      return { success: false, message: '发送验证码失败，请稍后重试' };
    }
  }

  /**
   * 用户注册
   * @param {Object} userData - 用户数据
   * @returns {Promise<Object>} 注册结果
   */
  async register(userData) {
    authStore.state.isLoading = true;

    try {
      const response = await fetch(`${config.API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
      });

      const result = await response.json();

      if (result.code === 200) {
        return { success: true, message: '注册成功' };
      } else {
        return { success: false, message: result.message || '注册失败' };
      }
    } catch (error) {
      console.error('[Auth] 注册失败:', error);
      return { success: false, message: '注册失败，请稍后重试' };
    } finally {
      authStore.state.isLoading = false;
    }
  }

  /**
   * 登出
   * @returns {Promise<Object>} 登出结果
   */
  async logout() {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/auth/logout`, {
        method: 'POST',
        headers: this.getAuthHeaders()
      });

      // 无论响应如何，都清除本地 Token
      this.clearTokens();

      if (response.ok) {
        return { success: true };
      } else {
        return { success: true }; // 即使服务器失败，本地已清除
      }
    } catch (error) {
      console.error('[Auth] 登出失败:', error);
      this.clearTokens();
      return { success: true };
    }
  }

  /**
   * 刷新 Access Token
   * @returns {Promise<Object>} 刷新结果
   */
  async refreshToken() {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: this.getRefreshHeaders()
      });

      const result = await response.json();

      if (result.code === 200 && result.data) {
        this.saveToken(result.data.access_token, result.data.refresh_token);
        return { success: true };
      } else {
        this.clearTokens();
        return { success: false };
      }
    } catch (error) {
      console.error('[Auth] 刷新 Token 失败:', error);
      this.clearTokens();
      return { success: false };
    }
  }

  /**
   * 获取当前用户信息
   * @returns {Promise<Object>} 用户信息
   */
  async getCurrentUser() {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/auth/me`, {
        method: 'GET',
        headers: this.getAuthHeaders()
      });

      if (response.ok) {
        const userInfo = await response.json();
        authStore.state.user = userInfo;
        return { success: true, user: userInfo };
      } else {
        return { success: false };
      }
    } catch (error) {
      console.error('[Auth] 获取用户信息失败:', error);
      return { success: false };
    }
  }
}

// 创建单例
const auth = new Auth();

// 导出静态方法
export const login = (email, password) => auth.login(email, password);
export const loginWithCode = (email, code) => auth.loginWithCode(email, code);
export const register = (userData) => auth.register(userData);
export const logout = () => auth.logout();
export const getCurrentUser = () => auth.getCurrentUser();
export const isLoggedIn = () => auth.isLoggedIn();
export const sendVerificationCode = (email) => auth.sendVerificationCode(email);
export const refreshToken = () => auth.refreshToken();
export const getAuthHeaders = () => auth.getAuthHeaders();
export const saveToken = (accessToken, refreshToken) => auth.saveToken(accessToken, refreshToken);
export const clearTokens = () => auth.clearTokens();

/**
 * 获取认证状态
 * @returns {Object} 状态快照
 */
export function getAuthState() {
  return authStore.getState();
}

/**
 * 订阅认证状态变化
 * @param {Function} callback - 回调函数
 * @returns {Function} 取消订阅函数
 */
export function subscribeAuth(callback) {
  return authStore.subscribeAll(callback);
}

export default {
  login,
  loginWithCode,
  register,
  logout,
  getCurrentUser,
  isLoggedIn,
  sendVerificationCode,
  refreshToken,
  getAuthHeaders,
  saveToken,
  clearTokens,
  getAuthState,
  subscribeAuth,
  Auth
};
