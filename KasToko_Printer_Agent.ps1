# -*- coding: utf-8 -*-
# tools/KasToko_Printer_Agent.ps1 - Native Windows Hardware Print Agent KasToko
# Berjalan di SEMUA Windows (7, 8, 10, 11) TANPA PERLU INSTALL PYTHON ATAU MODUL APAPUN.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "SilentlyContinue"

# Inisialisasi P/Invoke Winspool & Grafis .NET
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies "System.Drawing" -TypeDefinition @"
using System;
using System.IO;
using System.Drawing;
using System.Runtime.InteropServices;

public class PrinterHelper {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    public class DOCINFOA {
        [MarshalAs(UnmanagedType.LPStr)] public string pDocName;
        [MarshalAs(UnmanagedType.LPStr)] public string pOutputFile;
        [MarshalAs(UnmanagedType.LPStr)] public string pDataType;
    }
    [DllImport("winspool.drv", EntryPoint = "OpenPrinterA", SetLastError = true, CharSet = CharSet.Ansi, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
    public static extern bool OpenPrinter([MarshalAs(UnmanagedType.LPStr)] string szPrinter, out IntPtr hPrinter, IntPtr pd);

    [DllImport("winspool.drv", EntryPoint = "ClosePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
    public static extern bool ClosePrinter(IntPtr hPrinter);

    [DllImport("winspool.drv", EntryPoint = "StartDocPrinterA", SetLastError = true, CharSet = CharSet.Ansi, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
    public static extern bool StartDocPrinter(IntPtr hPrinter, Int32 level, [In, MarshalAs(UnmanagedType.LPStruct)] DOCINFOA di);

    [DllImport("winspool.drv", EntryPoint = "EndDocPrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
    public static extern bool EndDocPrinter(IntPtr hPrinter);

    [DllImport("winspool.drv", EntryPoint = "StartPagePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
    public static extern bool StartPagePrinter(IntPtr hPrinter);

    [DllImport("winspool.drv", EntryPoint = "EndPagePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
    public static extern bool EndPagePrinter(IntPtr hPrinter);

    [DllImport("winspool.drv", EntryPoint = "WritePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
    public static extern bool WritePrinter(IntPtr hPrinter, IntPtr pBytes, Int32 dwCount, out Int32 dwWritten);

    public static bool SendBytes(string szPrinterName, byte[] pBytes, string docName) {
        if (pBytes == null || pBytes.Length == 0) return false;
        IntPtr pUnmanagedBytes = Marshal.AllocCoTaskMem(pBytes.Length);
        Marshal.Copy(pBytes, 0, pUnmanagedBytes, pBytes.Length);
        IntPtr hPrinter;
        DOCINFOA di = new DOCINFOA();
        di.pDocName = docName;
        di.pDataType = "RAW";
        bool bSuccess = false;
        if (OpenPrinter(szPrinterName, out hPrinter, IntPtr.Zero)) {
            if (StartDocPrinter(hPrinter, 1, di)) {
                if (StartPagePrinter(hPrinter)) {
                    int dwWritten = 0;
                    bSuccess = WritePrinter(hPrinter, pUnmanagedBytes, pBytes.Length, out dwWritten);
                    EndPagePrinter(hPrinter);
                }
                EndDocPrinter(hPrinter);
            }
            ClosePrinter(hPrinter);
        }
        Marshal.FreeCoTaskMem(pUnmanagedBytes);
        return bSuccess;
    }

    public static byte[] ImageToTspl(byte[] imageBytes, int targetWidth) {
        using (MemoryStream ms = new MemoryStream(imageBytes))
        using (Bitmap orig = new Bitmap(ms)) {
            int targetHeight = (int)((float)targetWidth / orig.Width * orig.Height);
            using (Bitmap resized = new Bitmap(targetWidth, targetHeight)) {
                using (Graphics g = Graphics.FromImage(resized)) {
                    g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                    g.DrawImage(orig, 0, 0, targetWidth, targetHeight);
                }

                int widthBytes = (targetWidth + 7) / 8;
                byte[] bitmapData = new byte[widthBytes * targetHeight];
                for (int y = 0; y < targetHeight; y++) {
                    for (int x = 0; x < targetWidth; x++) {
                        Color c = resized.GetPixel(x, y);
                        int gray = (int)(0.299 * c.R + 0.587 * c.G + 0.114 * c.B);
                        if (gray < 175) {
                            int byteIdx = (y * widthBytes) + (x / 8);
                            int bitIdx = 7 - (x % 8);
                            bitmapData[byteIdx] |= (byte)(1 << bitIdx);
                        }
                    }
                }

                int h_mm = Math.Max(20, (int)Math.Round(targetHeight / 8.0));
                int w_mm = (int)Math.Round(targetWidth / 8.0);
                string header = "SIZE " + w_mm + " mm," + h_mm + " mm\nGAP 0 mm,0 mm\nDIRECTION 1\nREFERENCE 0,0\nCLS\nBITMAP 0,0," + widthBytes + "," + targetHeight + ",0,";
                byte[] headerBytes = System.Text.Encoding.ASCII.GetBytes(header);
                byte[] footerBytes = System.Text.Encoding.ASCII.GetBytes("\nPRINT 1,1\n");

                byte[] result = new byte[headerBytes.Length + bitmapData.Length + footerBytes.Length];
                Buffer.BlockCopy(headerBytes, 0, result, 0, headerBytes.Length);
                Buffer.BlockCopy(bitmapData, 0, result, headerBytes.Length, bitmapData.Length);
                Buffer.BlockCopy(footerBytes, 0, result, headerBytes.Length + bitmapData.Length, footerBytes.Length);
                return result;
            }
        }
    }

    public static byte[] ImageToEscPos(byte[] imageBytes, int targetWidth) {
        using (MemoryStream ms = new MemoryStream(imageBytes))
        using (Bitmap orig = new Bitmap(ms)) {
            int targetHeight = (int)((float)targetWidth / orig.Width * orig.Height);
            using (Bitmap resized = new Bitmap(targetWidth, targetHeight)) {
                using (Graphics g = Graphics.FromImage(resized)) {
                    g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                    g.DrawImage(orig, 0, 0, targetWidth, targetHeight);
                }

                int widthBytes = (targetWidth + 7) / 8;
                byte[] bitmapData = new byte[widthBytes * targetHeight];
                for (int y = 0; y < targetHeight; y++) {
                    for (int x = 0; x < targetWidth; x++) {
                        Color c = resized.GetPixel(x, y);
                        int gray = (int)(0.299 * c.R + 0.587 * c.G + 0.114 * c.B);
                        if (gray < 175) {
                            int byteIdx = (y * widthBytes) + (x / 8);
                            int bitIdx = 7 - (x % 8);
                            bitmapData[byteIdx] |= (byte)(1 << bitIdx);
                        }
                    }
                }

                byte xL = (byte)(widthBytes & 0xFF);
                byte xH = (byte)((widthBytes >> 8) & 0xFF);
                byte yL = (byte)(targetHeight & 0xFF);
                byte yH = (byte)((targetHeight >> 8) & 0xFF);

                byte[] initCmd = new byte[] { 0x1B, 0x40 };
                byte[] bitCmd = new byte[] { 0x1D, 0x76, 0x30, 0x00, xL, xH, yL, yH };
                byte[] feedCmd = new byte[] { 0x1B, 0x64, 0x03, 0x1D, 0x56, 0x00 };

                byte[] result = new byte[initCmd.Length + bitCmd.Length + bitmapData.Length + feedCmd.Length];
                int offset = 0;
                Buffer.BlockCopy(initCmd, 0, result, offset, initCmd.Length); offset += initCmd.Length;
                Buffer.BlockCopy(bitCmd, 0, result, offset, bitCmd.Length); offset += bitCmd.Length;
                Buffer.BlockCopy(bitmapData, 0, result, offset, bitmapData.Length); offset += bitmapData.Length;
                Buffer.BlockCopy(feedCmd, 0, result, offset, feedCmd.Length);
                return result;
            }
        }
    }
}
"@

# Lokasi konfigurasi
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
$configFile = Join-Path $scriptDir "config.json"
$appDataDir = Join-Path $env:USERPROFILE ".kastoko_agent"
$appDataConfig = Join-Path $appDataDir "config.json"

$centralServer = "https://autocash.dhanzcell.my.id"
$deviceId = ""
$pairingCode = ""

# Muat config jika ada
if (Test-Path $configFile) {
    try {
        $json = Get-Content $configFile -Raw | ConvertFrom-Json
        if ($json.central_server) { $centralServer = $json.central_server }
        if ($json.device_id) { $deviceId = $json.device_id }
        if ($json.pairing_code) { $pairingCode = $json.pairing_code }
    } catch {}
}
if (-not $deviceId -and (Test-Path $appDataConfig)) {
    try {
        $json = Get-Content $appDataConfig -Raw | ConvertFrom-Json
        if ($json.central_server) { $centralServer = $json.central_server }
        if ($json.device_id) { $deviceId = $json.device_id }
        if ($json.pairing_code) { $pairingCode = $json.pairing_code }
    } catch {}
}

# JIKA BELUM ADA DEVICE ID, OTOMATIS GENERATE ID PERMANEN (JANGAN PERNAH PAUSE ATAU TANYA USER)
if (-not $deviceId) {
    $compClean = ($env:COMPUTERNAME -replace '[^a-zA-Z0-9]','').ToLower()
    $deviceId = "dev_" + $compClean + "_" + [System.Guid]::NewGuid().ToString("N").Substring(0, 8)
    try {
        New-Item -ItemType Directory -Force $appDataDir | Out-Null
        $cfgJson = @{ central_server = $centralServer; device_id = $deviceId; machine_name = $env:COMPUTERNAME } | ConvertTo-Json
        $cfgJson | Set-Content $appDataConfig -Encoding UTF8
        $cfgJson | Set-Content $configFile -Encoding UTF8
    } catch {}
}

function Get-LocalPrintersList {
    $pList = @()
    $rawPrinters = Get-CimInstance Win32_Printer -ErrorAction SilentlyContinue
    if (-not $rawPrinters) {
        $rawPrinters = Get-WmiObject Win32_Printer -ErrorAction SilentlyContinue
    }
    foreach ($p in $rawPrinters) {
        $isDef = [bool]$p.Default
        $pList += @{
            name = $p.Name
            port = if ($p.PortName) { $p.PortName } else { "USB" }
            driver = if ($p.DriverName) { $p.DriverName } else { "" }
            is_default = $isDef
        }
    }
    return $pList
}

$printers = Get-LocalPrintersList
$defaultPrinter = ($printers | Where-Object { $_.is_default -eq $true } | Select-Object -First 1).name
if (-not $defaultPrinter -and $printers.Count -gt 0) {
    $defaultPrinter = $printers[0].name
}

Clear-Host
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "        KASTOKO - LOCAL HARDWARE PRINTER AGENT (WINDOWS)        " -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "Komputer Kasir : $env:COMPUTERNAME" -ForegroundColor White
Write-Host "Device ID      : $deviceId" -ForegroundColor White
Write-Host "Server Pusat   : $centralServer" -ForegroundColor Gray
Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Daftar Printer Fisik di PC ini ($($printers.Count) printer):" -ForegroundColor Green
if ($printers.Count -eq 0) {
    Write-Host "  [!] Belum ada printer terdeteksi di Windows." -ForegroundColor Red
    Write-Host "      Pastikan kabel USB printer thermal terhubung & printer menyala." -ForegroundColor Yellow
} else {
    $i = 1
    foreach ($p in $printers) {
        $defTag = if ($p.is_default) { " [DEFAULT]" } else { "" }
        Write-Host "  [$i] $($p.name) (Port: $($p.port))$defTag" -ForegroundColor White
        $i++
    }
}
Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan

# 1. Start Local HTTP Server di Port 18080 (Browser Direct Access)
$localListener = $null
try {
    $localListener = New-Object System.Net.HttpListener
    $localListener.Prefixes.Add("http://127.0.0.1:18080/")
    $localListener.Start()
    Write-Host "Koneksi Lokal  : 🟢 Port 18080 Aktif (Browser terhubung instan)" -ForegroundColor Green
} catch {
    Write-Host "Koneksi Lokal  : Port 18080 sedang dipakai (Menggunakan Cloud Relay)" -ForegroundColor DarkGray
    $localListener = $null
}

# 2. Pendaftaran Awal ke Server Pusat
function Register-Agent {
    try {
        $pArr = @(Get-LocalPrintersList)
        $regBody = @{
            device_id = $deviceId
            pairing_code = $pairingCode
            machine_name = $env:COMPUTERNAME
            printers = $pArr
            default = $defaultPrinter
        } | ConvertTo-Json -Depth 4

        Invoke-RestMethod -Uri "$centralServer/api/printer-agent/register" -Method Post -Body $regBody -ContentType "application/json" -UserAgent "KasTokoPrinterAgent/1.0" -TimeoutSec 4 | Out-Null
        return $true
    } catch {
        return $false
    }
}

$regOk = Register-Agent
if ($regOk) {
    Write-Host "Cloud Relay    : 🟢 Terdaftar ke Server Pusat (NAT/Firewall Bypass)" -ForegroundColor Green
} else {
    Write-Host "Cloud Relay    : 🟡 Menghubungkan ke server pusat..." -ForegroundColor Yellow
}

Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "STATUS         : 🟢 SIAP MENERIMA PERINTAH CETAK!" -ForegroundColor Green
Write-Host ">> Biarkan jendela ini tetap terbuka / minimize selama bekerja <<" -ForegroundColor Yellow
Write-Host "================================================================`n" -ForegroundColor Cyan

function Execute-PrintJob($jobData, $jobType, $targetPrinter) {
    $pName = if ($targetPrinter) { $targetPrinter } else { $defaultPrinter }
    if (-not $pName -and $printers.Count -gt 0) { $pName = $printers[0].name }
    if (-not $pName) { return @{ success = $false; message = "Tidak ada printer thermal terpasang di PC ini" } }

    $printSuccess = $false
    $errorMsg = ""
    try {
        if ($jobType -eq "test" -or $jobData.test -eq $true) {
            $isLabelTest = ($jobData.type -eq "label" -or $pName.ToLower().Contains("label"))
            if ($isLabelTest) {
                $tsplCmd = "SIZE 40 mm,30 mm`nGAP 2 mm,0 mm`nDIRECTION 1`nREFERENCE 0,0`nCLS`nTEXT 20,20,`"3`",0,1,1,`"KASTOKO AGENT`"`nTEXT 20,60,`"2`",0,1,1,`"$env:COMPUTERNAME`"`nTEXT 20,95,`"2`",0,1,1,`"Status: TERHUBUNG`"`nBARCODE 20,130,`"128`",40,1,0,2,2,`"TEST-OK`"`nPRINT 1,1`n"
                $bytes = [System.Text.Encoding]::ASCII.GetBytes($tsplCmd)
                $printSuccess = [PrinterHelper]::SendBytes($pName, $bytes, "Test Stiker Label")
            } else {
                $escText = [char]0x1B + "@" + [char]0x1B + "a" + [char]1 + [char]0x1B + "E" + [char]1 + "KASTOKO PRINT AGENT" + [char]0x1B + "E" + [char]0 + "`n" +
                           "================================`n" +
                           "UJI KONEKSI PRINTER LOKAL`n" +
                           "PC Klien : $env:COMPUTERNAME`n" +
                           "Printer  : $pName`n" +
                           "Waktu    : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n" +
                           "Status   : BERHASIL TERHUBUNG!`n" +
                           "================================`n`n`n`n" +
                           [char]0x1D + "V" + [char]0
                $bytes = [System.Text.Encoding]::GetEncoding("ISO-8859-1").GetBytes($escText)
                $printSuccess = [PrinterHelper]::SendBytes($pName, $bytes, "Test Cetak Thermal")
            }
        } elseif ($jobData.image_data) {
            $imgBase64 = [string]$jobData.image_data
            if ($imgBase64.Contains(",")) {
                $imgBase64 = $imgBase64.Substring($imgBase64.IndexOf(",") + 1)
            }
            $rawImgBytes = [System.Convert]::FromBase64String($imgBase64)
            $pWidthStr = if ($jobData.paper_width) { "$($jobData.paper_width)" } else { "78" }
            $isTspl = ($pWidthStr.Contains("78") -or $pName.ToLower().Contains("label") -or $jobData.mode -eq "tspl")

            if ($isTspl) {
                $tsplBytes = [PrinterHelper]::ImageToTspl($rawImgBytes, 576)
                $printSuccess = [PrinterHelper]::SendBytes($pName, $tsplBytes, "KasToko Stiker Label")
            } else {
                $targetWidthPx = if ($pWidthStr -eq "58") { 384 } else { 576 }
                $escBytes = [PrinterHelper]::ImageToEscPos($rawImgBytes, $targetWidthPx)
                $printSuccess = [PrinterHelper]::SendBytes($pName, $escBytes, "KasToko Nota Kasir")
            }
        } else {
            $fallbackText = [char]0x1B + "@" + [char]0x1B + "a" + [char]1 + "KASTOKO RECEIPT`n`n`n`n" + [char]0x1D + "V" + [char]0
            $bytes = [System.Text.Encoding]::ASCII.GetBytes($fallbackText)
            $printSuccess = [PrinterHelper]::SendBytes($pName, $bytes, "KasToko Nota Kasir")
        }
    } catch {
        $printSuccess = $false
        $errorMsg = $_.Exception.Message
    }

    if ($printSuccess) {
        Write-Host "  [OK] Cetak berhasil -> '$pName'!" -ForegroundColor Green
    } else {
        Write-Host "  [ERR] Gagal mencetak ke '$pName': $errorMsg" -ForegroundColor Red
    }

    return @{
        success = $printSuccess
        message = if ($printSuccess) { "Nota berhasil dicetak langsung ke printer '$pName' di PC ini!" } else { "Gagal mencetak: $errorMsg" }
    }
}

# Loop Utama
$asyncContext = $null
$lastHeartbeat = [DateTime]::UtcNow
$lastCloudPoll = [DateTime]::UtcNow

while ($true) {
    # 1. Layani Request Browser Lokal di Port 18080 (CORS + PNA Private Network Access)
    if ($localListener -and $localListener.IsListening) {
        if ($null -eq $asyncContext) {
            try { $asyncContext = $localListener.BeginGetContext($null, $null) } catch {}
        }
        if ($asyncContext -and $asyncContext.IsCompleted) {
            try {
                $ctx = $localListener.EndGetContext($asyncContext)
                $asyncContext = $null

                # Headers CORS Lengkap untuk HTTPS -> HTTP localhost (Chrome/Edge/Firefox)
                $ctx.Response.Headers.Add("Access-Control-Allow-Origin", "*")
                $ctx.Response.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                $ctx.Response.Headers.Add("Access-Control-Allow-Headers", "*")
                $ctx.Response.Headers.Add("Access-Control-Allow-Private-Network", "true")

                $path = $ctx.Request.Url.AbsolutePath
                if ($ctx.Request.HttpMethod -eq "OPTIONS") {
                    $ctx.Response.StatusCode = 204
                    $ctx.Response.Close()
                } elseif ($path -eq "/api/printers") {
                    $pArr = @(Get-LocalPrintersList)
                    $respBody = @{
                        success = $true
                        printers = $pArr
                        default = $defaultPrinter
                        machine_name = $env:COMPUTERNAME
                        device_id = $deviceId
                        source = "local_agent"
                    } | ConvertTo-Json -Depth 4
                    $b = [System.Text.Encoding]::UTF8.GetBytes($respBody)
                    $ctx.Response.ContentType = "application/json"
                    $ctx.Response.OutputStream.Write($b, 0, $b.Length)
                    $ctx.Response.Close()
                } elseif ($path.StartsWith("/api/print")) {
                    $reader = New-Object System.IO.StreamReader($ctx.Request.InputStream, [System.Text.Encoding]::UTF8)
                    $bodyStr = $reader.ReadToEnd()
                    $pData = $bodyStr | ConvertFrom-Json
                    $targetP = if ($pData.printer_name) { $pData.printer_name } else { $defaultPrinter }
                    $jType = if ($path.Contains("label")) { "label" } elseif ($path.Contains("receipt")) { "receipt" } else { "direct" }
                    Write-Host "[PRINT LOKAL] Menerima cetak -> '$targetP'..." -ForegroundColor Yellow

                    $pRes = Execute-PrintJob -jobData $pData -jobType $jType -targetPrinter $targetP
                    $respBody = $pRes | ConvertTo-Json
                    $b = [System.Text.Encoding]::UTF8.GetBytes($respBody)
                    $ctx.Response.ContentType = "application/json"
                    $ctx.Response.OutputStream.Write($b, 0, $b.Length)
                    $ctx.Response.Close()
                } else {
                    $ctx.Response.StatusCode = 404
                    $ctx.Response.Close()
                }
            } catch {}
        }
    }

    # 2. Heartbeat Cloud Relay setiap 15 detik
    if (([DateTime]::UtcNow - $lastHeartbeat).TotalSeconds -ge 15) {
        Register-Agent | Out-Null
        $lastHeartbeat = [DateTime]::UtcNow
    }

    # 3. Poll Cloud Job Queue dari Server Pusat setiap 1.2 detik
    if (([DateTime]::UtcNow - $lastCloudPoll).TotalMilliseconds -ge 1200) {
        $lastCloudPoll = [DateTime]::UtcNow
        try {
            $pollUrl = "$centralServer/api/printer-agent/jobs?device_id=$deviceId"
            $pollRes = Invoke-RestMethod -Uri $pollUrl -Method Get -UserAgent "KasTokoPrinterAgent/1.0" -TimeoutSec 3
            if ($pollRes.has_job -and $pollRes.job) {
                $job = $pollRes.job
                $jobId = $job.job_id
                $pName = if ($job.printer_name) { $job.printer_name } else { $defaultPrinter }
                $jobType = $job.type
                $jobData = $job.data

                Write-Host "[PRINT CLOUD] Menerima tugas ($jobType) -> '$pName'..." -ForegroundColor Yellow
                $pRes = Execute-PrintJob -jobData $jobData -jobType $jobType -targetPrinter $pName

                # Lapor hasil cetak ke server pusat
                try {
                    $finishBody = @{
                        job_id = $jobId
                        success = $pRes.success
                        message = $pRes.message
                    } | ConvertTo-Json
                    Invoke-RestMethod -Uri "$centralServer/api/printer-agent/jobs/finish" -Method Post -Body $finishBody -ContentType "application/json" -UserAgent "KasTokoPrinterAgent/1.0" -TimeoutSec 4 | Out-Null
                } catch {}
            }
        } catch {}
    }

    Start-Sleep -Milliseconds 100
}
