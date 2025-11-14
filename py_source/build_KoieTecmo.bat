for %%s in (KoeiTecmo_Arch, KoeiTecmo_XL, KoeiTecmo_Data0, KoeiTecmo_Data0_Translate_Type1, KoeiTecmo_Data0_Translate_Type2_XL) do ((
    echo from CLI.%%s import main
    echo if __name__ == '__main__':
    echo     main^(^)
  ) > cli.py
  pyinstaller --specpath dist --onefile --version-file=..\CLI\%%s.txt --icon=..\Koei_Tecmo_Holdings_logo.ico cli.py --name %%s
)