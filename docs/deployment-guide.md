# DeepResearchBot 生产部署指南

本文档提供两种生产环境部署方案：Docker Compose（推荐起步）和 Kubernetes（企业级）。

---

## 目录

- [系统架构](#系统架构)
- [依赖服务](#依赖服务)
- [方案一：Docker Compose 部署](#方案一docker-compose-部署推荐起步)
- [方案二：Kubernetes 部署](#方案二kubernetes-部署企业级)
- [监控与运维](#监控与运维)
- [常见问题](#常见问题)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          交互层 (Presentation)                       │
│   ┌──────────────┐    WebSocket     ┌──────────────────────────┐    │
│   │  Vue 前端     │ ◄──────────────► │  FastAPI 后端             │    │
│   │  (HTML/CSS/JS)│  全双工实时推送   │  (异步服务 + JWT 认证)     │    │
│   └──────────────┘                  └──────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                    Agent 任务编排层 (Orchestration)                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  main_agent (主智能体)                                        │    │
│  │  - 任务拆解与资源调度                                         │    │
│  │  - 分派子智能体并行/串行执行                                   │    │
│  └──────────┬──────────┬──────────┬────────────────────────────┘    │
│             │          │          │                                  │
│  ┌──────────▼──┐ ┌─────▼─────┐ ┌──▼──────────────┐                │
│  │ 网络搜索助手 │ │ 数据库查询 │ │ 知识库检索助手    │                │
│  └─────────────┘ └───────────┘ └───────────────────┘                │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                         存储层 (Storage)                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐  │
│  │  Redis         │  │  MongoDB       │  │  MySQL               │  │
│  │  - 会话缓存    │  │  - 对话持久化   │  │  - 业务数据          │  │
│  │  - Token黑名单 │  │  - TTL自动清理  │  │  - 用户认证          │  │
│  └────────────────┘  └────────────────┘  └──────────────────────┘  │
│  ┌──────────────────────┐                                          │
│  │  ChromaDB            │                                          │
│  │  - 本地向量知识库     │                                          │
│  └──────────────────────┘                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 依赖服务

| 服务 | 版本 | 用途 | 端口 |
|------|------|------|------|
| MySQL | 8.0+ | 业务数据 + 用户认证 | 3306 |
| Redis | 7.0+ | 会话缓存 + Token黑名单 + 上下文卸载 | 6379 |
| MongoDB | 6.0+ | 对话历史持久化 | 27017 |
| Python | 3.10+ | 后端运行环境 | - |

---

## 方案一：Docker Compose 部署（推荐起步）

### 1.1 方案概述

**适用场景**：
- 单机服务器部署
- 小型团队（1-10人）
- 快速上线验证

**优势**：
- 部署简单，学习成本低
- 资源占用少
- 易于调试和维护

### 1.2 目录结构

在项目根目录创建 `deploy/` 目录：

```
deploy/
├── docker-compose.yml          # 编排文件
├── Dockerfile                  # 后端镜像构建
├── .env.production             # 生产环境变量
├── nginx/
│   ├── nginx.conf              # Nginx 主配置
│   └── ssl/                    # SSL 证书目录
│       ├── fullchain.pem
│       └── privkey.pem
├── init-db/
│   └── init.sql                # MySQL 初始化脚本
├── scripts/
│   └── init-mongo.js           # MongoDB 初始化脚本
└── redis.conf                  # Redis 配置
```

### 1.3 Dockerfile

创建 `deploy/Dockerfile`：

```dockerfile
# ==============================
# 阶段1: 构建依赖层
# ==============================
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ==============================
# 阶段2: 运行时镜像
# ==============================
FROM python:3.11-slim AS runtime

WORKDIR /app

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制Python包
COPY --from=builder /install /usr/local

# 复制项目代码
COPY . .

# 创建数据和输出目录
RUN mkdir -p /app/data/chroma_db /app/updated

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# 启动命令
CMD ["uvicorn", "api.server:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "info"]
```

### 1.4 docker-compose.yml

创建 `deploy/docker-compose.yml`：

```yaml
version: "3.8"

services:
  # --------------------------------------------------
  # FastAPI 后端应用
  # --------------------------------------------------
  backend:
    build:
      context: ..
      dockerfile: deploy/Dockerfile
    container_name: deepresearch-backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env.production
    environment:
      - MYSQL_HOST=mysql
      - MYSQL_PORT=3306
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - MONGODB_URI=mongodb://mongodb:27017
    volumes:
      - app-updated:/app/updated
      - chroma-data:/app/data/chroma_db
      - app-logs:/app/logs
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
      mongodb:
        condition: service_healthy
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/docs"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # --------------------------------------------------
  # Nginx 反向代理
  # --------------------------------------------------
  nginx:
    image: nginx:1.25-alpine
    container_name: deepresearch-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - app-updated:/usr/share/nginx/outputs:ro
    depends_on:
      - backend
    networks:
      - app-network

  # --------------------------------------------------
  # MySQL 8.0
  # --------------------------------------------------
  mysql:
    image: mysql:8.0
    container_name: deepresearch-mysql
    restart: unless-stopped
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-changeme_root_2024}
      MYSQL_DATABASE: ${MYSQL_DATABASE:-pharma_db}
      MYSQL_USER: ${MYSQL_USER:-appuser}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:-changeme_mysql_2024}
    volumes:
      - mysql-data:/var/lib/mysql
      - ./init-db/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    command: >
      --default-authentication-plugin=caching_sha2_password
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_unicode_ci
      --max-connections=200
      --innodb-buffer-pool-size=256M
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  # --------------------------------------------------
  # Redis 7
  # --------------------------------------------------
  redis:
    image: redis:7-alpine
    container_name: deepresearch-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - redis-data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf:ro
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # --------------------------------------------------
  # MongoDB 6
  # --------------------------------------------------
  mongodb:
    image: mongo:6
    container_name: deepresearch-mongodb
    restart: unless-stopped
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_ROOT_USER:-mongoadmin}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_ROOT_PASSWORD:-changeme_mongo_2024}
      MONGO_INITDB_DATABASE: ${MONGODB_DATABASE:-chat_memory_db}
    volumes:
      - mongo-data:/data/db
      - ./scripts/init-mongo.js:/docker-entrypoint-initdb.d/init-mongo.js:ro
    command: --wiredTigerCacheSizeGB 0.5
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

# ============================================================
# 持久化卷
# ============================================================
volumes:
  mysql-data:
    driver: local
  redis-data:
    driver: local
  mongo-data:
    driver: local
  chroma-data:
    driver: local
  app-updated:
    driver: local
  app-logs:
    driver: local

# ============================================================
# 网络
# ============================================================
networks:
  app-network:
    driver: bridge
```

### 1.5 Nginx 配置

创建 `deploy/nginx/nginx.conf`：

```nginx
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent" '
                    'upstream_addr=$upstream_addr '
                    'request_time=$request_time';

    access_log /var/log/nginx/access.log main;
    error_log  /var/log/nginx/error.log warn;

    sendfile    on;
    tcp_nopush  on;
    tcp_nodelay on;

    keepalive_timeout 65;
    client_max_body_size 50M;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript 
               text/xml application/xml text/javascript;
    gzip_min_length 1000;

    upstream backend {
        server backend:8000;
    }

    # HTTP -> HTTPS 重定向
    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$host$request_uri;
    }

    # HTTPS 主服务
    server {
        listen 443 ssl;
        server_name your-domain.com;

        ssl_certificate     /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        # WebSocket 代理
        location /ws/ {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }

        # API 代理
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 60s;
            proxy_read_timeout 300s;
        }

        # 静态文件
        location /outputs/ {
            alias /usr/share/nginx/outputs/;
            expires 7d;
            add_header Cache-Control "public, immutable";
        }

        # 前端页面
        location / {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

### 1.6 Redis 配置

创建 `deploy/redis.conf`：

```conf
bind 0.0.0.0
protected-mode yes
port 6379

# 持久化
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec

# 内存限制
maxmemory 512mb
maxmemory-policy allkeys-lru
```

### 1.7 MySQL 初始化脚本

创建 `deploy/init-db/init.sql`：

```sql
USE pharma_db;

-- 员工登录信息表
CREATE TABLE IF NOT EXISTS `employee_login_info` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `email` VARCHAR(128) NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `salt` VARCHAR(64) DEFAULT NULL,
    `employee_id` VARCHAR(32) DEFAULT NULL,
    `name` VARCHAR(64) DEFAULT NULL,
    `department` VARCHAR(64) DEFAULT NULL,
    `phone` VARCHAR(20) DEFAULT NULL,
    `avatar` VARCHAR(255) DEFAULT NULL,
    `status` ENUM('active', 'locked', 'disabled', 'deleted') DEFAULT 'active',
    `is_admin` TINYINT(1) DEFAULT 0,
    `failed_login_count` INT UNSIGNED DEFAULT 0,
    `lock_until` DATETIME DEFAULT NULL,
    `last_login_at` DATETIME DEFAULT NULL,
    `last_login_ip` VARCHAR(45) DEFAULT NULL,
    `verification_code` VARCHAR(10) DEFAULT NULL,
    `verification_code_sent_at` DATETIME DEFAULT NULL,
    `email_verified_at` DATETIME DEFAULT NULL,
    `verification_code_failed_count` INT UNSIGNED DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_email` (`email`),
    KEY `idx_status` (`status`),
    KEY `idx_employee_id` (`employee_id`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 1.8 生产环境变量

创建 `deploy/.env.production`：

```env
# ============================================
# LLM 配置
# ============================================
LLM=qwen-max
OPENAI_API_KEY=sk-your-real-api-key-here
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_TEXT_EMBEDDING=text-embedding-v4

# ============================================
# MySQL
# ============================================
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=appuser
MYSQL_PASSWORD=your-mysql-password
MYSQL_DATABASE=pharma_db
MYSQL_ROOT_PASSWORD=your-root-password

# ============================================
# Redis
# ============================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# ============================================
# MongoDB
# ============================================
MONGODB_URI=mongodb://mongoadmin:your-mongo-password@mongodb:27017
MONGODB_DATABASE=chat_memory_db
MONGODB_CHAT_COLLECTION=deepsearch_agent
MONGODB_MEMORY_TTL_DAYS=30
MONGO_ROOT_USER=mongoadmin
MONGO_ROOT_PASSWORD=your-mongo-password

# ============================================
# JWT（生产环境必须更换密钥！）
# ============================================
JWT_SECRET_KEY=generate-a-random-64-char-string-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# ============================================
# 百度搜索
# ============================================
BAIDU_API_KEY=your-baidu-api-key
BAIDU_SECRET_KEY=your-baidu-secret-key

# ============================================
# 邮件服务
# ============================================
SMTP_HOST=smtp.your-company.com
SMTP_PORT=465
SMTP_USER=noreply@your-company.com
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=DeepResearchBot <noreply@your-company.com>
```

### 1.9 部署命令

```bash
# 进入部署目录
cd deploy/

# 生成 JWT 密钥
python -c "import secrets; print(secrets.token_urlsafe(48))"

# 准备 SSL 证书
# Let's Encrypt 方式:
certbot certonly --standalone -d your-domain.com
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/

# 自签名证书（仅测试）:
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem -out nginx/ssl/fullchain.pem

# 构建并启动
docker-compose build --no-cache backend
docker-compose up -d

# 检查状态
docker-compose ps
docker-compose logs -f backend

# 验证服务
curl http://localhost:8000/docs
curl -k https://your-domain.com/

# 常用运维命令
docker-compose restart backend           # 重启后端
docker-compose logs --tail=100 backend   # 查看日志
docker-compose exec mysql mysql -u root -p  # 进入MySQL
docker-compose exec redis redis-cli      # 进入Redis
docker-compose exec mongodb mongosh      # 进入MongoDB

# 数据备份
docker-compose exec mysql mysqldump -u root -p pharma_db > backup_$(date +%Y%m%d).sql

# 停止服务
docker-compose down          # 停止（保留数据）
docker-compose down -v       # 停止并删除数据（危险！）
```

---

## 方案二：Kubernetes 部署（企业级）

### 2.1 方案概述

**适用场景**：
- 多节点集群部署
- 中大型团队（10人+）
- 需要高可用和自动扩缩容

**优势**：
- 高可用性（多副本 + 自动故障恢复）
- 自动扩缩容（HPA）
- 零停机滚动更新
- 统一的配置和密钥管理

### 2.2 目录结构

```
k8s/
├── namespace.yaml
├── configmap.yaml
├── secret.yaml
├── backend/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── hpa.yaml
├── mysql/
│   ├── statefulset.yaml
│   ├── service.yaml
│   └── pvc.yaml
├── redis/
│   ├── statefulset.yaml
│   └── service.yaml
├── mongodb/
│   ├── statefulset.yaml
│   └── service.yaml
├── ingress.yaml
└── Dockerfile
```

### 2.3 核心配置文件

**namespace.yaml**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: deepresearch
  labels:
    app: deepresearch
```

**secret.yaml**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
  namespace: deepresearch
type: Opaque
stringData:
  MYSQL_PASSWORD: "your-mysql-password"
  MYSQL_ROOT_PASSWORD: "your-root-password"
  MONGO_ROOT_PASSWORD: "your-mongo-password"
  JWT_SECRET_KEY: "your-64-char-random-secret"
  OPENAI_API_KEY: "sk-your-api-key"
  BAIDU_API_KEY: "your-baidu-key"
  BAIDU_SECRET_KEY: "your-baidu-secret"
```

**configmap.yaml**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: deepresearch
data:
  LLM: "qwen-max"
  OPENAI_BASE_URL: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  LLM_TEXT_EMBEDDING: "text-embedding-v4"
  MYSQL_HOST: "mysql-0.mysql"
  MYSQL_PORT: "3306"
  MYSQL_USER: "appuser"
  MYSQL_DATABASE: "pharma_db"
  REDIS_HOST: "redis-0.redis"
  REDIS_PORT: "6379"
  MONGODB_URI: "mongodb://mongoadmin:your-mongo-password@mongodb-0.mongodb:27017"
  MONGODB_DATABASE: "chat_memory_db"
  MONGODB_CHAT_COLLECTION: "deepsearch_agent"
  MONGODB_MEMORY_TTL_DAYS: "30"
  JWT_ALGORITHM: "HS256"
  ACCESS_TOKEN_EXPIRE_MINUTES: "30"
  REFRESH_TOKEN_EXPIRE_MINUTES: "10080"
```

**backend/deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: deepresearch
  labels:
    app: backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
        - name: backend
          image: your-registry/deepresearch-backend:latest
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: app-config
            - secretRef:
                name: app-secrets
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 2000m
              memory: 4Gi
          volumeMounts:
            - name: updated-data
              mountPath: /app/updated
            - name: chroma-data
              mountPath: /app/data/chroma_db
          livenessProbe:
            httpGet:
              path: /docs
              port: 8000
            initialDelaySeconds: 60
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /docs
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
      volumes:
        - name: updated-data
          persistentVolumeClaim:
            claimName: backend-updated-pvc
        - name: chroma-data
          persistentVolumeClaim:
            claimName: backend-chroma-pvc
```

**backend/hpa.yaml**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: deepresearch
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

**mysql/statefulset.yaml**
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
  namespace: deepresearch
spec:
  serviceName: mysql
  replicas: 1
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
        - name: mysql
          image: mysql:8.0
          ports:
            - containerPort: 3306
          env:
            - name: MYSQL_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: MYSQL_ROOT_PASSWORD
            - name: MYSQL_DATABASE
              value: pharma_db
            - name: MYSQL_USER
              value: appuser
            - name: MYSQL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: MYSQL_PASSWORD
          volumeMounts:
            - name: mysql-data
              mountPath: /var/lib/mysql
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: 1000m
              memory: 1Gi
  volumeClaimTemplates:
    - metadata:
        name: mysql-data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: standard
        resources:
          requests:
            storage: 20Gi
```

**redis/statefulset.yaml**
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: deepresearch
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          command: ["redis-server", "--appendonly", "yes", "--maxmemory", "512mb"]
          volumeMounts:
            - name: redis-data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: redis-data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: standard
        resources:
          requests:
            storage: 5Gi
```

**mongodb/statefulset.yaml**
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mongodb
  namespace: deepresearch
spec:
  serviceName: mongodb
  replicas: 1
  selector:
    matchLabels:
      app: mongodb
  template:
    metadata:
      labels:
        app: mongodb
    spec:
      containers:
        - name: mongodb
          image: mongo:6
          ports:
            - containerPort: 27017
          env:
            - name: MONGO_INITDB_ROOT_USERNAME
              value: mongoadmin
            - name: MONGO_INITDB_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: MONGO_ROOT_PASSWORD
          volumeMounts:
            - name: mongo-data
              mountPath: /data/db
  volumeClaimTemplates:
    - metadata:
        name: mongo-data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: standard
        resources:
          requests:
            storage: 20Gi
```

**ingress.yaml**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: deepresearch-ingress
  namespace: deepresearch
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/websocket-services: "backend-svc"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - your-domain.com
      secretName: deepresearch-tls
  rules:
    - host: your-domain.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: backend-svc
                port:
                  number: 80
          - path: /ws
            pathType: Prefix
            backend:
              service:
                name: backend-svc
                port:
                  number: 80
          - path: /
            pathType: Prefix
            backend:
              service:
                name: backend-svc
                port:
                  number: 80
```

### 2.4 部署命令

```bash
# 构建并推送镜像
docker build -t your-registry/deepresearch-backend:v1.0.0 -f Dockerfile ..
docker push your-registry/deepresearch-backend:v1.0.0

# 创建命名空间
kubectl apply -f k8s/namespace.yaml

# 部署配置和密钥
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml

# 部署基础设施
kubectl apply -f k8s/mysql/
kubectl apply -f k8s/redis/
kubectl apply -f k8s/mongodb/

# 等待数据库就绪
kubectl rollout status statefulset/mysql -n deepresearch --timeout=120s
kubectl rollout status statefulset/redis -n deepresearch --timeout=60s
kubectl rollout status statefulset/mongodb -n deepresearch --timeout=60s

# 部署后端应用
kubectl apply -f k8s/backend/
kubectl rollout status deployment/backend -n deepresearch --timeout=120s

# 部署 Ingress
kubectl apply -f k8s/ingress.yaml

# 验证
kubectl get all -n deepresearch
kubectl logs -f deployment/backend -n deepresearch
kubectl port-forward svc/backend-svc 8000:80 -n deepresearch
```

### 2.5 日常运维

```bash
# 查看状态
kubectl get pods -n deepresearch -o wide
kubectl top pods -n deepresearch

# 滚动更新
kubectl set image deployment/backend \
  backend=your-registry/deepresearch-backend:v1.1.0 \
  -n deepresearch
kubectl rollout status deployment/backend -n deepresearch

# 回滚
kubectl rollout undo deployment/backend -n deepresearch
kubectl rollout history deployment/backend -n deepresearch

# 扩缩容
kubectl scale deployment backend --replicas=5 -n deepresearch

# 数据备份
kubectl exec mysql-0 -n deepresearch -- \
  mysqldump -u root -p$MYSQL_ROOT_PASSWORD pharma_db > backup.sql

# 进入容器调试
kubectl exec -it deployment/backend -n deepresearch -- /bin/bash
```

---

## 监控与运维

### 日志管理

```bash
# Docker Compose
docker-compose logs -f --tail=100 backend

# Kubernetes
kubectl logs -f deployment/backend -n deepresearch --tail=100
```

### 数据备份

```bash
# MySQL 备份
docker-compose exec mysql mysqldump -u root -p pharma_db > backup_$(date +%Y%m%d).sql

# MongoDB 备份
docker-compose exec mongodb mongodump --db chat_memory_db --out /tmp/backup

# Redis 备份
docker-compose exec redis redis-cli BGSAVE
docker cp deepresearch-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

### 健康检查

```bash
# 检查所有服务状态
docker-compose ps

# 检查后端健康
curl http://localhost:8000/docs

# 检查数据库连接
docker-compose exec mysql mysql -u root -p -e "SELECT 1"
docker-compose exec redis redis-cli ping
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"
```

---

## 常见问题

### Q1: 容器启动失败，日志显示数据库连接错误？

**原因**：数据库容器还未完全启动。

**解决**：
```bash
# 等待数据库健康检查通过
docker-compose ps
# 查看数据库日志
docker-compose logs mysql
# 重启后端
docker-compose restart backend
```

### Q2: WebSocket 连接断开？

**原因**：Nginx 代理超时配置不足。

**解决**：在 `nginx.conf` 中增加超时时间：
```nginx
proxy_read_timeout 86400s;
proxy_send_timeout 86400s;
```

### Q3: 文件上传失败？

**原因**：Nginx 或后端的文件大小限制。

**解决**：
- Nginx: `client_max_body_size 50M;`
- FastAPI: 默认无限制，但需确保磁盘空间充足

### Q4: ChromaDB 数据丢失？

**原因**：未正确挂载持久化卷。

**解决**：确保 `chroma-data` 卷正确挂载到 `/app/data/chroma_db`。

### Q5: JWT Token 验证失败？

**原因**：JWT_SECRET_KEY 在不同环境不一致。

**解决**：确保所有后端实例使用相同的 `JWT_SECRET_KEY`。

---

## 方案对比

| 维度 | Docker Compose | Kubernetes |
|------|----------------|------------|
| 适用规模 | 单机 / 小团队 | 集群 / 中大型团队 |
| 运维复杂度 | 低 | 高 |
| 自动扩缩容 | ❌ 手动 | ✅ HPA 自动 |
| 零停机部署 | ✅ 简单 | ✅ 原生支持 |
| 高可用 | ❌ 单点 | ✅ 多副本 |
| 学习成本 | 1-2天 | 1-2周 |

**建议路径**：先用 Docker Compose 部署上线验证，业务稳定后再迁移到 Kubernetes。
