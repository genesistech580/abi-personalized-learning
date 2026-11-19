$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8000 is already in use. Stop the current Django server with Ctrl+C in its terminal, then try again.'
}

$key = Read-Host 'OpenAI API key' -AsSecureString
$previousKey = $env:OPENAI_API_KEY
try {
    $enteredKey = [System.Net.NetworkCredential]::new('', $key).Password.Trim()
    if ($enteredKey -notmatch '^sk-[^\s]+$') {
        throw 'Enter a complete OpenAI secret key.'
    }
    $env:OPENAI_API_KEY = $enteredKey
    & $python (Join-Path $PSScriptRoot 'manage.py') runserver 127.0.0.1:8000
} finally {
    $env:OPENAI_API_KEY = $previousKey
    Remove-Variable enteredKey, previousKey -ErrorAction SilentlyContinue
    $key.Dispose()
}
