param([string]$ListFile, [string]$OutFile, [string]$Lang = 'vi')
# VNA - Doc chu trong anh bang OCR co san cua Windows 10/11 (offline, mien phi).
# Can goi OCR tieng Viet: Settings > Time & Language > Language > Tieng Viet (bo cai VNA tu cai).
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$type) {
    $task = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
}

$language = New-Object Windows.Globalization.Language $Lang
if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($language)) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
} else {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    Write-Warning 'Chua co goi OCR tieng Viet; dung ngon ngu mac dinh (co the mat dau).'
}
if ($null -eq $engine) { throw 'Khong tao duoc bo OCR cua Windows.' }

$paths = [System.IO.File]::ReadAllLines($ListFile, [System.Text.Encoding]::UTF8)
$sb = New-Object System.Text.StringBuilder
foreach ($p in $paths) {
    if (-not $p) { continue }
    try {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        foreach ($line in $result.Lines) { [void]$sb.AppendLine($line.Text) }
    } catch {
        [void]$sb.AppendLine("(Khong doc duoc anh: $($_.Exception.Message))")
    }
    [void]$sb.AppendLine('<<<HET_TRANG>>>')
}
[System.IO.File]::WriteAllText($OutFile, $sb.ToString(), [System.Text.Encoding]::UTF8)
