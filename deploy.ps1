<# 
.SYNOPSIS
    Deploys humidifier driver to Raspberry Pi and runs setup
.DESCRIPTION
    Copies driver files to Pi, installs dependencies, starts pigpiod, runs example
.PARAMETER PiHost
    Pi hostname or IP (default: pi410)
.PARAMETER PiUser
    SSH username (default: pi)
.PARAMETER PiPass
    SSH password (default: raspberry)
.PARAMETER RemotePath
    Target directory on Pi (default: /home/pi/Desktop/humidifier)
.PARAMETER SkipCopy
    Skip file copy, only run remote commands
.PARAMETER SkipSetup
    Skip apt install and pigpiod setup
.PARAMETER DryRun
    Show commands without executing
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

function Invoke-Remote {
    param([string]$Cmd, [switch]$NoExit)
    $ssh = "sshpass -p '$PiPass' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $PiUser@$PiHost"
    $full = "$ssh '$Cmd'"
    if ($DryRun) { Write-Host "DRY-RUN: $full" -ForegroundColor Yellow; return }
    if ($NoExit) { iex $full } else { iex "$full 2>&1" }
}

function Copy-Files {
    $scp = "sshpass -p '$PiPass' scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r"
    $cmds = @(
        "$scp '$LocalRoot\driver' $PiUser@${PiHost}:$RemotePath/",
        "$scp '$LocalRoot\example_usage.py' $PiUser@${PiHost}:$RemotePath/"
    )
    foreach ($c in $cmds) {
        if ($DryRun) { Write-Host "DRY-RUN: $c" -ForegroundColor Yellow }
        else { iex "$c 2>&1" }
    }
}

# Check sshpass
if (-not (Get-Command sshpass -ErrorAction SilentlyContinue)) {
    Write-Error "sshpass not found. Install: choco install sshpass  OR  scoop install sshpass"
    exit 1
}

Write-Host "=== Deploying to $PiUser@${PiHost}:$RemotePath ===" -ForegroundColor Cyan

if (-not $SkipCopy) {
    Write-Host "Copying files..." -ForegroundColor Green
    Copy-Files
}

if (-not $SkipSetup) {
    Write-Host "Installing dependencies on Pi..." -ForegroundColor Green
    Invoke-Remote "sudo apt update && sudo apt install -y python3-gpiozero python3-pigpio"
    Write-Host "Starting pigpiod..." -ForegroundColor Green
    Invoke-Remote "sudo systemctl enable pigpiod && sudo systemctl start pigpiod"
}

Write-Host "Running example on Pi..." -ForegroundColor Green
Invoke-Remote "cd $RemotePath && python3 example_usage.py" -NoExit

Write-Host "Done." -ForegroundColor Cyan