pip install pyinstaller
if not errorlevel 0 exit
REM Copy icon?

set install_requirements=pip install -r script.requirements.txt
set arguments=--specpath dist --onefile --version-file=..\script.txt --icon=..\..\MUA3_Mods.ico script.pyw  --add-data "..\..\MUA3_Mods.ico;." --add-data "..\xmlb_fake.py;." --additional-hooks-dir=.


REM %install_requirements:script=RavenFormatsUI%
REM pyinstaller %arguments:script=RavenFormatsUI% --add-data "..\tkBreeze;tkBreeze"


REM ----------------- CustomTkInter Variant --------------------

for /f "tokens=1* delims=: " %%k in ('pip show customtkinter ^| findstr /bl "Location"') do set l=%%l
if not errorlevel 0 exit

%install_requirements:script=RavenFormatsUI_CTKI%
pyinstaller %arguments:script=RavenFormatsUI_CTKI% --noconfirm --windowed --add-data "%l:\=/%/customtkinter;customtkinter/"

REM set arguments=%arguments:onefile=onedir%
REM pyinstaller %arguments:script=RavenFormatsUI_CTKI% --noconfirm --windowed --add-data "%l:\=/%/customtkinter;customtkinter/"
