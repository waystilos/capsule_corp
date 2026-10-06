@echo off
setlocal
set "DIR=%~dp0.."
set "BIN=%DIR%\bin\capsule-go.exe"

if not exist "%BIN%" (
    pushd "%DIR%"
    go build -o "%BIN%" ./cmd/capsule
    popd
)

"%BIN%" %*
