param(
    [string]$InFile,
    [string]$OutWav,
    [double]$Rate = 1.0,
    [switch]$Play,
    [switch]$ListVoices
)
# VNA - Doc van ban bang giong noi cua Windows (offline).
# Uu tien giong tieng Viet (Microsoft An). Can cai goi giong noi tieng Viet trong Settings.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]

if ($ListVoices) {
    [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | ForEach-Object { "$($_.DisplayName) [$($_.Language)]" }
    exit 0
}

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

function Await($op, [Type]$type) {
    $task = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
}

$text = [System.IO.File]::ReadAllText($InFile, [System.Text.Encoding]::UTF8)
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Language -like 'vi*' } | Select-Object -First 1
if ($voice) { $synth.Voice = $voice }
else { Write-Warning 'Khong tim thay giong tieng Viet. Hay cai goi giong noi Tieng Viet trong Settings > Time & Language.' }
try { $synth.Options.SpeakingRate = [Math]::Max(0.5, [Math]::Min(3.0, $Rate)) } catch {}

$stream = Await ($synth.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$size = [uint32]$stream.Size
$reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
Await ($reader.LoadAsync($size)) ([uint32]) | Out-Null
$bytes = New-Object byte[] $size
$reader.ReadBytes($bytes)
[System.IO.File]::WriteAllBytes($OutWav, $bytes)

if ($Play) {
    $player = New-Object System.Media.SoundPlayer $OutWav
    $player.PlaySync()
    Remove-Item $OutWav -ErrorAction SilentlyContinue
}
