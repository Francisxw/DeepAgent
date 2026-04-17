/**
 * Store - 响应式状态管理
 * 使用 Proxy + PubSub 模式实现
 */

/**
 * Store 类 - 响应式状态管理器
 */
export class Store {
  /**
   * 创建 Store 实例
   * @param {Object} initialState - 初始状态
   */
  constructor(initialState = {}) {
    // 存储监听器
    this.listeners = new Map();
    
    // 创建响应式状态
    this.state = this._createReactiveState(initialState);
    
    // 历史记录（可选）
    this.history = [];
    this.maxHistoryLength = 10;
  }
  
  /**
   * 创建响应式状态
   * @private
   */
  _createReactiveState(initialState) {
    const self = this;
    
    return new Proxy(initialState, {
      set(target, prop, value) {
        const oldValue = target[prop];
        
        // 设置值
        target[prop] = value;
        
        // 记录历史
        if (self.maxHistoryLength > 0) {
          self.history.push({
            prop,
            oldValue,
            newValue: value,
            timestamp: Date.now()
          });
          
          // 限制历史记录长度
          if (self.history.length > self.maxHistoryLength) {
            self.history.shift();
          }
        }
        
        // 触发监听器
        self._notify(prop, value, oldValue);
        
        return true;
      },
      
      get(target, prop) {
        return target[prop];
      }
    });
  }
  
  /**
   * 订阅状态变化
   * @param {string} key - 状态键名
   * @param {Function} callback - 回调函数 (newValue, oldValue) => void
   * @returns {Function} 取消订阅函数
   */
  subscribe(key, callback) {
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    
    this.listeners.get(key).add(callback);
    
    // 返回取消订阅函数
    return () => {
      const callbacks = this.listeners.get(key);
      if (callbacks) {
        callbacks.delete(callback);
      }
    };
  }
  
  /**
   * 订阅所有状态变化
   * @param {Function} callback - 回调函数 (key, newValue, oldValue) => void
   * @returns {Function} 取消订阅函数
   */
  subscribeAll(callback) {
    return this.subscribe('*', callback);
  }
  
  /**
   * 触发监听器
   * @private
   */
  _notify(key, newValue, oldValue) {
    // 触发特定键的监听器
    const callbacks = this.listeners.get(key);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(newValue, oldValue);
        } catch (error) {
          console.error('[Store] 监听器执行错误:', error);
        }
      });
    }
    
    // 触发全局监听器
    const globalCallbacks = this.listeners.get('*');
    if (globalCallbacks) {
      globalCallbacks.forEach(callback => {
        try {
          callback(key, newValue, oldValue);
        } catch (error) {
          console.error('[Store] 全局监听器执行错误:', error);
        }
      });
    }
  }
  
  /**
   * 获取状态快照
   * @returns {Object} 状态对象的副本
   */
  getState() {
    return { ...this.state };
  }
  
  /**
   * 批量设置状态
   * @param {Object} updates - 要更新的状态键值对
   */
  setState(updates) {
    Object.keys(updates).forEach(key => {
      this.state[key] = updates[key];
    });
  }
  
  /**
   * 重置状态到初始值
   * @param {Object} initialState - 新的初始状态
   */
  reset(initialState) {
    this.listeners.clear();
    this.history = [];
    this.state = this._createReactiveState(initialState);
  }
  
  /**
   * 获取历史记录
   * @returns {Array} 状态变更历史
   */
  getHistory() {
    return [...this.history];
  }
  
  /**
   * 清除所有监听器
   */
  clearListeners() {
    this.listeners.clear();
  }
}

export default Store;
