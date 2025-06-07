<!-- build app -->
pyinstaller --onefile --windowed --add-binary "ffmpeg.exe;." --add-data "dautay.ico;." --icon=dautay.ico --name=dautay app_gui.py
<!-- package movie -->
https://pypi.org/project/moviepy/1.0.3/#files