# syntax=docker/dockerfile:1
# 电商价格采集工具 - Docker 部署镜像
# 项目零第三方依赖（纯 Python 标准库），镜像极简
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8765

WORKDIR /app

# 项目本身零依赖；保留 requirements.txt 以便未来扩展第三方库
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8765

# 健康检查：容器内调用 /api/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=3).status == 200 else 1)"

# 默认启动网页服务（浏览器访问 http://127.0.0.1:8765）
CMD ["python", "server.py"]
