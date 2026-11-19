param([string]$InFile)
# VNA - Hien thong bao nhac viec cua Windows 10/11.
$lines = [System.IO.File]::ReadAllLines($InFile, [System.Text.Encoding]::UTF8)
Remove-Item $InFile -ErrorAction SilentlyContinue
$title = [System.Security.SecurityElement]::Escape($lines[0])
$body = [System.Security.SecurityElement]::Escape(($lines | Select-Object -Skip 1) -join ' ')
try {
    $null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
    $null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml("<toast scenario='reminder'><visual><binding template='ToastGeneric'><text>$title</text><text>$body</text></binding></visual><actions><action content='Đã biết' arguments='ok' activationType='system'/></actions><audio src='ms-winsoundevent:Notification.Reminder'/></toast>")
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    $n = New-Object System.Windows.Forms.NotifyIcon
    $n.Icon = [System.Drawing.SystemIcons]::Information
    $n.Visible = $true
    $n.ShowBalloonTip(15000, $lines[0], (($lines | Select-Object -Skip 1) -join ' '), 'Info')
    Start-Sleep -Seconds 16
    $n.Dispose()
}
