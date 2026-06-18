<#
.SYNOPSIS
Native Clone Hero Downcharter - Replaces EasyChartGenerator.exe entirely.
#>

param (
    [bool]$ForceReplace = $true,
    [bool]$ScanAllExpert = $false
)

# --- BEGIN CLONE HERO DIRECTORY SETUP ---

# Define the config file name (saves in the same folder you run the script from)
$configFile = ".\CH_Settings.txt"
$songsDirectory = $null

# 1. Try to read the directory from the config file if it exists
if (Test-Path $configFile) {
    # Force the result into an array @(...) so [0] grabs the first line, not the first letter
    $validLines = @(Get-Content $configFile | Where-Object { $_ -match '\S' -and $_ -notmatch '^\s*#' })
    if ($validLines.Count -gt 0) {
        $songsDirectory = $validLines[0].Trim()
    }
}

# 2. Check if the directory we found actually exists
$isValidDir = $false
if (-not [string]::IsNullOrWhiteSpace($songsDirectory) -and (Test-Path $songsDirectory -PathType Container)) {
    $isValidDir = $true
    Write-Host "Loaded Songs directory from CH_Settings.txt:" -ForegroundColor Cyan
    Write-Host "$songsDirectory`n" -ForegroundColor DarkGray
}

# 3. If missing or invalid, prompt the user with the modern GUI
if (-not $isValidDir) {
    Write-Host "First time setup: Please select your Clone Hero 'songs' folder from the popup window..." -ForegroundColor Cyan
    
    # Use Add-Type to compile a quick C# wrapper for the modern Windows IFileDialog
    $csharpCode = @"
using System;
using System.Runtime.InteropServices;

public class ModernFolderPicker
{
    [ComImport, Guid("DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7")]
    private class FileOpenDialog { }

    [ComImport, Guid("42f85136-db7e-439c-85f1-e4075d135fc8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IFileDialog
    {
        [PreserveSig] uint Show([In] IntPtr parent);
        void SetFileTypes(); void SetFileTypeIndex(); void GetFileTypeIndex(); void Advise(); void Unadvise();
        void SetOptions([In] uint fos); void GetOptions([Out] out uint fos);
        void SetDefaultFolder(); void SetFolder(); void GetFolder(); void GetCurrentSelection();
        void SetFileName(); void GetFileName();
        void SetTitle([In, MarshalAs(UnmanagedType.LPWStr)] string pszTitle);
        void SetOkButtonLabel(); void SetFileNameLabel();
        void GetResult([MarshalAs(UnmanagedType.Interface)] out IShellItem ppsi);
        void AddPlace(); void SetDefaultExtension(); void Close(); void SetClientGuid(); void ClearClientData(); void SetFilter();
    }

    [ComImport, Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellItem
    {
        void BindToHandler(); void GetParent();
        void GetDisplayName([In] uint sigdnName, [MarshalAs(UnmanagedType.LPWStr)] out string ppszName);
        void GetAttributes(); void Compare();
    }

    public static string PickFolder(string title)
    {
        try {
            var dialog = (IFileDialog)new FileOpenDialog();
            dialog.SetTitle(title);
            
            // Refactored for C# 5.0 compatibility
            uint options;
            dialog.GetOptions(out options);
            dialog.SetOptions(options | 0x00000020); // FOS_PICKFOLDERS
            
            if (dialog.Show(IntPtr.Zero) == 0) // S_OK
            {
                IShellItem shellItem;
                dialog.GetResult(out shellItem);
                
                string path;
                shellItem.GetDisplayName(0x80058000, out path); // SIGDN_FILESYSPATH
                return path;
            }
        } catch { }
        return null;
    }
}
"@
    
    # Load the class (checking if it exists first so it doesn't crash on repeated tests)
    if (-not ([System.Management.Automation.PSTypeName]'ModernFolderPicker').Type) {
        Add-Type -TypeDefinition $csharpCode
    }
    
    $songsDirectory = [ModernFolderPicker]::PickFolder("Select your Clone Hero 'songs' folder")
    
    if ([string]::IsNullOrWhiteSpace($songsDirectory)) {
        Write-Host "`nFolder selection cancelled. Exiting." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit
    }

    # 4. Generate the config file for Notepad editing later
    $configTemplate = @"
# Clone Hero Batch-EasyChart Configuration
# You can safely edit the path below using Notepad.
# Just make sure it points to your actual Clone Hero Songs directory.

$($songsDirectory)
"@
    # Save it to the text file
    $configTemplate | Out-File -FilePath $configFile -Encoding UTF8
    Write-Host "`nSaved! You can change this path anytime by editing $configFile in Notepad.`n" -ForegroundColor Green
}

# --- END CLONE HERO DIRECTORY SETUP ---

if (-not (Test-Path $songsDirectory)) {
    Write-Host "ERROR: Cannot find your Songs folder at $songsDirectory" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit
}
Write-Host "Clone Hero Difficulty Creator v1.0.1 initialized..."
Write-Host ""
Write-Host "Scanning charts in $songsDirectory..." -ForegroundColor Cyan
$targetFolders = @()

$chartFiles = Get-ChildItem -Path $songsDirectory -Filter "*.chart" -Recurse

# 1. SCAN AND FILTER
foreach ($file in $chartFiles) {
    $content = [System.IO.File]::ReadAllText($file.FullName)
    
    $hasExpert = $content -match '\[Expert[A-Za-z]*\]'
    $hasLower  = $content -match '\[(Hard|Medium|Easy)[A-Za-z]*\]'
    
    if ($hasExpert) {
        if ($ScanAllExpert -or -not $hasLower) {
            $targetFolders += [pscustomobject]@{
                SongName  = $file.Directory.Name
                ChartFile = $file.FullName
            }
        }
    }
}

if ($targetFolders.Count -eq 0) {
    Write-Host "No matching charts found!" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit
}

# 2. GUI SELECTOR
Write-Host "Found $($targetFolders.Count) matching charts." -ForegroundColor Green
$selected = $targetFolders | Out-GridView -Title "Select Charts to Natively Downchart" -PassThru

if (-not $selected) {
    Write-Host "No charts selected. Exiting." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit
}

# 3. CORE LOGIC FUNCTION
function Get-DownchartedNotes {
    param([string]$notesData, [string]$difficulty, [int]$resolution)
    
    $lines = $notesData -split "`n"
    $newLines = @()
    
    $lastAcceptedTick = -99999
    $acceptedTicks = @{} 
    
    foreach ($line in $lines) {
        $line = $line.Trim("`r")
        
        # Match note line: "  Tick = N Color Length"
        if ($line -match '^\s*(\d+)\s*=\s*N\s+(\d+)\s+(\d+)') {
            $tick = [int]$matches[1]
            $color = [int]$matches[2]
            $length = [int]$matches[3]
            
            # Strip HOPO/Strum forces (5 and 6) on lower difficulties
            if ($color -eq 5 -or $color -eq 6) {
                if ($difficulty -eq "Hard") { $newLines += "  $tick = N $color $length" }
                continue
            }
            
            # Normal Frets (0-4) and Open Notes (7)
            if ($color -le 4 -or $color -eq 7) {
                
                # COLOR DOWN-MAPPING
                if ($difficulty -eq "Medium" -and $color -eq 4) { $color = 3 }
                if ($difficulty -eq "Easy" -and $color -ge 3 -and $color -ne 7) { $color = 2 }
                
                # TICK DISTANCE (THINNING OUT FAST SECTIONS)
                if (-not $acceptedTicks.ContainsKey($tick)) {
                    $distance = $tick - $lastAcceptedTick
                    $skipTick = $false
                    
                    # Easy: Max speed is Quarter Notes (1x Resolution)
                    if ($difficulty -eq "Easy" -and $distance -lt $resolution) { $skipTick = $true }
                    # Medium: Max speed is 8th Notes (0.5x Resolution)
                    if ($difficulty -eq "Medium" -and $distance -lt ($resolution / 2)) { $skipTick = $true }
                    
                    if ($skipTick) {
                        continue # Drop note because it's too fast
                    } else {
                        $acceptedTicks[$tick] = @()
                        $lastAcceptedTick = $tick
                    }
                }
                
                # If tick wasn't accepted, drop the note
                if (-not $acceptedTicks.ContainsKey($tick)) { continue }
                
                # CHORD LIMITS
                if ($acceptedTicks[$tick] -contains $color) { continue } # Prevent duplicate colors
                if ($difficulty -eq "Easy" -and $acceptedTicks[$tick].Count -ge 1) { continue } # Single notes only
                if ($difficulty -eq "Medium" -and $acceptedTicks[$tick].Count -ge 2) { continue } # Max 2-note chords
                
                $acceptedTicks[$tick] += $color
                $newLines += "  $tick = N $color $length"
            } else {
                # Keep odd note types intact just in case
                $newLines += "  $tick = N $color $length"
            }
        } else {
            # Keep Star Power, Events, and curly braces intact
            if ($line.Trim() -ne "") { $newLines += $line }
        }
    }
    return $newLines -join "`n"
}


# 4. EXECUTE FILE OVERWRITES
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

foreach ($item in $selected) {
    Write-Host "Rewriting: $($item.SongName)..." -ForegroundColor Cyan
    
    $content = [System.IO.File]::ReadAllText($item.ChartFile)
    
    # Grab song resolution for math (Defaults to 192 if not found)
    $resolution = 192
    if ($content -match '(?m)^\s*Resolution\s*=\s*(\d+)') {
        $resolution = [int]$matches[1]
    }
    
    # Strip existing Hard/Medium/Easy blocks if ForceReplace is True
    if ($ForceReplace) {
        $content = $content -replace '(?m)^\[(Hard|Medium|Easy)[A-Za-z]+\]\r?\n\{\r?\n[\s\S]*?\r?\n\}\r?\n?', ''
    }
    
    # Find all Expert blocks (Single, DoubleBass, Keys, etc.)
    $pattern = '(?m)^\[Expert([A-Za-z]+)\]\r?\n\{\r?\n([\s\S]*?)\r?\n\}'
    $expertBlocks = [regex]::Matches($content, $pattern)
    
    $newBlocks = ""
    
    foreach ($match in $expertBlocks) {
        $instrument = $match.Groups[1].Value
        $notesData = $match.Groups[2].Value
        
        $hardNotes = Get-DownchartedNotes -notesData $notesData -difficulty "Hard" -resolution $resolution
        $mediumNotes = Get-DownchartedNotes -notesData $notesData -difficulty "Medium" -resolution $resolution
        $easyNotes = Get-DownchartedNotes -notesData $notesData -difficulty "Easy" -resolution $resolution
        
        $newBlocks += "`n[Hard$instrument]`n{`n$hardNotes`n}"
        $newBlocks += "`n[Medium$instrument]`n{`n$mediumNotes`n}"
        $newBlocks += "`n[Easy$instrument]`n{`n$easyNotes`n}"
    }
    
    # Append the newly generated difficulties to the file
    $finalContent = $content.TrimEnd() + "`n" + $newBlocks + "`n"
    
    [System.IO.File]::WriteAllText($item.ChartFile, $finalContent, $utf8NoBom)
    
    Write-Host "Success: $($item.SongName) fully downcharted!" -ForegroundColor Green
}

Write-Host "`nBatch process complete! You can delete EasyChartGenerator.exe." -ForegroundColor Magenta
Read-Host "Press Enter to exit"