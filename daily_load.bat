@echo off
REM FedProspect Daily Data Load
REM This batch file delegates to the Python daily load command.
REM For options: python ./fed_prospector/main.py job daily --help
REM
REM NAICS codes (for reference):
REM 336611,488190,519210,541219,541330,541511,541512,541513,541519,
REM 541611,541612,541613,541690,541990,561110,561210,561510,561990,
REM 611430,611710,621111,621399,624190,812910

python ./fed_prospector/main.py job daily %*
