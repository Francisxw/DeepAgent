/**
 * DOM 操作工具集
 * 提供常用的 DOM 操作方法
 */

/**
 * querySelector 简写
 * @param {string} selector - CSS 选择器
 * @param {Element} context - 上下文元素，默认为 document
 * @returns {Element|null}
 */
export function qs(selector, context = document) {
  return context.querySelector(selector);
}

/**
 * querySelectorAll 简写
 * @param {string} selector - CSS 选择器
 * @param {Element} context - 上下文元素，默认为 document
 * @returns {NodeList}
 */
export function qsa(selector, context = document) {
  return context.querySelectorAll(selector);
}

/**
 * 添加事件监听器
 * @param {Element|Window|Document} element - 目标元素
 * @param {string} event - 事件名称
 * @param {Function} handler - 事件处理函数
 * @param {Object} options - 事件选项
 * @returns {Function} 移除监听器函数
 */
export function on(element, event, handler, options = {}) {
  element.addEventListener(event, handler, options);
  
  // 返回移除函数
  return () => element.removeEventListener(event, handler, options);
}

/**
 * 添加一次性事件监听器
 * @param {Element} element - 目标元素
 * @param {string} event - 事件名称
 * @param {Function} handler - 事件处理函数
 */
export function once(element, event, handler) {
  element.addEventListener(event, handler, { once: true });
}

/**
 * 添加类名
 * @param {Element} element - 目标元素
 * @param {...string} classNames - 类名列表
 */
export function addClass(element, ...classNames) {
  element.classList.add(...classNames);
}

/**
 * 移除类名
 * @param {Element} element - 目标元素
 * @param {...string} classNames - 类名列表
 */
export function removeClass(element, ...classNames) {
  element.classList.remove(...classNames);
}

/**
 * 切换类名
 * @param {Element} element - 目标元素
 * @param {string} className - 类名
 * @param {boolean} force - 强制添加或移除
 */
export function toggleClass(element, className, force) {
  element.classList.toggle(className, force);
}

/**
 * 检查是否有类名
 * @param {Element} element - 目标元素
 * @param {string} className - 类名
 * @returns {boolean}
 */
export function hasClass(element, className) {
  return element.classList.contains(className);
}

/**
 * 创建元素
 * @param {string} tag - 标签名
 * @param {Object} attrs - 属性对象
 * @param {Array|string} children - 子元素或文本
 * @returns {Element}
 */
export function createElement(tag, attrs = {}, children = []) {
  const element = document.createElement(tag);
  
  // 设置属性
  Object.entries(attrs).forEach(([key, value]) => {
    if (key === 'className') {
      element.className = value;
    } else if (key.startsWith('data')) {
      element.setAttribute(key.replace(/([A-Z])/g, '-$1').toLowerCase(), value);
    } else if (key === 'style' && typeof value === 'object') {
      Object.assign(element.style, value);
    } else {
      element.setAttribute(key, value);
    }
  });
  
  // 添加子元素
  if (Array.isArray(children)) {
    children.forEach(child => {
      if (typeof child === 'string') {
        element.appendChild(document.createTextNode(child));
      } else if (child instanceof Element) {
        element.appendChild(child);
      }
    });
  } else if (typeof children === 'string') {
    element.textContent = children;
  }
  
  return element;
}

/**
 * 移除元素
 * @param {Element} element - 要移除的元素
 */
export function removeElement(element) {
  if (element && element.parentNode) {
    element.parentNode.removeChild(element);
  }
}

/**
 * 清空元素内容
 * @param {Element} element - 目标元素
 */
export function clearElement(element) {
  element.innerHTML = '';
}

/**
 * 设置元素样式
 * @param {Element} element - 目标元素
 * @param {Object} styles - 样式对象
 */
export function setStyles(element, styles) {
  Object.assign(element.style, styles);
}

/**
 * 显示元素
 * @param {Element} element - 目标元素
 * @param {string} display - display 值，默认为 'block'
 */
export function show(element, display = 'block') {
  element.style.display = display;
}

/**
 * 隐藏元素
 * @param {Element} element - 目标元素
 */
export function hide(element) {
  element.style.display = 'none';
}

/**
 * 切换元素显示/隐藏
 * @param {Element} element - 目标元素
 */
export function toggle(element) {
  if (element.style.display === 'none') {
    element.style.display = '';
  } else {
    element.style.display = 'none';
  }
}

export default {
  qs,
  qsa,
  on,
  once,
  addClass,
  removeClass,
  toggleClass,
  hasClass,
  createElement,
  removeElement,
  clearElement,
  setStyles,
  show,
  hide,
  toggle
};
