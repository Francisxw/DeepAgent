/**
 * Sidebar - 侧边栏组件
 * 负责侧边栏的展开/收起和导航
 */

import Store from '../core/Store.js';

// 侧边栏状态
const sidebarStore = new Store({
  collapsed: false,
  activePage: 'home'
});

/**
 * Sidebar 类
 */
class Sidebar {
  constructor() {
    this.sidebar = null;
    this.sidebarToggle = null;
    this.userProfileTrigger = null;
    this.navItems = null;
    this.backToHomeBtn = null;
    this.logoutBtn = null;
    
    console.log('[Sidebar] 初始化');
  }

  /**
   * 初始化侧边栏
   */
  init() {
    console.log('[Sidebar] 初始化侧边栏...');

    this.sidebar = document.getElementById('sidebar');
    this.sidebarToggle = document.getElementById('sidebar-toggle');
    this.userProfileTrigger = document.getElementById('user-profile-trigger');
    this.navItems = document.querySelectorAll('.sidebar-nav-item');
    this.backToHomeBtn = document.getElementById('back-to-home');
    this.logoutBtn = document.getElementById('logout-btn');

    console.log('[Sidebar] 侧边栏元素:', this.sidebar);
    console.log('[Sidebar] 切换按钮:', this.sidebarToggle);
    console.log('[Sidebar] 导航项数量:', this.navItems.length);

    this.bindEvents();
    console.log('[Sidebar] 初始化完成');
  }

  /**
   * 绑定事件
   */
  bindEvents() {
    // 侧边栏切换
    if (this.sidebarToggle && this.sidebar) {
      this.sidebarToggle.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.toggle();
      });
      console.log('[Sidebar] 侧边栏切换事件已绑定');
    }

    // 导航项点击
    this.navItems.forEach((item, index) => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const page = item.dataset.page;
        this.setActive(page);
        this.switchPage(page);
      });
    });
    console.log(`[Sidebar] 共绑定了 ${this.navItems.length} 个导航项`);

    // 用户卡片点击
    if (this.userProfileTrigger) {
      this.userProfileTrigger.addEventListener('click', () => {
        this.setActive('profile');
        this.switchPage('profile');
      });
    }

    // 返回主页
    if (this.backToHomeBtn) {
      this.backToHomeBtn.addEventListener('click', () => {
        this.setActive('home');
        this.switchPage('home');
      });
    }

    // 退出登录
    if (this.logoutBtn) {
      this.logoutBtn.addEventListener('click', async () => {
        if (confirm('确定要退出登录吗？')) {
          // 触发登出事件，由 Auth 模块处理
          window.dispatchEvent(new CustomEvent('auth:logout'));
        }
      });
    }
  }

  /**
   * 切换侧边栏展开/收起
   */
  toggle() {
    if (!this.sidebar) return;

    this.sidebar.classList.toggle('collapsed');
    const isCollapsed = this.sidebar.classList.contains('collapsed');
    
    // 更新切换按钮文本
    if (this.sidebarToggle) {
      this.sidebarToggle.textContent = isCollapsed ? '▶' : '◀';
    }

    // 更新状态
    sidebarStore.state.collapsed = isCollapsed;
    console.log('[Sidebar] 状态:', isCollapsed ? '已收起' : '已展开');
  }

  /**
   * 设置当前活动页面
   * @param {string} page - 页面名称
   */
  setActive(page) {
    this.navItems.forEach(nav => {
      nav.classList.remove('active');
      if (nav.dataset.page === page) {
        nav.classList.add('active');
      }
    });
    
    sidebarStore.state.activePage = page;
    console.log('[Sidebar] 活动页面:', page);
  }

  /**
   * 切换页面
   * @param {string} page - 页面名称
   */
  switchPage(page) {
    console.log('[Sidebar] 切换页面:', page);

    const homePage = document.getElementById('home-page');
    const profilePage = document.getElementById('profile-page');

    if (!homePage || !profilePage) {
      console.error('[Sidebar] 页面元素未找到');
      return;
    }

    if (page === 'home') {
      homePage.style.display = 'block';
      profilePage.style.display = 'none';
    } else if (page === 'profile') {
      homePage.style.display = 'none';
      profilePage.style.display = 'block';
      // 触发加载用户信息事件
      window.dispatchEvent(new CustomEvent('sidebar:loadProfile'));
    }
  }
}

// 创建单例
const sidebar = new Sidebar();

/**
 * 初始化侧边栏
 */
export function initSidebar() {
  sidebar.init();
}

/**
 * 切换侧边栏
 */
export function toggleSidebar() {
  sidebar.toggle();
}

/**
 * 设置活动页面
 * @param {string} page - 页面名称
 */
export function setActivePage(page) {
  sidebar.setActive(page);
}

/**
 * 获取侧边栏状态
 * @returns {Object} 状态快照
 */
export function getSidebarState() {
  return sidebarStore.getState();
}

/**
 * 订阅侧边栏状态变化
 * @param {Function} callback - 回调函数
 * @returns {Function} 取消订阅函数
 */
export function subscribeSidebar(callback) {
  return sidebarStore.subscribeAll(callback);
}

export default {
  initSidebar,
  toggleSidebar,
  setActivePage,
  getSidebarState,
  subscribeSidebar,
  Sidebar
};
