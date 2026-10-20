param(
    [string]$Target,
    [string]$Arguments = "",
    [string]$WorkDir = "",
    [string]$Icon = "",
    [string]$Folder = "Desktop"   # "Desktop" atau "Startup"
)
$dir = [Environment]::GetFolderPath($Folder)
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path $dir "Halo.lnk"))
$lnk.TargetPath = $Target
$lnk.Arguments = $Arguments
$lnk.WorkingDirectory = $WorkDir
if ($Icon) { $lnk.IconLocation = $Icon }
$lnk.Description = "Halo - Spotify now playing popup"
$lnk.Save()
Write-Host "Shortcut dibuat di: $dir"
