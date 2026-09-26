<# 
.SYNOPSIS
    Deploys humidifier driver to Raspberry Pi using native .NET SSH (no sshpass needed)
.DESCRIPTION
    Uses Renci.SshNet (via NuGet) for SSH/SCP operations
#>

param(
    [string]$PiHost = "pi410",
    [string]$PiUser = "pi",
    [string]$PiPass = "raspberry",
    [string]$RemotePath = "/home/pi/Desktop/humidifier",
    [switch]$SkipCopy,
    [switch]$SkipSetup,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$LocalRoot = "C:\git_hub\humidifier"

# Load Renci.SshNet from NuGet
$nugetPath = "$env:TEMP\Renci.SshNet.dll"
if (-not (Test-Path $nugetPath)) {
    Write-Host "Downloading Renci.SshNet..." -ForegroundColor Yellow
    $client = New-Object System.Net.WebClient
    $client.DownloadFile("https://www.nuget.org/api/v2/package/Renci.SshNet/2020.0.1", "$env:TEMP\renci.nupkg")
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory("$env:TEMP\renci.nupkg", "$env:TEMP\renci")
    Copy-Item "$env:TEMP\renci\lib\net461\Renci.SshNet.dll" $nugetPath
}
Add-Type -Path $nugetPath

function New-SshClient {
    $conn = New-Object Renci.SshNet.ConnectionInfo($PiHost, $PiUser, 
        (New-Object Renci.SshNet.PasswordAuthenticationMethod($PiUser, $PiPass)),
        (New-Object Renci.SshNet.KeyboardInteractiveAuthenticationMethod($PiUser)))
    $ssh = New-Object Renci.SshNet.SshClient($conn)
    $ssh.Connect()
    return $ssh
}

function New-ScpClient {
    $conn = New-Object Renci.SshNet.ConnectionInfo($PiHost, $PiUser,
        (New-Object Renci.SshNet.PasswordAuthenticationMethod($PiUser, $PiPass)))
    $scp = New-Object Renci.SshNet.ScpClient($conn)
    $scp.Connect()
    return $scp
}

function Invoke-Remote {
    param([string]$Cmd)
    if ($DryRun) { Write-Host "DRY-RUN: ssh $PiUser@$PiHost '$Cmd'" -ForegroundColor Yellow; return }
    $ssh = New-SshClient
    try {
        $result = $ssh.RunCommand($Cmd)
        if ($result.ExitStatus -ne 0) {
            Write-Error "Command failed ($result.ExitStatus): $result.Error"
        }
        Write-Host $result.Result
    } finally {
        $ssh.Disconnect()
    }
}

function Copy-ItemToPi {
    param([string]$LocalPath, [string]$RemotePath)
    if ($DryRun) { Write-Host "DRY-RUN: scp $LocalPath $PiUser@${PiHost}:$RemotePath" -ForegroundColor Yellow; return }
    $scp = New-ScpClient
    try {
        $scp.Upload($LocalPath, $RemotePath)
    } finally {
        $scp.Disconnect()
    }
}

Write-Host "=== Deploying to $PiUser@${PiHost}:$RemotePath ===" -ForegroundColor Cyan

if (-not $SkipCopy) {
    Write-Host "Copying driver/..." -ForegroundColor Green
    $driverDir = "$LocalRoot\driver"
    $files = Get-ChildItem -Recurse -File $driverDir
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($driverDir.Length + 1)
        $remoteFile = "$RemotePath/driver/$rel".Replace('\', '/')
        Write-Host "  $rel"
        Copy-ItemToPi $f.FullName $remoteFile
    }
    Write-Host "Copying example_usage.py..." -ForegroundColor Green
    Copy-ItemToPi "$LocalRoot\example_usage.py" "$RemotePath/example_usage.py"
}

if (-not $SkipSetup) {
    Write-Host "Installing dependencies on Pi..." -ForegroundColor Green
    Invoke-Remote "sudo apt update && sudo apt install -y python3-gpiozero python3-pigpio"
    Write-Host "Starting pigpiod..." -ForegroundColor Green
    Invoke-Remote "sudo systemctl enable pigpiod && sudo systemctl start pigpiod"
}

Write-Host "Running example on Pi..." -ForegroundColor Green
Invoke-Remote "cd $RemotePath && python3 example_usage.py"

Write-Host "Done." -ForegroundColor Cyan