[![PyPi Release](https://img.shields.io/pypi/v/mercurygui.svg?style=flat)](https://pypi.org/project/mercurygui/)
[![Build Status](https://travis-ci.com/OE-FET/mercurygui.svg?branch=master)](https://travis-ci.com/OE-FET/mercurygui)

# mercurygui
mercurygui provides a higher-level worker thread which regularly queries the MercuryiTC for its sensor readings and provides a live stream of this data to other parts of the software. This prevents individual functions from querying the MercuryiTC directly and causing unnecessary overhead.

The user interface for the cryostat plots historic temperature readings going back up to 24 h and provides access to relevant temperature control settings such as gas flow, heater power, and ramping speed while lower-level configurations such as calibration tables must be changed programatically.


<img src="https://raw.githubusercontent.com/OE-FET/mercurygui/master/screenshots/MercuryGUI.png" alt="Screenshot of the user interface" width="800"/>

## System requirements
*Required*:

- Linux or macOS
- Python 2.7 or 3.x

## Installation
Download or clone the repository. Install the package by running:
```console
$ pip install git+https://github.com/OE-FET/mercurygui
```

## Acknowledgements
Config modules are based on the implementation from [Spyder](https://github.com/spyder-ide).
