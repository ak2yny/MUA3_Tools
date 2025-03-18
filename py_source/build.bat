REM Blender
REM -------
mkdir MUA3\lib
for %%p in (Blender_plugin\*.py) do copy %%p MUA3\
copy CLI\lib MUA3\lib
for %%p in (MUA3_ZL, MUA3_BIN, MUA3_Formats, MUA3_G1_Helper, MUA3_KTSR) do copy CLI\%%p.py MUA3\
copy Blender_plugin\blender_manifest.toml MUA3\
copy ..\LICENSE MUA3\
copy ..\README.md MUA3\
REM tar -cf .\dist\MUA3_Blender_Plugin.zip ".\MUA3"
powershell "Compress-Archive -Force .\MUA3 .\dist\MUA3_Blender_Plugin.zip"
rd /s /q MUA3


REM Standalone executables
REM ----------------------
pip install -r build.requirements.txt

REM MUA3_G1
copy /y MUA3_KTSR.txt MUA3_KTSL2STBIN.txt
for %%s in (MUA3_ZL, MUA3_BIN, MUA3_G1T, MUA3_KTSR, MUA3_KTSL2STBIN, MUA3_KSLT) do ((
    echo from CLI.%%s import main
    echo if __name__ == '__main__':
    echo     main^(^)
  ) > cli.py
  pyinstaller --specpath dist --onefile --version-file=..\CLI\%%s.txt --icon=..\MUA3_Mods.ico cli.py --name %%s
)