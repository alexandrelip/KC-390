[CmdletBinding()]
param(
    [ValidateSet('Info', 'Capture', 'Click', 'Key', 'Resize', 'Close', 'Inspect', 'Invoke', 'Select', 'SetValue')]
    [string]$Action = 'Info',
    [Parameter(Mandatory)][int]$ProcessId,
    [int]$X,
    [int]$Y,
    [string]$Keys,
    [string]$OutputPath,
    [string]$ControlName,
    [string]$ControlId,
    [string]$ControlType,
    [string]$Value
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
if (-not ('KC390LiveryWindowV2' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class KC390LiveryWindowV2 {
    [StructLayout(LayoutKind.Sequential)]
    public struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr window, out Rect rect);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr window, int command);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr window, int x, int y, int width, int height, bool repaint);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr window, IntPtr device, uint flags);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr window);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint source, uint target, bool attach);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint x, uint y, uint data, UIntPtr extra);
    public static bool Focus(IntPtr window) {
        uint foregroundProcess;
        uint foregroundThread = GetWindowThreadProcessId(GetForegroundWindow(), out foregroundProcess);
        uint currentThread = GetCurrentThreadId();
        bool attached = foregroundThread != currentThread && AttachThreadInput(currentThread, foregroundThread, true);
        try {
            BringWindowToTop(window);
            SetForegroundWindow(window);
            return GetForegroundWindow() == window;
        } finally { if (attached) AttachThreadInput(currentThread, foregroundThread, false); }
    }
}
'@
}
$process = Get-Process -Id $ProcessId
if ($process.ProcessName -notin @('ModelViewer2', 'DCS') -or $process.MainWindowHandle -eq 0) {
    throw 'Refusing to control a process without a DCS or ModelViewer2 window.'
}
if ($Action -in @('Inspect', 'Invoke', 'Select', 'SetValue')) {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    $processCondition = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcessId)
    $roots = [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children, $processCondition)
    $controls = foreach ($root in $roots) {
        $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    }
    $matches = @($controls | Where-Object {
        (-not $ControlName -or $_.Current.Name -eq $ControlName) -and
        (-not $ControlId -or $_.Current.AutomationId -eq $ControlId) -and
        (-not $ControlType -or $_.Current.ControlType.ProgrammaticName -eq "ControlType.$ControlType")
    })
    if ($Action -eq 'Inspect') {
        $matches | Where-Object { $_.Current.Name -or $_.Current.ControlType.ProgrammaticName -eq 'ControlType.Edit' } | ForEach-Object {
            [pscustomobject]@{
                Name = $_.Current.Name
                Id = $_.Current.AutomationId
                Type = $_.Current.ControlType.ProgrammaticName
                Enabled = $_.Current.IsEnabled
                Offscreen = $_.Current.IsOffscreen
                Patterns = ($_.GetSupportedPatterns() | ForEach-Object ProgrammaticName) -join ','
            }
        }
        return
    }
    if (-not $ControlName -and -not $ControlId) { throw 'An exact control name or automation ID is required.' }
    if ($matches.Count -ne 1) { throw "Expected exactly one control; found $($matches.Count)." }
    $control = $matches[0]
    switch ($Action) {
        'Invoke' { ([System.Windows.Automation.InvokePattern]$control.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)).Invoke() }
        'Select' { ([System.Windows.Automation.SelectionItemPattern]$control.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)).Select() }
        'SetValue' { ([System.Windows.Automation.ValuePattern]$control.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)).SetValue($Value) }
    }
    Write-Output "UIA|$Action|$ControlName|$ControlId"
    return
}
[void][KC390LiveryWindowV2]::SetProcessDPIAware()
$bounds = [KC390LiveryWindowV2+Rect]::new()
if (-not [KC390LiveryWindowV2]::GetWindowRect($process.MainWindowHandle, [ref]$bounds)) {
    throw 'Cannot read target window bounds.'
}
if ($Action -in @('Click', 'Key')) {
    if (-not [KC390LiveryWindowV2]::Focus($process.MainWindowHandle)) {
        throw 'Refusing input or capture because the target window is not in the foreground.'
    }
    [void][KC390LiveryWindowV2]::GetWindowRect($process.MainWindowHandle, [ref]$bounds)
}
switch ($Action) {
    'Info' {
        [pscustomobject]@{ Id = $process.Id; Title = $process.MainWindowTitle; Left = $bounds.Left; Top = $bounds.Top; Width = $bounds.Right - $bounds.Left; Height = $bounds.Bottom - $bounds.Top }
    }
    'Resize' {
        if ($X -lt 640 -or $Y -lt 480) { throw 'Resize dimensions are too small.' }
        [void][KC390LiveryWindowV2]::ShowWindow($process.MainWindowHandle, 9)
        [void][KC390LiveryWindowV2]::MoveWindow($process.MainWindowHandle, 40, 40, $X, $Y, $true)
    }
    'Capture' {
        if (-not $OutputPath) { throw 'Capture requires an output path.' }
        $bitmap = [Drawing.Bitmap]::new($bounds.Right - $bounds.Left, $bounds.Bottom - $bounds.Top)
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        try {
            $device = $graphics.GetHdc()
            try {
                if (-not [KC390LiveryWindowV2]::PrintWindow($process.MainWindowHandle, $device, 2)) { throw 'Native window capture failed.' }
            } finally { $graphics.ReleaseHdc($device) }
            $bitmap.Save($OutputPath, [Drawing.Imaging.ImageFormat]::Png)
        } finally { $graphics.Dispose(); $bitmap.Dispose() }
        Write-Output "CAPTURE|$OutputPath"
    }
    'Click' {
        if ($X -lt 0 -or $Y -lt 0 -or $X -ge $bounds.Right - $bounds.Left -or $Y -ge $bounds.Bottom - $bounds.Top) { throw 'Click outside target window.' }
        [void][KC390LiveryWindowV2]::SetCursorPos($bounds.Left + $X, $bounds.Top + $Y)
        [KC390LiveryWindowV2]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero)
        [KC390LiveryWindowV2]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
    }
    'Key' { [Windows.Forms.SendKeys]::SendWait($Keys) }
    'Close' { Write-Output ("CLOSE_REQUESTED|" + $process.CloseMainWindow()) }
}