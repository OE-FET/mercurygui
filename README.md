# mercurygui
mercurygui provides a higher-level worker thread which regularly queries the MercuryiTC for its sensor readings and provides a live stream of this data to other parts of the software. This prevents individual functions from querying the MercuryiTC directly and causing unnecessary overhead.

The user interface for the cryostat plots historic temperature readings going back up to 24 h and provides access to relevant temperature control settings such as gas flow, heater power, and ramping speed while lower-level configurations such as calibration tables must be changed programatically.


![Screenshot of the user interface](/screenshots/MercuryGUI.png)

## System requirements
*Required*:

- Linux or macOS
- Python 2.7 or 3.x

## Acknowledgements
Config file modules are based on the implementation from [Spyder](https://github.com/spyder-ide).