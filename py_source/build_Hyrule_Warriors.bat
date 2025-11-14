for %%s in (HyruleWarriors_Data, DWO_Data) do ((
    echo from CLI.%%s import main
    echo if __name__ == '__main__':
    echo     main^(^)
  ) > cli.py
  pyinstaller --specpath dist --onefile --version-file=..\CLI\%%s.txt --icon=..\Hyrule_Warriors_Age_Of_Calamity_Logo.ico cli.py --name %%s
)