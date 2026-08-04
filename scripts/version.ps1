function Get-APISwitchVersion {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot
    )

    $versionSource = Join-Path $RepositoryRoot "backend\apiswitch\__init__.py"
    if (-not (Test-Path -LiteralPath $versionSource -PathType Leaf)) {
        throw "APISwitch version source is missing: $versionSource"
    }

    $match = [regex]::Match(
        (Get-Content -LiteralPath $versionSource -Raw),
        '(?m)^__version__\s*=\s*["'']([^"'']+)["'']\s*$'
    )
    if (-not $match.Success) {
        throw "Unable to read __version__ from $versionSource"
    }

    $version = $match.Groups[1].Value
    if ($version -notmatch '^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$') {
        throw "Invalid APISwitch version: $version"
    }
    return $version
}
