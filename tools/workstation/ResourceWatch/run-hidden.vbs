' Starts the ResourceWatch check without flashing a console window.
' Runs ResourceWatch.ps1 from the same folder as this file, so no user path is baked in.
Dim fso, here
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
CreateObject("WScript.Shell").Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & here & "\ResourceWatch.ps1"" -Mode Check", 0, False
