Set WshShell = CreateObject("WScript.Shell")
strPath = WshShell.CurrentDirectory

' Prefer virtual environment pythonw if present, else fallback to system pythonw
Set fso = CreateObject("Scripting.FileSystemObject")
If fso.FileExists(strPath & "\venv\Scripts\pythonw.exe") Then
    pythonwExe = """" & strPath & "\venv\Scripts\pythonw.exe"""
ElseIf fso.FileExists(strPath & "\..\venv\Scripts\pythonw.exe") Then
    pythonwExe = """" & strPath & "\..\venv\Scripts\pythonw.exe"""
Else
    pythonwExe = "pythonw.exe"
End If

scriptPath = """" & strPath & "\kupido_player.py"""
WshShell.Run pythonwExe & " " & scriptPath, 0, False
Set WshShell = Nothing
Set fso = Nothing
