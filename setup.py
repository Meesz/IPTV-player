from setuptools import setup, find_packages

setup(
    name="simple-iptv",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "PyQt6>=6.0.0",
        "python-vlc>=3.0.0",
        "requests>=2.25.0",
    ],
    entry_points={
        'console_scripts': [
            'simple-iptv=simple_iptv.main:main',
        ],
    },
    author="Meesz",
    author_email="meesz@meesz.com",
    description="A simple IPTV player with EPG support",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Meesz/IPTV-player",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Environment :: X11 Applications :: Qt",
        "Topic :: Multimedia :: Video :: Display",
    ],
    python_requires=">=3.7",
) 