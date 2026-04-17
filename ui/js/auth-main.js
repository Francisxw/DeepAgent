/**
 * Auth Page Entry Point
 * 认证页面 ES6 模块入口
 */

import Auth from './services/Auth.js';
import { showToast } from './utils/toast.js';
import { qs, on, addClass, removeClass } from './utils/dom.js';

// Auth 模块 default export 已经是一个组装好的对象（含所有方法），
// 无需也不能 new；同时解构导入 sendVerificationCode 命名导出。
const auth = Auth;

// 如果已登录，重定向到主页
if (auth.isLoggedIn()) {
  window.location.href = '/ui/index.html';
}

/**
 * 标签页切换
 */
function initTabs() {
  const loginTab = qs('[data-tab="login"]');
  const registerTab = qs('[data-tab="register"]');
  const loginForm = qs('#login-form');
  const registerForm = qs('#register-form');
  
  if (!loginTab || !registerTab) return;
  
  on(loginTab, 'click', () => {
    addClass(loginTab, 'active');
    removeClass(registerTab, 'active');
    loginForm.style.display = 'block';
    registerForm.style.display = 'none';
  });
  
  on(registerTab, 'click', () => {
    addClass(registerTab, 'active');
    removeClass(loginTab, 'active');
    loginForm.style.display = 'none';
    registerForm.style.display = 'block';
  });
}

/**
 * 密码登录
 */
async function handlePasswordLogin(e) {
  e.preventDefault();
  
  const email = qs('#login-email').value.trim();
  const password = qs('#login-password').value;
  
  if (!email || !password) {
    showError('请填写完整的登录信息');
    return;
  }
  
  try {
    const result = await auth.login(email, password);
    if (result.success) {
      showToast('登录成功', 'success');
      setTimeout(() => {
        window.location.href = '/ui/index.html';
      }, 1000);
    } else {
      showError(result.message || '登录失败');
    }
  } catch (error) {
    showError(error.message || '登录失败');
  }
}

/**
 * 验证码登录
 */
async function handleCodeLogin(e) {
  e.preventDefault();
  
  const email = qs('#login-code-email').value.trim();
  const code = qs('#verification-code-input').value.trim();
  
  if (!email || !code) {
    showError('请填写完整的登录信息');
    return;
  }
  
  try {
    const result = await auth.loginWithCode(email, code);
    if (result.success) {
      showToast('登录成功', 'success');
      setTimeout(() => {
        window.location.href = '/ui/index.html';
      }, 1000);
    } else {
      showError(result.message || '登录失败');
    }
  } catch (error) {
    showError(error.message || '登录失败');
  }
}

/**
 * 发送验证码
 */
async function handleSendCode() {
  const email = qs('#login-code-email').value.trim();
  
  if (!email) {
    showError('请输入邮箱地址');
    return;
  }
  
  try {
    const result = await auth.sendVerificationCode(email);
    if (result.success) {
      showToast('验证码已发送', 'success');
      // 仅调试模式（后端返回 code 字段）时弹窗显示
      if (result.code) {
        showVerificationCode(result.code);
      }
    } else {
      showError(result.message || '发送验证码失败');
    }
  } catch (error) {
    showError(error.message || '发送验证码失败');
  }
}

/**
 * 显示验证码弹窗
 */
function showVerificationCode(code) {
  const popup = document.createElement('div');
  popup.className = 'verification-popup';
  popup.innerHTML = `
    <div class="verification-content">
      <h3>验证码</h3>
      <div class="verification-code">${code}</div>
      <p>验证码有效期为 5 分钟</p>
      <button type="button" class="btn-primary close-popup">关闭</button>
    </div>
  `;
  document.body.appendChild(popup);
  
  on(qs('.close-popup'), 'click', () => {
    popup.remove();
  });
}

/**
 * 注册
 */
async function handleRegister(e) {
  e.preventDefault();
  
  const email = qs('#register-email').value.trim();
  const password = qs('#register-password').value;
  const confirmPassword = qs('#register-confirm-password').value;
  const name = qs('#register-name')?.value.trim() || '';
  
  if (!email || !password) {
    showError('请填写邮箱和密码');
    return;
  }
  
  if (password !== confirmPassword) {
    showError('两次输入的密码不一致');
    return;
  }
  
  try {
    const result = await auth.register({ email, password, name });
    if (result.success) {
      showToast('注册成功，请登录', 'success');
      // 切换到登录标签
      qs('[data-tab="login"]').click();
    } else {
      showError(result.message || '注册失败');
    }
  } catch (error) {
    showError(error.message || '注册失败');
  }
}

/**
 * 显示错误消息
 */
function showError(message) {
  const errorEl = qs('#error-message');
  if (errorEl) {
    errorEl.textContent = message;
    errorEl.classList.add('show');
    setTimeout(() => {
      errorEl.classList.remove('show');
    }, 3000);
  }
}

/**
 * 初始化
 */
document.addEventListener('DOMContentLoaded', () => {
  console.log('[Auth Page] 初始化');
  
  // 初始化标签页
  initTabs();
  
  // 绑定表单事件
  const passwordLoginForm = qs('#password-login-form');
  const codeLoginForm = qs('#code-login-form');
  const registerForm = qs('#register-form-element');
  const sendCodeBtn = qs('#send-code-btn');
  
  if (passwordLoginForm) {
    on(passwordLoginForm, 'submit', handlePasswordLogin);
  }
  
  if (codeLoginForm) {
    on(codeLoginForm, 'submit', handleCodeLogin);
  }
  
  if (registerForm) {
    on(registerForm, 'submit', handleRegister);
  }
  
  if (sendCodeBtn) {
    on(sendCodeBtn, 'click', handleSendCode);
  }
});

// 导出给全局使用（兼容性）
window.authModule = {
  auth,
  showToast,
  showError
};
