param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [Parameter(Mandatory = $true)][string[]]$CommandArguments,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$StdoutPath,
    [Parameter(Mandatory = $true)][string]$StderrPath,
    [Parameter(Mandatory = $true)][string]$MetricsPath
)

$ErrorActionPreference = "Stop"
$info = [System.Diagnostics.ProcessStartInfo]::new()
$info.FileName = $Executable
$info.WorkingDirectory = $WorkingDirectory
$info.UseShellExecute = $false
$info.CreateNoWindow = $true
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
foreach ($argument in $CommandArguments) {
    [void]$info.ArgumentList.Add($argument)
}

$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $info
$startedUtc = [DateTime]::UtcNow
$timer = [System.Diagnostics.Stopwatch]::StartNew()
if (-not $process.Start()) { throw "Unable to start measured process." }
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$peakWorkingSet = 0L
while (-not $process.HasExited) {
    $process.Refresh()
    if ($process.PeakWorkingSet64 -gt $peakWorkingSet) {
        $peakWorkingSet = $process.PeakWorkingSet64
    }
    Start-Sleep -Milliseconds 100
}
$process.WaitForExit()
$timer.Stop()
$stdout = $stdoutTask.GetAwaiter().GetResult()
$stderr = $stderrTask.GetAwaiter().GetResult()
[System.IO.File]::WriteAllText($StdoutPath, $stdout, [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText($StderrPath, $stderr, [System.Text.UTF8Encoding]::new($false))
$metrics = [ordered]@{
    schema_version = 1
    started_utc = $startedUtc.ToString("o")
    finished_utc = [DateTime]::UtcNow.ToString("o")
    wall_seconds = $timer.Elapsed.TotalSeconds
    peak_working_set_bytes = $peakWorkingSet
    exit_code = $process.ExitCode
    executable = $Executable
    arguments = $CommandArguments
    working_directory = $WorkingDirectory
}
[System.IO.File]::WriteAllText(
    $MetricsPath,
    ($metrics | ConvertTo-Json -Depth 4),
    [System.Text.UTF8Encoding]::new($false)
)
exit $process.ExitCode
