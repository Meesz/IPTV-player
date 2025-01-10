from cx_Freeze import setup, Executable

setup(
    name="Simple IPTV",
    version="0.1.0",
    description="A simple IPTV player with EPG support",
    executables=[Executable("main.py", base="Win32GUI")],
) 