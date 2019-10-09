#### v1.1.3 (2019-10-09):

This release focuses on cosmetic improvements, including dark mode support.

##### Changed:

- We now depend on our own fork of pyqtgraph `cx_pyqtgraph`.

##### Added:

- Support for dark interface themes, such as the dark mode in macOS Mojave. This will
  require a version of PyQt / Qt which supports system themes, such as v5.12 for macOS.

####  v1.1.2 (2019-08-04)

##### Changed:

- Bumped mercuryitc driver requirements.
- `MercuryMonitorApp` must now be explicitly imported from main.
- Moved utils to submodule `pyqt_labutils`.

##### Fixed:

- Fixed a bug which would cause saving of log files to fail if no heater module is
  connected.

#### v1.1.1 (2019-04-23)

##### Changed:

- Switched plotting to from Matplotlib to PyQtGraph for better performance.
- Switched to scientific spin boxes.

#### v1.1.0 (2019-04-23)

##### Added:

- Plot gasflow and heater output below temperature plot.
