param(
  [int]$Tail = 200
)

# Convenience wrapper so you can run this from repo root.
& "$PSScriptRoot\scripts\show_local_errors.ps1" -Tail $Tail
