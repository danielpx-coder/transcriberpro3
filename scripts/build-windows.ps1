$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not $IsWindows -and $env:OS -ne 'Windows_NT') { throw 'Execute em Windows x64.' }
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Comando falhou: $LASTEXITCODE" } }
py -3.11 -m venv .venv-build
Check-Exit
$Python = Join-Path $PWD '.venv-build\Scripts\python.exe'
& $Python -m pip install -r requirements-core.txt pyinstaller==6.16.0
Check-Exit
& $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name TranscriberPro3 --paths . --collect-all faster_whisper --collect-all ctranslate2 --collect-all av --collect-all tokenizers --collect-all onnxruntime --collect-all huggingface_hub desktop/main.py
Check-Exit
Copy-Item docs/WINDOWS.md dist/TranscriberPro3/LEIA-ME.md
Copy-Item THIRD_PARTY.md dist/TranscriberPro3/THIRD_PARTY.md
& $Python scripts/collect-licenses.py dist/TranscriberPro3/licenses
Check-Exit
$exe = Join-Path $PWD 'dist\TranscriberPro3\TranscriberPro3.exe'
$test = Start-Process -FilePath $exe -ArgumentList '--self-test' -Wait -PassThru
if ($test.ExitCode -ne 0) { throw 'O executável não passou no smoke test.' }
Compress-Archive -Path dist/TranscriberPro3 -DestinationPath dist/TranscriberPro3-windows-x64.zip -Force
Get-FileHash dist/TranscriberPro3-windows-x64.zip -Algorithm SHA256 | Format-List
