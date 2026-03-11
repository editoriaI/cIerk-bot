$ErrorActionPreference = "Stop"

if (-not $args -or [string]::IsNullOrWhiteSpace($args[0])) {
  throw "Usage: .\scripts\new-pr.ps1 <branch-name>"
}

$branch = $args[0].Trim()

git show-ref --verify --quiet "refs/heads/$branch"
if ($LASTEXITCODE -eq 0) {
  throw "Branch already exists: $branch"
}

git checkout -b $branch
git status -sb
git push -u origin $branch

Write-Host ""
Write-Host "Next: open a PR on GitHub for branch '$branch'."
