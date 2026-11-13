$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

Write-Host 'Atelier local AI check (OpenRouter)'
Write-Host 'Your key is hidden while typing and is not saved to a file.'
$secureKey = Read-Host 'Paste your OpenRouter API key' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
$plainKey = $null
$previousKey = $env:OPENROUTER_API_KEY
$previousVisionModel = $env:VISION_LAB_MODEL

try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        throw 'No key entered. Start this script again and enter your OpenRouter key.'
    }

    $env:OPENROUTER_API_KEY = $plainKey
    $probeScript = Join-Path $PSScriptRoot 'tools\test_openrouter_free_models.py'
    if (Test-Path -LiteralPath $probeScript) {
        $probeLines = @(& $python $probeScript 2>&1)
        foreach ($line in $probeLines) { Write-Host $line }
        $selectedLine = $probeLines | ForEach-Object { $_.ToString() } | Where-Object { $_.StartsWith('SELECTED_MODEL=') } | Select-Object -Last 1
        if ($selectedLine) {
            $selectedModel = $selectedLine.Substring('SELECTED_MODEL='.Length).Trim()
            if ($selectedModel) {
                $env:VISION_LAB_MODEL = $selectedModel
                Write-Host "Visual Lab will use: $selectedModel"
            } else {
                Write-Host 'No free model answered. The app will stay on its configured default and show its fallback if AI is unavailable.'
            }
        }
    }
    Write-Host 'Starting test server at http://127.0.0.1:5001'
    Write-Host 'Keep this window open while testing. Press Ctrl+C to stop.'
    & $python -m flask --app app run --host 127.0.0.1 --port 5001
}
finally {
    if ($null -ne $keyPointer) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
    $plainKey = $null
    $secureKey = $null
    if ([string]::IsNullOrEmpty($previousKey)) {
        Remove-Item Env:OPENROUTER_API_KEY -ErrorAction SilentlyContinue
    } else {
        $env:OPENROUTER_API_KEY = $previousKey
    }
    if ([string]::IsNullOrEmpty($previousVisionModel)) {
        Remove-Item Env:VISION_LAB_MODEL -ErrorAction SilentlyContinue
    } else {
        $env:VISION_LAB_MODEL = $previousVisionModel
    }
    $previousKey = $null
    $previousVisionModel = $null
}
