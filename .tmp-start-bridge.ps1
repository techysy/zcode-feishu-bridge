$root = 'F:\Files\GitHub Files\zcode-feishu-bridge'
$py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = 'python.exe' }
Write-Host "interpreter: $py"
Write-Host "env check: APP_ID=$env:FEISHU_APP_ID CHAT=$env:FEISHU_NOTIFY_CHAT_ID"
Start-Process -FilePath $py -ArgumentList 'bridge.py' -WorkingDirectory $root -WindowStyle Hidden
Start-Sleep -Seconds 6

Write-Host '--- pidfile ---'
Get-Content (Join-Path $root 'bridge.pid')

Write-Host '--- python procs ---'
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
  Select-Object ProcessId, Name, @{N='Cmd';E={$_.CommandLine}} | Format-List

Write-Host '--- log tail ---'
Get-Content (Join-Path $root 'bridge.log') -Tail 6

Write-Host '--- heartbeat age (s) ---'
$hb = Get-Item (Join-Path $root 'bridge.heartbeat')
Write-Host ([math]::Round(((Get-Date) - $hb.LastWriteTime).TotalSeconds, 1))
