# 电商价格采集工具 - Docker Desktop 部署脚本
# 用法：powershell -ExecutionPolicy Bypass -File .\deploy.ps1
# 前置条件：Docker Desktop 已安装并启动
$ErrorActionPreference = "Stop"
$Image = "price-collector:1.0.0"
$Container = "price-collector"
$HostPort = 8765

Write-Host "[1/3] 构建镜像 $Image ..."
docker build -t $Image .

# 清理同名旧容器（保留数据卷之外的运行状态由容器重建）
$old = docker ps -a --filter "name=^/$Container$" --format "{{.ID}}"
if ($old) {
    Write-Host "移除旧容器 $Container ..."
    docker rm -f $Container | Out-Null
}

Write-Host "[2/3] 启动容器 $Container (宿主机端口 $HostPort -> 容器 8765) ..."
docker run -d --name $Container --restart unless-stopped -p "${HostPort}:8765" $Image

Write-Host "[3/3] 等待服务就绪 ..."
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:${HostPort}/api/health" -TimeoutSec 2
        if ($r.status -eq "ok") { $ok = $true; break }
    } catch { }
}
if (-not $ok) {
    Write-Host "服务未就绪，查看日志：" -ForegroundColor Red
    docker logs $Container
    exit 1
}

Write-Host "部署成功！" -ForegroundColor Green
Write-Host "  网页演示: http://127.0.0.1:${HostPort}"
Write-Host "  健康检查: http://127.0.0.1:${HostPort}/api/health"
Write-Host "  容器内跑 CLI 示例: docker exec $Container python cli.py search 蓝牙耳机 --source mock"
