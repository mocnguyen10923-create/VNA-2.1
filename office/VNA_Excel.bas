Attribute VB_Name = "VNA_Excel"
' =====================================================================
'  VNA - Tro ly AI trong Microsoft Excel
'  Yeu cau: phan mem VNA dang chay (bieu tuong VNA tren Desktop).
'  Cach dung: chon vung du lieu -> Alt+F8 -> chon macro VNA_... -> Run
' =====================================================================
Option Explicit

Private Const VNA_URL As String = "http://127.0.0.1:8765/api/office"

Private Function GoiVNA(ByVal task As String, ByVal noiDung As String) As String
    Dim http As Object
    GoiVNA = ""
    On Error GoTo LoiKetNoi
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 5000, 5000, 30000, 1800000
    http.Open "POST", VNA_URL & "?task=" & task & "&fmt=md", False
    http.setRequestHeader "Content-Type", "text/plain; charset=utf-8"
    Application.StatusBar = "VNA dang xu ly, vui long cho..."
    Application.Cursor = xlWait
    http.send noiDung
    Application.Cursor = xlDefault
    Application.StatusBar = False
    If http.Status = 200 Then
        GoiVNA = http.responseText
    Else
        MsgBox "VNA bao loi: " & Left(http.responseText, 600), vbExclamation, "VNA"
    End If
    Exit Function
LoiKetNoi:
    Application.Cursor = xlDefault
    Application.StatusBar = False
    MsgBox "Khong ket noi duoc VNA." & vbCrLf & _
           "Hay mo phan mem VNA truoc (bieu tuong VNA tren Desktop) roi thu lai.", vbExclamation, "VNA"
End Function

' Chuyen vung chon thanh van ban TSV (toi da 20000 o)
Private Function VungSangTSV(ByVal rg As Range) As String
    Dim r As Long, c As Long, s As String, dong As String
    If rg.Cells.CountLarge > 20000 Then
        MsgBox "Vung chon qua lon (toi da 20000 o). Hay chon vung nho hon.", vbExclamation, "VNA"
        VungSangTSV = ""
        Exit Function
    End If
    For r = 1 To rg.Rows.Count
        dong = ""
        For c = 1 To rg.Columns.Count
            If c > 1 Then dong = dong & vbTab
            dong = dong & Replace(Replace(rg.Cells(r, c).Text, vbTab, " "), vbLf, " ")
        Next c
        If Len(Replace(dong, vbTab, "")) > 0 Then s = s & dong & vbLf
    Next r
    VungSangTSV = s
End Function

Private Function HoiYeuCau(ByVal loiNhac As String) As String
    Dim v As Variant
    v = Application.InputBox(loiNhac, "VNA - Tro ly AI", Type:=2)
    If VarType(v) = vbBoolean Then
        HoiYeuCau = ""
    Else
        HoiYeuCau = Trim(CStr(v))
    End If
End Function

Private Function LaSo(ByVal s As String) As Boolean
    Dim t As String
    t = Replace(Replace(s, " ", ""), ",", "")
    LaSo = (Len(t) > 0 And t Like "*[0-9]*" And Not t Like "*[!0-9.-]*" And _
            (Len(t) - Len(Replace(t, ".", ""))) <= 1 And InStr(2, t, "-") = 0)
End Function

Private Function BoDinhDang(ByVal s As String) As String
    s = Replace(s, "**", "")
    s = Replace(s, "`", "")
    s = Replace(s, "<br>", " ")
    BoDinhDang = Trim(s)
End Function

' Ghi ket qua (bang Markdown + loi binh) sang trang tinh moi
Private Sub GhiKetQua(ByVal kq As String, ByVal tenSheet As String)
    Dim ws As Worksheet, dongs() As String, i As Long, j As Long, r As Long
    Dim dg As String, o() As String, gt As String, dauBang As Boolean, loc As String
    If kq = "" Then Exit Sub
    Set ws = ActiveWorkbook.Worksheets.Add(After:=ActiveWorkbook.Sheets(ActiveWorkbook.Sheets.Count))
    On Error Resume Next
    ws.Name = Left(tenSheet & " " & Format(Now, "hhmmss"), 31)
    On Error GoTo 0
    ws.Cells.Font.Name = "Times New Roman"
    ws.Cells.Font.Size = 12
    kq = Replace(kq, vbCr, "")
    dongs = Split(kq, vbLf)
    r = 1
    dauBang = True
    For i = LBound(dongs) To UBound(dongs)
        dg = Trim(dongs(i))
        If Left(dg, 1) = "|" Then
            loc = Replace(Replace(Replace(Replace(dg, "|", ""), "-", ""), ":", ""), " ", "")
            If loc = "" Then GoTo TiepTuc   ' dong phan cach |---|---|
            If Right(dg, 1) = "|" Then dg = Left(dg, Len(dg) - 1)
            o = Split(Mid(dg, 2), "|")
            For j = LBound(o) To UBound(o)
                gt = BoDinhDang(o(j))
                If Not dauBang And LaSo(gt) Then
                    ws.Cells(r, j + 1).Value = Val(Replace(Replace(gt, " ", ""), ",", ""))
                Else
                    ws.Cells(r, j + 1).NumberFormat = "@"
                    ws.Cells(r, j + 1).Value = gt
                End If
                ws.Cells(r, j + 1).Borders.LineStyle = xlContinuous
                If dauBang Then
                    ws.Cells(r, j + 1).Font.Bold = True
                    ws.Cells(r, j + 1).Interior.Color = RGB(220, 230, 241)
                    ws.Cells(r, j + 1).HorizontalAlignment = xlCenter
                End If
            Next j
            dauBang = False
            r = r + 1
        Else
            dauBang = True
            If dg <> "" Then
                If Left(dg, 1) = "#" Then
                    ws.Cells(r, 1).Value = Trim(Replace(dg, "#", ""))
                    ws.Cells(r, 1).Font.Bold = True
                Else
                    ws.Cells(r, 1).Value = BoDinhDang(dg)
                End If
                r = r + 1
            ElseIf r > 1 Then
                r = r + 1
            End If
        End If
TiepTuc:
    Next i
    ws.Columns.AutoFit
    For j = 1 To ws.UsedRange.Columns.Count
        If ws.Columns(j).ColumnWidth > 60 Then ws.Columns(j).ColumnWidth = 60
    Next j
    ws.Activate
End Sub

' =====================================================================
'  CAC CHUC NANG
' =====================================================================

' 1. Phan tich du lieu trong vung chon theo yeu cau -> sheet moi
Public Sub VNA_PhanTichDuLieu()
    Dim dl As String, yc As String
    If TypeName(Selection) <> "Range" Then Exit Sub
    dl = VungSangTSV(Selection)
    If dl = "" Then Exit Sub
    yc = HoiYeuCau("Nhap yeu cau phan tich (co the go tieng Viet co dau)." & vbCrLf & _
                   "VD: Tong hop theo don vi, tinh ty le hoan thanh, nhan xet")
    If yc = "" Then yc = "Phan tich tong quan, lap bang tong hop va nhan xet"
    GhiKetQua GoiVNA("phan_tich", "YEU CAU: " & yc & vbLf & vbLf & "DU LIEU:" & vbLf & dl), "VNA phan tich"
End Sub

' 2. Tao bang moi tu mo ta -> sheet moi
Public Sub VNA_TaoBang()
    Dim yc As String
    yc = HoiYeuCau("Mo ta bang can tao." & vbCrLf & "VD: Bang theo doi tien do 10 nhiem vu: STT, nhiem vu, don vi chu tri, han, tinh trang")
    If yc = "" Then Exit Sub
    GhiKetQua GoiVNA("tao_bang", yc), "VNA bang"
End Sub

' 3. Viet cong thuc Excel theo mo ta -> ghi vao o dang chon
Public Sub VNA_VietCongThuc()
    Dim yc As String, ct As String, o As Range
    Set o = ActiveCell
    yc = HoiYeuCau("Mo ta cong thuc can viet cho o " & o.Address(False, False) & "." & vbCrLf & _
                   "VD: Tong cot D tu dong 2 den 100 neu cot C la 'Hoan thanh'")
    If yc = "" Then Exit Sub
    ct = Trim(GoiVNA("cong_thuc", "O dang chon: " & o.Address(False, False) & " (sheet " & o.Worksheet.Name & ")" & vbLf & yc))
    If ct = "" Then Exit Sub
    On Error GoTo KhongHopLe
    o.Formula = ct
    Exit Sub
KhongHopLe:
    o.Offset(0, 1).Value = "'" & ct
    MsgBox "Cong thuc VNA de xuat chua dung voi Excel cua ban, da ghi o ben canh de chinh sua:" & vbCrLf & ct, vbInformation, "VNA"
End Sub

' 3b. Nhan xet hoc sinh theo Thong tu 22: chon vung CO DONG TIEU DE (Ho ten, diem...) -> nhan xet ghi vao cot ben phai
Public Sub VNA_NhanXetHocSinh()
    Dim rg As Range, mon As String, kq As String, dongs() As String, i As Long, cotKQ As Long, loai As String
    If TypeName(Selection) <> "Range" Then Exit Sub
    Set rg = Selection
    If rg.Rows.Count < 2 Then
        MsgBox "Hay chon ca dong tieu de va danh sach hoc sinh (Ho ten, cac cot diem).", vbInformation, "VNA"
        Exit Sub
    End If
    mon = HoiYeuCau("Mon hoc / lop (VD: Toan 9A). Nhap 'RL' neu la nhan xet ren luyen.")
    loai = "mon_hoc"
    If UCase(Trim(mon)) = "RL" Then loai = "ren_luyen": mon = ""
    kq = GoiVNA("nhan_xet&loai=" & loai, VungSangTSV(rg))
    If kq = "" Then Exit Sub
    kq = Replace(kq, vbCr, "")
    dongs = Split(kq, vbLf)
    cotKQ = rg.Column + rg.Columns.Count
    rg.Worksheet.Cells(rg.Row, cotKQ).Value = "Nhan xet (VNA)"
    rg.Worksheet.Cells(rg.Row, cotKQ).Font.Bold = True
    For i = 0 To UBound(dongs)
        If i + 1 > rg.Rows.Count - 1 Then Exit For
        rg.Worksheet.Cells(rg.Row + 1 + i, cotKQ).Value = dongs(i)
        rg.Worksheet.Cells(rg.Row + 1 + i, cotKQ).WrapText = True
    Next i
    rg.Worksheet.Columns(cotKQ).ColumnWidth = 60
End Sub

' 4. Doc to noi dung vung chon
Public Sub VNA_DocVungChon()
    Dim http As Object
    If TypeName(Selection) <> "Range" Then Exit Sub
    On Error GoTo LoiKetNoi
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.Open "POST", VNA_URL & "?task=tts", False
    http.setRequestHeader "Content-Type", "text/plain; charset=utf-8"
    http.send VungSangTSV(Selection)
    Exit Sub
LoiKetNoi:
    MsgBox "Khong ket noi duoc VNA. Hay mo phan mem VNA truoc.", vbExclamation, "VNA"
End Sub

' 5. Dung doc
Public Sub VNA_DungDoc()
    Dim http As Object
    On Error Resume Next
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.Open "POST", VNA_URL & "?task=tts_stop", False
    http.send ""
End Sub
