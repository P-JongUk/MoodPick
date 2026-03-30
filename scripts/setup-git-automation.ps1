param(
    [switch]$InitializeDevelop
)

$ErrorActionPreference = "Stop"

Write-Host "[1/3] Git hooks path 설정..."
git config core.hooksPath .githooks

Write-Host "[2/3] 실행 권한 준비(Windows에서는 필수 아님)..."
# Git for Windows는 실행 비트를 엄격히 요구하지 않지만, 유지보수를 위해 안내만 남깁니다.

Write-Host "[3/3] 브랜치 상태 점검..."
$hasDevelop = git branch --list develop

if (-not $hasDevelop -and $InitializeDevelop) {
    Write-Host "develop 브랜치가 없어 생성합니다."

    # origin/develop이 있으면 tracking으로 생성
    git fetch origin
    $hasRemoteDevelop = git branch -r --list origin/develop

    if ($hasRemoteDevelop) {
        git checkout -b develop --track origin/develop
    }
    else {
        git checkout -b develop
        git push -u origin develop
    }
}

Write-Host "완료: Git 자동화가 활성화되었습니다."
Write-Host "- hooksPath: .githooks"
Write-Host "- main 직접 커밋 차단 + 브랜치별 메시지 규칙 적용"
