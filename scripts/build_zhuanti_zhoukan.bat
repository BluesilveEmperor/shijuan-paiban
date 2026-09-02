@echo off
REM build_zhuanti_zhoukan.bat - Build script for zhuanti/zhoukan templates
REM Usage: build_zhuanti_zhoukan.bat <work_dir> <output_name> <type> [version]
REM   work_dir: root directory containing templates folder
REM   output_name: output file prefix, e.g., "calculus_20260315" or "week5_math"
REM   type: zhuanti | zhoukan
REM   version: all / student / teacher / onepage (default all)

set WORK_DIR=%~1
set NAME=%~2
set TYPE=%~3
set VERSION=%~4

if "%WORK_DIR%"=="" (
    echo Error: work_dir not specified
    echo Usage: build_zhuanti_zhoukan.bat ^<work_dir^> ^<output_name^> ^<zhuanti|zhoukan^> [all|student|teacher|onepage]
    exit /b 1
)

if "%NAME%"=="" (
    echo Error: output_name not specified
    exit /b 1
)

if "%TYPE%"=="" (
    echo Error: type not specified (zhuanti or zhoukan)
    exit /b 1
)

if "%VERSION%"=="" set VERSION=all

REM Validate type
if /i not "%TYPE%"=="zhuanti" if /i not "%TYPE%"=="zhoukan" (
    echo Error: type must be zhuanti or zhoukan
    exit /b 1
)

REM Set template prefix
if /i "%TYPE%"=="zhuanti" (
    set PREFIX=zhuanti
) else (
    set PREFIX=zhoukan
)

cd /d "%WORK_DIR%\templates"

echo Compiling %NAME% (%TYPE%) ...

REM Determine versions to build
set VERSIONS_TO_BUILD=
if /i "%VERSION%"=="all" (
    set VERSIONS_TO_BUILD=student teacher onepage
) else (
    set VERSIONS_TO_BUILD=%VERSION%
)

REM First pass compilation
for %%v in (%VERSIONS_TO_BUILD%) do (
    echo   Compiling %%v ...
    xelatex -interaction=nonstopmode -output-directory="%WORK_DIR%\templates" "%PREFIX%_%%v.tex" >nul 2>&1
    if errorlevel 1 (
        echo   Warning: %%v first pass has errors, continuing to second pass...
    )
)

REM Second pass (resolve page references)
for %%v in (%VERSIONS_TO_BUILD%) do (
    echo   Compiling %%v (pass 2)...
    xelatex -interaction=nonstopmode -output-directory="%WORK_DIR%\templates" "%PREFIX%_%%v.tex"
)

REM Check Overfull
echo.
echo ==== Compilation Log Check ====
for %%v in (%VERSIONS_TO_BUILD%) do (
    echo --- %PREFIX%_%%v.log ---
    findstr /R /C:"Overfull" /C:"Error" "%WORK_DIR%\templates\%PREFIX%_%%v.log" 2>nul | findstr /V "infwarerr" || echo   No serious Overfull/Error
)

REM Clean aux files
del /q "%WORK_DIR%\templates\*.aux" "%WORK_DIR%\templates\*.log" "%WORK_DIR%\templates\*.out" 2>nul

REM Copy output files to work dir
for %%v in (%VERSIONS_TO_BUILD%) do (
    if exist "%WORK_DIR%\templates\%PREFIX%_%%v.pdf" (
        copy /y "%WORK_DIR%\templates\%PREFIX%_%%v.pdf" "%WORK_DIR%\%NAME%_%%v.pdf" >nul
        echo Generated: %WORK_DIR%\%NAME%_%%v.pdf
    )
)

echo.
echo Build completed!
echo PDF files location: %WORK_DIR%\
