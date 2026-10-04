$ErrorActionPreference = 'Stop'
$runtime = 'C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { throw '找不到本机 Python 环境' }
# 回环请求（127.0.0.1:8790 号池）绝不能被代理劫持，否则 502 "upstream connect failed"，
# 前端永远停在 queued —— 桥接里 pool_api 已写死 trust_env=False 兜住这一条。
#
# 但**不能把代理变量整体清空**：GMI 的成图/素材直链在 storage.googleapis.com 上，
# 实测直连 21 秒超时（000），必须走代理才通（12000 内核 0.4 秒 200）。
# 桥接的 cache_media()/upload() 会按候选列表试代理，最后回落到 127.0.0.1:12000。
# 这里显式给出出口，省得依赖调用方环境。
# 只设大写键：.NET 监督器(dola.exe) 的环境字典大小写不敏感，
# 同时存在 HTTP_PROXY 和 http_proxy 会让它起不来子进程。
Remove-Item Env:http_proxy,Env:https_proxy,Env:all_proxy,Env:no_proxy -ErrorAction SilentlyContinue
$env:HTTP_PROXY = 'http://127.0.0.1:12000'
$env:HTTPS_PROXY = 'http://127.0.0.1:12000'
$env:NO_PROXY = '127.0.0.1,localhost'
$env:FENGYE_MEDIA_PROXY = 'http://127.0.0.1:12000'
$listener = Get-NetTCPConnection -LocalPort 8793 -State Listen -ErrorAction SilentlyContinue
if (-not $listener) {
  Start-Process -FilePath $runtime -ArgumentList 'local_pool_bridge.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot '.local-pool-service.out.log') -RedirectStandardError (Join-Path $PSScriptRoot '.local-pool-service.err.log')
}
Start-Process 'http://127.0.0.1:8793/'
