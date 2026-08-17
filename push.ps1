# git remote add origin https://myrepos.stackroute.niit.com/1986713_Harshit/p1-student-management
# git remote set-url origin <REPO_URL>
# git add .
# git commit -m "your commit message here"
# git push -u origin main


# git remote -v




# ================================
# UPDATE THESE TWO VALUES ONLY
# ================================

$repoUrl = Read-Host "https://myrepos.stackroute.niit.com/1986713_Harshit/p1-student-management"
$commitMessage = Read-Host "Completed Student Management App"

# ================================
# DO NOT EDIT BELOW
# ================================

# Check if current folder is a git repo
if (-Not (Test-Path ".git")) {
    Write-Host "This folder is not a Git repository."
    exit
}

Write-Host "Current Directory: $(Get-Location)"

# Remove existing origin safely
git remote remove origin 2>$null

# Add new origin
git remote add origin $repoUrl

# Add all files
git add .

# Commit
git commit -m $commitMessage

# Detect current branch automatically
$currentBranch = git branch --show-current

# Push
git push -u origin $currentBranch

Write-Host "Push completed successfully."
