Attribute VB_Name = "VNA_Word"
' =====================================================================
'  VNA - Tro ly AI trong Microsoft Word
'  Yeu cau: phan mem VNA dang chay (bieu tuong VNA tren Desktop).
'  Cach dung: boi den doan van ban -> Alt+F8 -> chon macro VNA_... -> Run
'  (hoac gan macro len thanh Ribbon / Quick Access Toolbar).
' =====================================================================
Option Explicit

Private Const VNA_URL As String = "http://127.0.0.1:8765/api/office"

' ---------- Ham goi VNA ----------
Private Function GoiVNA(ByVal task As String, ByVal noiDung As String) As String
    Dim http As Object
    GoiVNA = ""
    On Error GoTo LoiKetNoi
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 5000, 5000, 30000, 1800000
    http.Open "POST", VNA_URL & "?task=" & task, False
    http.setRequestHeader "Content-Type", "text/plain; charset=utf-8"
    Application.StatusBar = "VNA dang xu ly, vui long cho..."
    System.Cursor = wdCursorWait
    http.send noiDung
    System.Cursor = wdCursorNormal
    Application.StatusBar = ""
    If http.Status = 200 Then
        GoiVNA = http.responseText
    Else
        MsgBox "VNA bao loi: " & Left(http.responseText, 600), vbExclamation, "VNA"
    End If
    Exit Function
LoiKetNoi:
    System.Cursor = wdCursorNormal
    Application.StatusBar = ""
    MsgBox "Khong ket noi duoc VNA." & vbCrLf & _
           "Hay mo phan mem VNA truoc (bieu tuong VNA tren Desktop) roi thu lai.", vbExclamation, "VNA"
End Function

' Lay van ban dang boi den; neu khong boi den thi lay ca tai lieu (khi cho phep)
Private Function LayVanBan(Optional ByVal choPhepCaTaiLieu As Boolean = True) As String
    If Len(Selection.Text) > 1 Then
        LayVanBan = Selection.Text
    ElseIf choPhepCaTaiLieu Then
        LayVanBan = ActiveDocument.Content.Text
    Else
        LayVanBan = ""
    End If
End Function

Private Function ChuanHoa(ByVal s As String) As String
    s = Replace(s, vbCrLf, vbCr)
    s = Replace(s, vbLf, vbCr)
    ChuanHoa = s
End Function

' Chen ket qua ngay sau vung chon (giu nguyen van ban goc)
Private Sub ChenSauVungChon(ByVal kq As String)
    Dim r As Range
    If kq = "" Then Exit Sub
    Set r = Selection.Range
    r.Collapse wdCollapseEnd
    r.InsertParagraphAfter
    r.Collapse wdCollapseEnd
    r.InsertAfter ChuanHoa(kq)
    r.Select
End Sub

' Mo tai lieu moi chua ket qua
Private Sub MoTaiLieuMoi(ByVal tieuDe As String, ByVal kq As String)
    Dim d As Document
    If kq = "" Then Exit Sub
    Set d = Documents.Add
    With d.Content
        .Font.Name = "Times New Roman"
        .Font.Size = 13
        .Text = tieuDe & vbCr & ChuanHoa(kq)
    End With
    d.Paragraphs(1).Range.Font.Bold = True
    d.Paragraphs(1).Range.Font.Size = 14
    d.Paragraphs(1).Alignment = wdAlignParagraphCenter
End Sub

' =====================================================================
'  CAC CHUC NANG
' =====================================================================

' 1. Thuc hien yeu cau: viet yeu cau vao van ban (VD: "Soan cong van gui cac phong ve viec..."),
'    boi den roi chay macro. Ket qua chen ngay ben duoi.
Public Sub VNA_ThucHienYeuCau()
    Dim s As String
    s = LayVanBan(False)
    If s = "" Then
        MsgBox "Hay viet yeu cau vao van ban, boi den roi chay lai." & vbCrLf & _
               "Vi du: Soan cong van gui cac phong, ban ve viec bao cao ket qua quy IV.", vbInformation, "VNA"
        Exit Sub
    End If
    ChenSauVungChon GoiVNA("thuc_hien", s)
End Sub

' 2. Tom tat van ban (vung chon hoac ca tai lieu) -> tai lieu moi
Public Sub VNA_TomTat()
    MoTaiLieuMoi "TOM TAT VAN BAN", GoiVNA("tom_tat", LayVanBan())
End Sub

' 3. Ra soat phap ly, the thuc, chinh ta -> tai lieu moi
Public Sub VNA_RaSoatVanBan()
    MoTaiLieuMoi "KET QUA RA SOAT VAN BAN", GoiVNA("ra_soat", LayVanBan())
End Sub

' 4. Bien tap van phong hanh chinh: ban sua chen ngay duoi doan goc
Public Sub VNA_BienTapVanPhong()
    Dim s As String
    s = LayVanBan(False)
    If s = "" Then
        MsgBox "Hay boi den doan van can bien tap.", vbInformation, "VNA"
        Exit Sub
    End If
    ChenSauVungChon GoiVNA("chinh_sua", s)
End Sub

' 5. Tham muu lanh dao: phan tich, phuong an, phan cong -> tai lieu moi
Public Sub VNA_ThamMuuLanhDao()
    MoTaiLieuMoi "Y KIEN THAM MUU", GoiVNA("tham_muu", LayVanBan())
End Sub

' 6. Phan tich phap ly / thuc thi phap luat -> tai lieu moi
Public Sub VNA_PhanTichPhapLy()
    MoTaiLieuMoi "PHAN TICH PHAP LY", GoiVNA("phap_ly", LayVanBan())
End Sub

' 6b. Lanh dao nha truong: nghien cuu van ban chi dao, nhiem vu cua truong -> tai lieu moi
Public Sub VNA_NghienCuuChoNhaTruong()
    MoTaiLieuMoi "NGHIEN CUU VAN BAN - NHIEM VU CUA NHA TRUONG", GoiVNA("truong", LayVanBan())
End Sub

' 6c. Giao vien: viet yeu cau (VD: Giao an Toan 9 bai Can bac hai, 2 tiet), boi den -> giao an chen ben duoi
Public Sub VNA_SoanGiaoAn()
    Dim s As String
    s = LayVanBan(False)
    If s = "" Then
        MsgBox "Hay viet yeu cau (mon, lop, bai, so tiet), boi den roi chay lai.", vbInformation, "VNA"
        Exit Sub
    End If
    MoTaiLieuMoi "KE HOACH BAI DAY", GoiVNA("giao_an", s)
End Sub

' 6d. Giao vien: soan ma tran, dac ta, de kiem tra va dap an
Public Sub VNA_SoanDeKiemTra()
    Dim s As String
    s = LayVanBan(False)
    If s = "" Then
        MsgBox "Hay viet yeu cau de kiem tra (mon, lop, thoi gian, pham vi, cau truc), boi den roi chay lai.", vbInformation, "VNA"
        Exit Sub
    End If
    MoTaiLieuMoi "DE KIEM TRA", GoiVNA("de_kiem_tra", s)
End Sub

' 7. Doc van ban thanh giong noi (vung chon hoac ca tai lieu)
Public Sub VNA_DocVanBan()
    Dim http As Object
    On Error GoTo LoiKetNoi
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.Open "POST", VNA_URL & "?task=tts", False
    http.setRequestHeader "Content-Type", "text/plain; charset=utf-8"
    http.send LayVanBan()
    Exit Sub
LoiKetNoi:
    MsgBox "Khong ket noi duoc VNA. Hay mo phan mem VNA truoc.", vbExclamation, "VNA"
End Sub

' 8. Dung doc
Public Sub VNA_DungDoc()
    Dim http As Object
    On Error Resume Next
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.Open "POST", VNA_URL & "?task=tts_stop", False
    http.send ""
End Sub
