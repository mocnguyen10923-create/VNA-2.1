; =====================================================================
;  VNA - Bo cai dat Windows MOT LAN BAM, TU DONG CAI MOI THU
;  Nguoi dung chi chay VNA_Setup.exe. Sau khi cai:
;   - Tao thu muc VNA quan ly, bieu tuong Desktop, tu chay cung Windows
;   - Cai macro Word/Excel (im lang)
;   - Cai giong doc tieng Viet (Windows hoi quyen quan tri 1 lan)
;   - Mo VNA: VNA tu cai bo nao AI Ollama + tu tai mo hinh hop voi RAM (co thanh tien do)
; =====================================================================
#define AppName "VNA - AI chuyên gia"
#define AppVer "2.1.0"

[Setup]
AppId={{6E2B7A51-3C4D-4F8E-9A1B-0000000000A1}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=VNA
DefaultDirName={autopf}\VNA
DefaultGroupName=VNA
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=VNA_Setup
SetupIconFile=assets\vna.ico
UninstallDisplayIcon={app}\VNA.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force

[Dirs]
Name: "{userdocs}\VNA\Quản lý công việc\01_VAN_BAN_DEN\Da_xu_ly"
Name: "{userdocs}\VNA\Quản lý công việc\02_NGUON_CAN_CU\Van_ban_phap_luat"
Name: "{userdocs}\VNA\Quản lý công việc\02_NGUON_CAN_CU\Huong_dan_chuyen_mon"
Name: "{userdocs}\VNA\Quản lý công việc\02_NGUON_CAN_CU\Chuong_trinh_GDPT_2018"
Name: "{userdocs}\VNA\Quản lý công việc\02_NGUON_CAN_CU\Quy_che_noi_bo"
Name: "{userdocs}\VNA\Quản lý công việc\02_NGUON_CAN_CU\Het_hieu_luc"
Name: "{userdocs}\VNA\Quản lý công việc\03_TAI_LIEU_THAM_KHAO"
Name: "{userdocs}\VNA\Quản lý công việc\04_SAN_PHAM\Du_thao"
Name: "{userdocs}\VNA\Quản lý công việc\04_SAN_PHAM\Da_ban_hanh"
Name: "{userdocs}\VNA\Quản lý công việc\05_THEO_DOI"

[Files]
Source: "dist\VNA\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
; (Tuy chon) kem san bo cai Ollama de cai khong can Internet: dat file vao redist\OllamaSetup.exe truoc khi dong goi
Source: "redist\OllamaSetup.exe"; DestDir: "{app}\redist"; Flags: ignoreversion skipifsourcedoesntexist
; (Tuy chon) kem san mo hinh AI: chep thu muc %USERPROFILE%\.ollama\models tu may da tai vao redist\models
Source: "redist\models\*"; DestDir: "{%USERPROFILE}\.ollama\models"; Flags: recursesubdirs ignoreversion skipifsourcedoesntexist onlyifdoesntexist

[Icons]
Name: "{autoprograms}\VNA\VNA - AI chuyên gia"; Filename: "{app}\VNA.exe"; IconFilename: "{app}\vna.ico"
Name: "{autoprograms}\VNA\Hướng dẫn sử dụng VNA"; Filename: "{app}\HUONG_DAN.docx"
Name: "{autoprograms}\VNA\Cài lại macro Word - Excel"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\office\cai_dat_office.ps1"""
Name: "{autoprograms}\VNA\Gỡ cài đặt VNA"; Filename: "{uninstallexe}"
Name: "{autodesktop}\VNA"; Filename: "{app}\VNA.exe"; IconFilename: "{app}\vna.ico"
Name: "{autodesktop}\VNA - Quản lý công việc"; Filename: "{userdocs}\VNA\Quản lý công việc"
Name: "{userstartup}\VNA"; Filename: "{app}\VNA.exe"; Parameters: "--no-browser"

[Run]
; 1. Macro Word/Excel (im lang)
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\office\cai_dat_office.ps1"" -Silent"; StatusMsg: "Đang cài macro VNA vào Word và Excel..."; Flags: runhidden waituntilterminated
; 2. Giong doc tieng Viet (can quyen quan tri - Windows hoi 1 lan)
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\setup\cai_giong_viet.ps1"""; StatusMsg: "Đang cài giọng đọc tiếng Việt..."; Flags: shellexec waituntilterminated; Verb: runas
; 3. Mo VNA: VNA tu cai bo nao AI va tai mo hinh (hien tien do tren man hinh)
Filename: "{app}\VNA.exe"; Flags: nowait

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/IM VNA.exe /F"; Flags: runhidden; RunOnceId: "KillVNA"

[Messages]
FinishedLabel=VNA đã được cài đặt. VNA sẽ tự mở và tự hoàn tất các phần còn lại (bộ não AI, mô hình) — bạn không cần làm gì thêm.
