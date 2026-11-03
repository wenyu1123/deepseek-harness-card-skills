param([string]$Root = $PSScriptRoot, [int]$Index = 0, [switch]$List, [switch]$TextOnly)
$ErrorActionPreference = 'Stop'
$cardDirectory = [IO.Path]::GetFullPath($Root)
$mapping = @(
    @{Label='破甲词 / 沉浸约定';Path='主提示词\01_破甲词_沉浸约定.txt'},
    @{Label='人设与规则';Path='主提示词\02_人设与规则.txt'},
    @{Label='输出格式';Path='主提示词\03_输出格式.txt'},
    @{Label='内置CSS';Path='主提示词\04_内置CSS.css'},
    @{Label='前置提示词';Path='主提示词\05_前置提示词.txt'},
    @{Label='后置提示词';Path='主提示词\06_后置提示词.txt'},
    @{Label='引导页 HTML / 完整代码';Path='引导页\引导页_直接粘贴.txt'}
)
if ($List) { for ($i=0; $i -lt $mapping.Count; $i++) { Write-Output ('{0}. {1}' -f ($i+1),$mapping[$i].Label) }; return }
if ($Index -eq 0) {
    for ($i=0; $i -lt $mapping.Count; $i++) { Write-Host ('{0}. {1}' -f ($i+1),$mapping[$i].Label) }
    $answer = Read-Host '输入要复制的编号'
    if (-not [int]::TryParse($answer,[ref]$Index)) { throw '请输入数字。' }
}
if ($Index -lt 1 -or $Index -gt $mapping.Count) { throw '编号超出范围。' }
$selectedPath = $mapping[$Index-1].Path
if ($Index -eq 7 -and -not (Test-Path -LiteralPath (Join-Path $cardDirectory $selectedPath) -PathType Leaf)) {
    foreach ($legacy in @('引导页\引导页_本地预览.html','引导页\引导页.html')) {
        if (Test-Path -LiteralPath (Join-Path $cardDirectory $legacy) -PathType Leaf) { $selectedPath = $legacy; break }
    }
}
if ($Index -eq 7 -and -not $TextOnly) { Write-Host '复制的是完整HTML代码；请查看填写说明中的平台保存验证结果。' }
$target = [IO.Path]::GetFullPath((Join-Path $cardDirectory $selectedPath))
if (-not $target.StartsWith($cardDirectory.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw '文件路径越界。' }
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw ('找不到文件：'+$target) }
$content = [IO.File]::ReadAllText($target,[Text.Encoding]::UTF8)
if ([string]::IsNullOrWhiteSpace($content)) { throw '文件为空，未复制。' }
if ($Index -eq 7) {
    $isJson = $false
    try { $null = ConvertFrom-Json -InputObject $content -ErrorAction Stop; $isJson = $true } catch {}
    if ($isJson -or $content.TrimStart().StartsWith('```') -or $content -notmatch '(?is)<(?:section|div|main)\b') {
        throw '引导页不是完整HTML代码，不能复制JSON配置或Markdown代码围栏。请先生成引导页成品。'
    }
}
if ($TextOnly) { Write-Output $content; return }
Set-Clipboard -Value $content
Write-Host ('已复制完整{0}，共{1}个字符。请粘贴到春水对应栏位。' -f $mapping[$Index-1].Label,$content.Length)
