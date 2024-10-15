set arguments=--specpath dist --onefile --version-file=..\script.txt --icon=..\MUA3_Mods.ico script.py
pyinstaller %arguments:script=MUA3_ZL%
pyinstaller %arguments:script=MUA3_BIN%

pyinstaller %arguments:script=MUA3_KTSR%
copy /y MUA3_KTSR.txt MUA3_KTSL2STBIN.txt
pyinstaller %arguments:script=MUA3_KTSL2STBIN%
