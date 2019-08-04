####  v1.1.2 (2019-08-04)

_Changed:_

- Bumped mercuryitc driver requirements.
- `MercuryMonitorApp` must now be explicitly imported from main.
- Moved utils to submodule `pyqt_labutils`.

_Fixed:_

- Fixed a bug which would cause saving of log files to fail if no heater module is
  connected.

#### v1.1.1 (2019-04-23)

_Changed:_

- Switched plotting to from Matplotlib to PyQtGraph for better performance.
- Switched to scientific spin boxes.

#### v1.1.0 (2019-04-23)

_Added:_

- Plot gasflow and heater output below temperature plot.
