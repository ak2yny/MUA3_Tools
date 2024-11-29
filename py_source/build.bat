pip install -r build.requirements.txt

set arguments=--specpath dist --onefile --version-file=..\script.txt --icon=..\MUA3_Mods.ico script.py
pyinstaller %arguments:script=MUA3_ZL%
pyinstaller %arguments:script=MUA3_BIN%

pyinstaller %arguments:script=MUA3_G1T% --add-data="..\lib\lib_g1t.py;lib\lib_g1t.py"
REM pyinstaller %arguments:script=MUA3_G1% --add-data="..\lib\*;lib"

pyinstaller %arguments:script=MUA3_KTSR%
copy /y MUA3_KTSR.txt MUA3_KTSL2STBIN.txt
pyinstaller %arguments:script=MUA3_KTSL2STBIN%
