### v2.1.2

#### Fixed:

- Fixed connecting to MercuryiTC without a default temperature module.

### v2.1.1

#### Fixed:

- Fixed missing submodule in PyPI release.

### v2.1.0

#### Added:

- New menu "Assign modules" to assign gasflow and heater modules to a temperature sensor
  from the GUI.
- New control to set the minimum gas flow for automatic mode.
- Display any alarms for a temperature sensor and its associated modules in the GUI.

#### Changed:

- Select the current temperature sensor from a menu instead of a dialog.
- Clear the plot when switching sensors.

### v2.0.0

#### Changed:

- `MercuryMonitorApp` now takes a `MercuryITC` instance as a first argument instead of
  a `MercuryFeed` instance. The feed will be created internally.
- If a temperature module does not have an attached heater or gas flow module, the
  corresponding GUI elements are greyed out.

### v1.2.0

This release drops support for Python 2.7. Only Python 3.6 and higher are supported.

#### Changed:

- Updated submodule 'pyqt_labutils'.
- Depend on PyQt5 instead of qtpy.
- Resize connection dialog when hiding PyVisa backend textbox. 

#### Removed:

- Python 2.7 support.

### v1.1.3

This release focuses on cosmetic improvements, including dark mode support.

#### Changed:

- We now depend on our own fork of pyqtgraph `cx_pyqtgraph`.

#### Added:

- Support for dark interface themes, such as the dark mode in macOS Mojave. This will
  require a version of PyQt / Qt which supports system themes, such as v5.12 for macOS.

###  v1.1.2

#### Changed:

- Bumped mercuryitc driver requirements.
- `MercuryMonitorApp` must now be explicitly imported from main.
- Moved utils to submodule `pyqt_labutils`.

#### Fixed:

- Fixed a bug which would cause saving of log files to fail if no heater module is
  connected.

### v1.1.1

#### Changed:

- Switched plotting to from Matplotlib to PyQtGraph for better performance.
- Switched to scientific spin boxes.

### v1.1.0

#### Added:

- Plot gasflow and heater output below temperature plot.
