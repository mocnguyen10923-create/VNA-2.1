# =====================================================================
#  VNA - Tu dong cai goi giong noi tieng Viet cua Windows (Microsoft An)
#  Bo cai VNA chay buoc nay voi quyen quan tri (Windows hoi xac nhan 1 lan).
#  Can Internet (tai tu Windows Update), mat khoang 1-5 phut.
# =====================================================================
$ErrorActionPreference = 'Continue'
Write-Host '=== VNA: cai giong doc tieng Viet ===' -ForegroundColor Cyan

$have = $false
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
    $have = @([Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Language -like 'vi*' }).Count -gt 0
} catch {}

try {
    $ocr = Get-WindowsCapability -Online -Name 'Language.OCR~~~vi-VN~0.0.1.0' -ErrorAction Stop
    if ($ocr.State -ne 'Installed') { Write-Host 'Dang cai goi doc chu trong anh (OCR) tieng Viet...'; Add-WindowsCapability -Online -Name 'Language.OCR~~~vi-VN~0.0.1.0' | Out-Null }
    Write-Host '[OK] OCR tieng Viet' -ForegroundColor Green
} catch { Write-Host "[!] Khong cai duoc OCR tieng Viet: $($_.Exception.Message)" -ForegroundColor Yellow }
if ($have) {
    Write-Host '[OK] May da co giong doc tieng Viet.' -ForegroundColor Green
} else {
    $caps = @('Language.Basic~~~vi-VN~0.0.1.0', 'Language.TextToSpeech~~~vi-VN~0.0.1.0', 'Language.Speech~~~vi-VN~0.0.1.0', 'Language.OCR~~~vi-VN~0.0.1.0')
    foreach ($c in $caps) {
        try {
            $st = Get-WindowsCapability -Online -Name $c -ErrorAction Stop
            if ($st.State -ne 'Installed') {
                Write-Host "Dang cai $c ..."
                Add-WindowsCapability -Online -Name $c -ErrorAction Stop | Out-Null
            }
            Write-Host "[OK] $c" -ForegroundColor Green
        } catch {
            Write-Host "[!] Khong cai duoc $c : $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
    Write-Host 'Neu chua co giong Viet: Settings > Time & Language > Language & region > Add a language > Tieng Viet (tich Text-to-speech).'
}
Start-Sleep -Seconds 3
