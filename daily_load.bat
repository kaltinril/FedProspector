@echo off
echo ============================================
echo   FedProspect Daily Data Load
echo   %date% %time%
echo ============================================
echo.

set NAICS=336611,488190,519210,541219,541330,541511,541512,541513,541519,541611,541612,541613,541690,541990,561110,561210,561510,561990,611430,611710,621111,621399,624190,812910

echo [1/13] Loading opportunities (31 days back, key 2) ...
python ./fed_prospector/main.py load opportunities --max-calls 300 --key 2 --days-back 31 --force
echo.

echo [2/13] Fetching missing descriptions (priority NAICS+set-aside, then others, limit 100) ...
python ./fed_prospector/main.py update fetch-descriptions --key 2 --limit 100 --naics %NAICS% --set-aside WOSB,8A,SBA
echo.

echo [3/13] Loading USASpending bulk (5 days back) ...
python ./fed_prospector/main.py load usaspending-bulk --days-back 5
echo.

echo [4/13] Loading awards — 8(a) set-aside ...
python ./fed_prospector/main.py load awards --naics %NAICS% --days-back 10 --max-calls 100 --key 2 --set-aside 8a
echo.

echo [5/13] Loading awards — WOSB set-aside ...
python ./fed_prospector/main.py load awards --naics %NAICS% --days-back 10 --max-calls 100 --key 2 --set-aside WOSB
echo.

echo [6/13] Loading awards — SBA set-aside ...
python ./fed_prospector/main.py load awards --naics %NAICS% --days-back 10 --max-calls 100 --key 2 --set-aside SBA
echo.

echo [7/13] Enriching resource link metadata (filenames, content types) ...
python ./fed_prospector/main.py update link-metadata
echo.

echo [8/13] Downloading attachments (active opps, missing only) ...
python ./fed_prospector/main.py download attachments --missing-only --active-only --batch-size 5000
echo.

echo [9/13] Extracting text from downloaded attachments ...
python ./fed_prospector/main.py extract attachment-text --batch-size 5000  --workers 10
echo.

echo [10/13] Extracting intelligence from attachment text ...
python ./fed_prospector/main.py extract attachment-intel --batch-size 5000
echo.

echo [11/13] Running AI analysis on attachment text ...
REM disabling for now to save on costs, this is a per opportunity analysis that can be run on demand when needed 
echo "skipping attachment AI analysis to save on costs, can be run on demand when needed"
rem python ./fed_prospector/main.py extract attachment-ai --model haiku --batch-size 50
echo.

echo [12/13] Backfilling opportunity intel from analysis results ...
python ./fed_prospector/main.py backfill opportunity-intel
echo.

echo [13/13] Cleaning up fully-analyzed attachment files ...
python ./fed_prospector/main.py maintain attachment-files
echo.

echo "TEMPORARY ORG HIERARCHY LOAD TO CATCH UP"
python ./fed_prospector/main.py load offices --key 2 --max-calls 300
python ./fed_prospector/main.py load offices --key 1 --max-calls 10

echo ============================================
echo   Daily load complete: %time%
echo ============================================
