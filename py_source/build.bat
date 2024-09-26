set arguments=--specpath dist --onefile --version-file=..\script.txt --icon=..\MUA3_Mods.ico script.py
pyinstaller %arguments:script=MUA3_ZL%
pyinstaller %arguments:script=MUA3_BIN%
