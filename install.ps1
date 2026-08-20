<#
.SYNOPSIS
    把本 repo 的 Godot Skills 與 Agents 安裝到 Claude Code 設定目錄。

.EXAMPLE
    .\install.ps1
    複製到 ~\.claude\skills 與 ~\.claude\agents

.EXAMPLE
    .\install.ps1 -Link
    改用符號連結（需系統管理員或開發者模式），之後 git pull 即同步

.EXAMPLE
    .\install.ps1 -Target .\myproject
    裝進專案內的 .claude\ 而非使用者家目錄
#>
[CmdletBinding()]
param(
    [switch]$Link,
    [string]$Target,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($Target) {
    $ClaudeDir = Join-Path (Resolve-Path $Target) '.claude'
} else {
    $ClaudeDir = Join-Path $HOME '.claude'
}

$SkillsDir = Join-Path $ClaudeDir 'skills'
$AgentsDir = Join-Path $ClaudeDir 'agents'
New-Item -ItemType Directory -Force -Path $SkillsDir, $AgentsDir | Out-Null

Write-Host "安裝目標：$ClaudeDir" -ForegroundColor Cyan
Write-Host ("模式：" + $(if ($Link) { '符號連結' } else { '複製' })) -ForegroundColor Cyan
Write-Host ''

function Install-Item {
    param([string]$Source, [string]$DestDir, [string]$Kind)

    $name = Split-Path -Leaf $Source
    $dest = Join-Path $DestDir $name

    if (Test-Path $dest) {
        if (-not $Force) {
            Write-Host "  跳過 $name（已存在，用 -Force 覆蓋）" -ForegroundColor Yellow
            return
        }
        Remove-Item $dest -Recurse -Force
    }

    if ($Link) {
        New-Item -ItemType SymbolicLink -Path $dest -Target $Source | Out-Null
        Write-Host "  連結 $name" -ForegroundColor Green
    } else {
        Copy-Item $Source $dest -Recurse
        Write-Host "  複製 $name" -ForegroundColor Green
    }
}

Write-Host 'Skills：'
Get-ChildItem (Join-Path $Root 'skills') -Directory | ForEach-Object {
    Install-Item -Source $_.FullName -DestDir $SkillsDir -Kind 'skill'
}

Write-Host ''
Write-Host 'Agents：'
Get-ChildItem (Join-Path $Root 'agents') -Filter '*.md' -File | ForEach-Object {
    Install-Item -Source $_.FullName -DestDir $AgentsDir -Kind 'agent'
}

Write-Host ''
Write-Host '完成。在 Claude Code 用 /skills 與 /agents 確認載入狀況。' -ForegroundColor Cyan
