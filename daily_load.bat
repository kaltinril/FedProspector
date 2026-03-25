@echo off
echo ============================================
echo   FedProspect Daily Data Load
echo   %date% %time%
echo ============================================
echo.

set NAICS=336611,488190,519210,541219,541330,541511,541512,541513,541519,541611,541612,541613,541690,541990,561110,561210,561510,561990,611430,611710,621111,621399,624190,812910

echo [1/12] Loading opportunities (31 days back, key 2) ...
python ./fed_prospector/main.py load opportunities --max-calls 300 --key 2 --days-back 31 --force
echo.

echo [2/12] Loading USASpending bulk (5 days back) ...
python ./fed_prospector/main.py load usaspending-bulk --days-back 5
echo.

echo [3/12] Loading awards — 8(a) set-aside ...
python ./fed_prospector/main.py load awards --naics %NAICS% --days-back 10 --max-calls 300 --key 2 --set-aside 8a
echo.

echo [4/12] Loading awards — WOSB set-aside ...
python ./fed_prospector/main.py load awards --naics %NAICS% --days-back 10 --max-calls 300 --key 2 --set-aside WOSB
echo.

echo [5/12] Loading awards — SBA set-aside ...
python ./fed_prospector/main.py load awards --naics %NAICS% --days-back 10 --max-calls 300 --key 2 --set-aside SBA
echo.

echo [6/12] Enriching resource link metadata (filenames, content types) ...
python ./fed_prospector/main.py update link-metadata
echo.

echo [7/12] Downloading attachments (active opps, missing only) ...
python ./fed_prospector/main.py download attachments --missing-only --active-only --batch-size 5000
echo.

echo [8/12] Extracting text from downloaded attachments ...
python ./fed_prospector/main.py extract attachment-text --batch-size 5000  --workers 10
echo.

echo [9/12] Extracting intelligence from attachment text ...
python ./fed_prospector/main.py extract attachment-intel --batch-size 5000
echo.

echo [10/12] Running AI analysis on attachment text ...
python ./fed_prospector/main.py extract attachment-ai --model haiku --batch-size 50
echo.

echo [11/12] Backfilling opportunity intel from analysis results ...
python ./fed_prospector/main.py backfill opportunity-intel
echo.

echo [12/12] Cleaning up fully-analyzed attachment files ...
python ./fed_prospector/main.py maintain attachment-files
echo.

echo ============================================
echo   Daily load complete: %time%
echo ============================================
