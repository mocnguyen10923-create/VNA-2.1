param([string]$File)
# VNA - Phat file am thanh (mp3/wav) bang Windows Media Player, khong hien cua so.
$player = New-Object -ComObject WMPlayer.OCX
$player.URL = $File
$player.controls.play()
Start-Sleep -Milliseconds 800
while ($player.playState -eq 3 -or $player.playState -eq 6 -or $player.playState -eq 9) {
    Start-Sleep -Milliseconds 300
}
$player.close()
