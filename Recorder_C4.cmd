@ECHO OFF
SETLOCAL EnableDelayedExpansion
TITLE Select model:
:START
ECHO.
SET n=0
FOR /F "tokens=*" %%A IN (%~dp1C4_Model.txt) DO (
SET /A n=n+1
SET _fav!n!=%%A
ECHO !n! %%A
)
ECHO.
SET /P MODEL=Select Model (%M% %MODEL%): 
FOR /L %%f IN (1,1,!n!) DO (
IF /I '%MODEL%'=='%%f' SET M=%%f
)
SET n=0
FOR /F "tokens=*" %%A IN (%~dp1C4_Model.txt) DO (
SET /A n=n+1
IF !n!==%M% SET MODEL=%%A
)
SET UMODEL=%MODEL%
for /f "usebackq delims=" %%I in (`powershell "\"%MODEL%\".toUpper()"`) do set "UMODEL=%%~I"
:main
ECHO.
ECHO #####################################################
ECHO ### SHOWUP ###  R E C O R D I N G  -  2 4 / 7  ######
SET hour=%time:~0,2%
IF "%hour:~0,1%" == " " SET hour=0%hour:~1,1%
SET NOW=%date:~0,4%%date:~4,2%%date:~6,4%-%hour%%time:~3,2%%time:~6,2%
FOR /f "tokens=1-2 delims=/:" %%a IN ('time /t') DO (set mytime=%%a%%b)
SET OUT_DIR=%~dp1Capture\
SET FILENAME=%MODEL%_C4_%NOW%.mp4
SET OUTPUT=%OUT_DIR%%FILENAME%
SET FNAME=######## %FILENAME% ### %M% ##############################
SET _FNAME_=%FNAME:~5,53%
IF EXIST "%OUT_DIR%" (ECHO %_FNAME_%) ELSE (MD "%OUT_DIR%"
ECHO %_FNAME_%)
ECHO #####################################################
ECHO.
TITLE %UMODEL%
"%~dp1Streamlink_Portable\Streamlink.exe" "https://cam4.com/%MODEL%" 720p_alt,720p,best -o "%OUT_DIR%%FILENAME%"
TITLE %MODEL%

IF EXIST "%OUT_DIR%%FILENAME%" (
  SET /A WTIME=15 * %random% / 32767 + 22
) ELSE (
  SET /A WTIME=30 * %random% / 32767 + 45
)

TIMEOUT %WTIME%
GOTO main
ENDLOCAL
