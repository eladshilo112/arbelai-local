$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Bundle = Split-Path -Parent $PSScriptRoot
Write-Host "ARBELAI Local, אשף התקנה בטוח" -ForegroundColor Cyan
Write-Host "האפליקציה תבדוק תחילה את המחשב. לא תתבצע הורדה או עריכת תצורה בלי אישור."
Write-Host "ברירת המחדל היא Local Only וללא Telemetry. לא ייפתח פורט קבוע."
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    Write-Host "Python 3 אינו מותקן. ניתן להתקין אותו ממקור Microsoft המאומת באמצעות winget."
    $Approval = Read-Host "להתקין Python 3? הקלד כן"
    if ($Approval -ne 'כן') { Write-Host "לא בוצע שינוי."; exit 2 }
    $Winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $Winget) { Write-Host "winget אינו זמין. התקן Python 3 מהאתר הרשמי והפעל שוב."; exit 3 }
    winget install --id Python.Python.3.12 --exact --source winget --scope user
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Python) { Write-Host "ההתקנה הסתיימה. פתח מחדש את הקובץ לאחר כניסה מחדש למערכת."; exit 4 }
}
$Choice = Read-Host "בחר: 1 בדיקה בלבד, 2 התקנה מונחית, 3 מסלול מתקדם"
$Target = Join-Path $env:USERPROFILE 'ARBELAI_COMPUTE_NODE'
if ($Choice -eq '1') {
    & $Python.Source (Join-Path $Bundle 'portable.py') bootstrap --target $Target --dry-run
} elseif ($Choice -eq '3') {
    Write-Host "מסלול מתקדם: ניתן לבחור יעד. כל הורדה וחיבור עדיין דורשים אישור."
    $Custom = Read-Host "נתיב התקנה, או Enter לברירת המחדל"
    if ($Custom) { $Target = $Custom }
    & $Python.Source (Join-Path $Bundle 'portable.py') bootstrap --target $Target
} else {
    & $Python.Source (Join-Path $Bundle 'portable.py') bootstrap --target $Target
}
$Code = $LASTEXITCODE
if ($Code -eq 0) { Write-Host "התהליך הסתיים. דוח הסיום נמצא בתיקיית reports." -ForegroundColor Green }
exit $Code
