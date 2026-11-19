# =====================================================================
#  VNA - Cai macro vao Microsoft Word (Normal.dotm) va Excel (PERSONAL.XLSB)
#  Chay: chuot phai > Run with PowerShell  (hoac bo cai VNA tu chay)
#  Hay DONG Word va Excel truoc khi chay.
# =====================================================================
param([switch]$Silent)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$wordBas = Join-Path $here 'VNA_Word.bas'
$excelBas = Join-Path $here 'VNA_Excel.bas'

function Get-OfficeVersion {
    foreach ($v in '16.0', '15.0', '14.0') {
        if (Test-Path "HKCU:\Software\Microsoft\Office\$v") { return $v }
    }
    return '16.0'
}
$ver = Get-OfficeVersion

function Enable-VBOM($app) {
    $key = "HKCU:\Software\Microsoft\Office\$ver\$app\Security"
    if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
    $old = (Get-ItemProperty -Path $key -Name AccessVBOM -ErrorAction SilentlyContinue).AccessVBOM
    Set-ItemProperty -Path $key -Name AccessVBOM -Value 1 -Type DWord
    return $old
}
function Restore-VBOM($app, $old) {
    $key = "HKCU:\Software\Microsoft\Office\$ver\$app\Security"
    if ($null -eq $old) { Remove-ItemProperty -Path $key -Name AccessVBOM -ErrorAction SilentlyContinue }
    else { Set-ItemProperty -Path $key -Name AccessVBOM -Value $old -Type DWord }
}
function Remove-Module($vbproj, $name) {
    foreach ($c in @($vbproj.VBComponents)) { if ($c.Name -eq $name) { $vbproj.VBComponents.Remove($c) } }
}

Write-Host '=== VNA: cai macro cho Microsoft Office ===' -ForegroundColor Cyan

# ---------------- WORD ----------------
try {
    $old = Enable-VBOM 'Word'
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $tpl = $word.NormalTemplate
    Remove-Module $tpl.VBProject 'VNA_Word'
    $tpl.VBProject.VBComponents.Import($wordBas) | Out-Null
    $tpl.Save()
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    Write-Host '[OK] Da cai macro VNA vao Word (Normal.dotm).' -ForegroundColor Green
} catch {
    Write-Host "[!] Khong cai duoc macro Word: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host '    Cach thu cong: Word > Alt+F11 > File > Import File... > chon VNA_Word.bas'
} finally {
    Restore-VBOM 'Word' $old
}

# ---------------- EXCEL ----------------
try {
    $old = Enable-VBOM 'Excel'
    $xl = New-Object -ComObject Excel.Application
    $xl.Visible = $false
    $xl.DisplayAlerts = $false
    $startup = $xl.StartupPath
    if (-not (Test-Path $startup)) { New-Item -ItemType Directory -Path $startup -Force | Out-Null }
    $personal = Join-Path $startup 'PERSONAL.XLSB'
    if (Test-Path $personal) {
        $wb = $xl.Workbooks.Open($personal)
    } else {
        $wb = $xl.Workbooks.Add()
    }
    Remove-Module $wb.VBProject 'VNA_Excel'
    $wb.VBProject.VBComponents.Import($excelBas) | Out-Null
    if (Test-Path $personal) {
        $wb.Save()
    } else {
        $wb.SaveAs($personal, 50)   # 50 = xlExcel12 (.xlsb)
    }
    $wb.Close($false)
    $xl.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
    # An so tay PERSONAL khi mo Excel lan sau
    Write-Host '[OK] Da cai macro VNA vao Excel (PERSONAL.XLSB).' -ForegroundColor Green
    Write-Host '     Lan dau mo Excel neu thay so "PERSONAL" hien ra: View > Hide, roi luu khi dong Excel.'
} catch {
    Write-Host "[!] Khong cai duoc macro Excel: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host '    Cach thu cong: Excel > Alt+F11 > File > Import File... > chon VNA_Excel.bas'
} finally {
    Restore-VBOM 'Excel' $old
}

Write-Host ''
Write-Host 'Xong. Trong Word/Excel: Alt+F8 > chon macro VNA_... > Run.' -ForegroundColor Cyan
Write-Host 'Nen gan macro len thanh cong cu: File > Options > Customize Ribbon > Choose commands from: Macros.'
# Danh dau da cai (VNA se khong cai lai)
try {
    $flagDir = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'VNA'
    New-Item -ItemType Directory -Path $flagDir -Force | Out-Null
    Set-Content -Path (Join-Path $flagDir '.macro_da_cai') -Value 'ok'
} catch {}
if (-not $Silent) { Read-Host 'Nhan Enter de dong' }
