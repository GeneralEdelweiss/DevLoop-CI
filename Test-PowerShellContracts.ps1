# Parse synthetic examples only; never invoke candidate scripts.
$ErrorActionPreference = 'Stop'
$valid = @'
param([string]$Name)
if ($Name -eq 'fixture') { Write-Output 'ok' }
'@
$invalid = @'
if ($true) { Write-Output 'missing brace'
'@
foreach ($case in @(@{Source=$valid; Valid=$true}, @{Source=$invalid; Valid=$false})) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseInput($case.Source,[ref]$tokens,[ref]$errors)
    if (($errors.Count -eq 0) -ne $case.Valid) { throw 'Unexpected parser result' }
}
$tokens = $null
$errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($PSCommandPath,[ref]$tokens,[ref]$errors)
if ($errors.Count -ne 0) { throw 'Self parser check failed' }
Write-Host 'POWERSHELL_CONTRACTS_PASS=True; valid/invalid synthetic parser controls'
