$ErrorActionPreference = 'Stop'
$runtime = 'C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { throw '找不到本机 Python 环境' }
$listener = Get-NetTCPConnection -LocalPort 8792 -State Listen -ErrorAction SilentlyContinue
if (-not $listener) {
  Start-Process -FilePath $runtime -ArgumentList 'local_pool_bridge.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot '.local-pool-service.out.log') -RedirectStandardError (Join-Path $PSScriptRoot '.local-pool-service.err.log')
}
Start-Process 'http://127.0.0.1:8792/'
