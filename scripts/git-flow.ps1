param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("feat", "fix")]
    [string]$Type,

    [Parameter(Mandatory = $true)]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [string]$Message,

    [string]$BaseBranch = "develop",

    [switch]$Push
)

$ErrorActionPreference = "Stop"

function Require-GitClean {
    $status = git status --porcelain
    if ($status) {
        Write-Error "작업 트리가 깨끗하지 않습니다. 먼저 커밋/스태시 후 다시 실행하세요."
    }
}

function Ensure-BaseBranch {
    param([string]$Branch)

    git fetch origin
    $local = git branch --list $Branch
    $remote = git branch -r --list "origin/$Branch"

    if (-not $local) {
        if ($remote) {
            git checkout -b $Branch --track "origin/$Branch"
        }
        else {
            if ($Branch -eq "develop") {
                git checkout -b develop
                git push -u origin develop
            }
            else {
                Write-Error "기준 브랜치 '$Branch'가 로컬/원격에 없습니다."
            }
        }
    }
}

function Checkout-And-UpdateBase {
    param([string]$Branch)
    git checkout $Branch
    git pull --ff-only origin $Branch
}

function Ensure-WorkBranch {
    param([string]$BranchName, [string]$Base)

    $local = git branch --list $BranchName
    if ($local) {
        git checkout $BranchName
    }
    else {
        git checkout -b $BranchName $Base
    }
}

$branchName = "$Type/$Name"
$commitPrefix = "$Type($Name):"
$commitMessage = "$commitPrefix $Message"

Write-Host "[1/5] 사전 점검..."
Require-GitClean

Write-Host "[2/5] 기준 브랜치 준비: $BaseBranch"
Ensure-BaseBranch -Branch $BaseBranch
Checkout-And-UpdateBase -Branch $BaseBranch

Write-Host "[3/5] 작업 브랜치 준비: $branchName"
Ensure-WorkBranch -BranchName $branchName -Base $BaseBranch

Write-Host "[4/5] 변경사항 커밋"
git add -A

$hasChanges = git diff --cached --name-only
if (-not $hasChanges) {
    Write-Error "커밋할 변경사항이 없습니다."
}

git commit -m $commitMessage

if ($Push) {
    Write-Host "[5/5] 원격 브랜치 푸시"
    git push -u origin $branchName
}
else {
    Write-Host "[5/5] 푸시 생략 (옵션 -Push 미사용)"
}

Write-Host "완료"
Write-Host "- 브랜치: $branchName"
Write-Host "- 커밋: $commitMessage"
