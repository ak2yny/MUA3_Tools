for %%s in (Fire_Emblem_Warriors_BIN, Fire_Emblem_Warriors_XL, Fire_Emblem_Warriors_TalkEv, Fire_Emblem_Warriors_TH_Data, RTK8r_GameMsg) do ((
    echo from CLI.%%s import main
    echo if __name__ == '__main__':
    echo     main^(^)
  ) > cli.py
  pyinstaller --specpath dist --onefile --version-file=..\CLI\%%s.txt --icon=..\Fire_Emblem_Warriors.ico cli.py --name %%s
)