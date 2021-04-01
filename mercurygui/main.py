# -*- coding: utf-8 -*-
"""
@author: Sam Schott  (ss2151@cam.ac.uk)

(c) Sam Schott; This work is licensed under a Creative Commons
Attribution-NonCommercial-NoDerivs 2.0 UK: England & Wales License.

"""

# system imports
import sys
import os
import platform
import subprocess
import pkg_resources as pkgr
import time
import numpy as np
import logging
from pathlib import Path
from PyQt5 import QtCore, QtWidgets, uic
from mercuryitc.mercury_driver import MercuryITC_TEMP, MercuryITC_HTR, MercuryITC_AUX

# local imports
from .feed import MercuryFeed
from .pyqt_labutils import LedIndicator, ConnectionDialog
from .pyqtplot_canvas import TemperatureHistoryPlot
from .config.main import CONF

MAIN_UI_PATH = pkgr.resource_filename("mercurygui", "main.ui")
PANEL_UI_PATH = pkgr.resource_filename("mercurygui", "panel.ui")
MODULE_DIALOG_UI_PATH = pkgr.resource_filename("mercurygui", "module_dialog.ui")

logger = logging.getLogger(__name__)


# noinspection PyArgumentList
class MercuryMonitorApp(QtWidgets.QMainWindow):

    QUIT_ON_CLOSE = True

    MAX_DISPLAY = 24 * 60 * 60
    UPDATE_FREQ = 1
    TITLE_TEMPLATE = "MercuryiTC Control"
    log_path = Path.home() / ".mercurygui" / "LOG_FILES"

    def __init__(self, mercury):
        super(self.__class__, self).__init__()
        uic.loadUi(MAIN_UI_PATH, self)

        self.mercury = mercury
        self._cached_connection_status = False

        # create popup Widgets
        self.connectionDialog = ConnectionDialog(self, self.mercury, CONF)
        self.readingsDialog = ReadingsOverview(self.mercury)
        self.modulesDialog = ModulesDialog(self.mercury)

        # create LED indicator
        self.led = LedIndicator(self)
        self.statusbar.addPermanentWidget(self.led)
        self.led.setChecked(False)

        # restore previous window geometry
        self.restore_geometry()

        # connect to callbacks
        self.modulesAction.triggered.connect(self.on_module_selection_clicked)
        self.showLogAction.triggered.connect(self.on_log_clicked)
        self.exitAction.triggered.connect(self.exit_)
        self.readingsAction.triggered.connect(self.on_readings_clicked)
        self.updateAddressAction.triggered.connect(self.connectionDialog.open)
        self.connectionDialog.accepted.connect(self.build_tabs)

        self.actionUpdateVeryOften.triggered.connect(lambda: self.set_update_freq(0.5))
        self.actionUpdateOften.triggered.connect(lambda: self.set_update_freq(1))
        self.actionUpdateNormally.triggered.connect(lambda: self.set_update_freq(2))

        action_group = QtWidgets.QActionGroup(self)
        action_group.addAction(self.actionUpdateVeryOften)
        action_group.addAction(self.actionUpdateOften)
        action_group.addAction(self.actionUpdateNormally)

        # initially disable menu bar items, will be enabled later individually
        self.modulesAction.setEnabled(False)
        self.readingsAction.setEnabled(False)

        # check if mercury is connected, connect slots
        self.display_message(f"Looking for Mercury at {self.mercury.visa_address}...")

        # populate panels for temperature modules
        self.panels = {}
        self.build_tabs()

        self.update_timer = QtCore.QTimer()
        self.update_timer.setInterval(self.UPDATE_FREQ * 1000)
        self.update_timer.setSingleShot(False)  # set to reoccur
        self.update_timer.timeout.connect(self.update_gui)
        self.update_timer.start()

    def set_update_freq(self, seconds):
        self.update_timer.setInterval(seconds * 1000)

        for panel in self.panels.values():
            panel.feed.refresh = seconds

    def build_tabs(self):

        self.tabWidget.clear()

        sensor_names = self._get_nicks(MercuryITC_TEMP)

        if len(sensor_names) == 0:
            sensor_names.append("Dummy")

        for sensor_name in sensor_names:
            panel = ControlPanel(self.mercury, self, sensor_name)
            self.panels[sensor_name] = panel
            self.tabWidget.addTab(panel, sensor_name)

    def update_gui(self):

        if not self.mercury.connected:
            self.mercury.connect()

        connected = self.mercury.connected

        if connected is not self._cached_connection_status:
            # update gui to reflect changed connection status
            self.build_tabs()
            self.update_gui_connection(connected)
            for panel in self.panels.values():
                panel.update_gui_connection(connected)

        self._cached_connection_status = self.mercury.connected

    # =================== BASIC UI SETUP ==========================================

    def restore_geometry(self):
        x = CONF.get("Window", "x")
        y = CONF.get("Window", "y")
        w = CONF.get("Window", "width")
        h = CONF.get("Window", "height")

        self.setGeometry(x, y, w, h)

    def save_geometry(self):
        geo = self.geometry()
        CONF.set("Window", "height", geo.height())
        CONF.set("Window", "width", geo.width())
        CONF.set("Window", "x", geo.x())
        CONF.set("Window", "y", geo.y())

    def exit_(self):
        self.save_geometry()
        self.deleteLater()

    def closeEvent(self, event):
        if self.QUIT_ON_CLOSE:
            self.exit_()
        else:
            self.hide()

    def update_gui_connection(self, connected):

        if connected:
            self.led.setChecked(True)

            # enable / disable menu bar items
            self.connectAction.setEnabled(False)
            self.disconnectAction.setEnabled(True)
            self.modulesAction.setEnabled(True)
            self.readingsAction.setEnabled(True)
            self.sensorAction.setEnabled(True)

        elif not connected:
            self.led.setChecked(False)

            # enable / disable menu bar items
            self.connectAction.setEnabled(True)
            self.disconnectAction.setEnabled(False)
            self.modulesAction.setEnabled(False)
            self.readingsAction.setEnabled(False)

    def display_message(self, text):
        self.statusbar.showMessage(str(text), 5000)

    def display_error(self, text):
        self.statusbar.showMessage(str(text))

    # ========================== CALLBACKS FOR MENU BAR ===========================

    @QtCore.pyqtSlot()
    def on_readings_clicked(self):
        self.readingsDialog.update_gui()
        self.readingsDialog.show()

    @QtCore.pyqtSlot()
    def on_module_selection_clicked(self):
        self.modulesDialog.update_gui()
        self.modulesDialog.open()

    @QtCore.pyqtSlot()
    def on_log_clicked(self):
        """
        Opens directory with log files with current log file selected.
        """

        if platform.system() == "Windows":
            os.startfile(self.log_path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(self.log_path)])
        else:
            subprocess.Popen(["xdg-open", str(self.log_path)])

    def _get_nicks(self, sensor_type):
        if self.mercury.connected:
            return list(m.nick for m in self.mercury.modules if type(m) == sensor_type)
        else:
            return []


# noinspection PyArgumentList
class ControlPanel(QtWidgets.QMainWindow):

    MAX_DISPLAY = 24 * 60 * 60

    def __init__(self, mercury, parent, sensor_name=""):
        super(self.__class__, self).__init__()
        uic.loadUi(PANEL_UI_PATH, self)

        self.mercury = mercury
        self.parent = parent

        self.sensor_name = sensor_name
        self.temperature = self.get_modules(sensor_name)
        if self.temperature:
            self.feed = MercuryFeed(self.mercury, self.temperature, self.parent.UPDATE_FREQ)
            self.feed.readings_signal.connect(self.update_gui)
            self.feed.readings_signal.connect(self.update_plot)
            self.feed.connected_signal.connect(self.update_gui_connection)

        # set up temperature plot, adjust window margins accordingly
        self.canvas = TemperatureHistoryPlot()
        self.gridLayoutCanvas.addWidget(self.canvas)
        self.horizontalSlider.setMaximum(self.MAX_DISPLAY / 60)

        # connect slider to plot
        self.horizontalSlider.valueChanged.connect(self.on_slider_changed)

        # adapt text edit colors to graph colors
        self.t1_reading.setStyleSheet("color:rgb%s" % str(self.canvas.GREEN))
        self.gf1_edit.setStyleSheet("color:rgb%s" % str(self.canvas.BLUE))
        self.h1_edit.setStyleSheet("color:rgb%s" % str(self.canvas.RED))
        self.gf1_edit.setMinimalStep(0.1)
        self.h1_edit.setMinimalStep(0.1)

        # set up data vectors for plot
        self.xdata = np.array([])
        self.xdata_min_zero = np.array([])
        self.ydata_tmpr = np.array([])
        self.ydata_gflw = np.array([])
        self.ydata_htr = np.array([])

        # connect to callbacks
        self.t2_edit.returnPressed.connect(self.change_t_setpoint)
        self.r1_edit.returnPressed.connect(self.change_ramp)
        self.r2_checkbox.clicked.connect(self.change_ramp_auto)
        self.gf1_edit.returnPressed.connect(self.change_flow)
        self.gf2_checkbox.clicked.connect(self.change_flow_auto)
        self.gf3_edit.returnPressed.connect(self.change_flow_min)
        self.h1_edit.returnPressed.connect(self.change_heater)
        self.h2_checkbox.clicked.connect(self.change_heater_auto)

        # enable or disable controls
        self.update_gui_connection(self.mercury.connected)

        # set up logging to file
        self.setup_logging()

    def get_modules(self, sensor_name):
        """
        Updates module list after the new modules have been selected.
        """
        # find all temperature modules
        modules = getattr(self.mercury, "modules", [])
        tmp_modules = [m for m in modules if type(m) is MercuryITC_TEMP]

        # find match for given nick
        match = next((m for m in tmp_modules if m.nick == sensor_name), None)

        if match:
            temperature = match
        elif tmp_modules:
            logger.warning(f'Sensor "{sensor_name}" not found, choosing first module')
            temperature = tmp_modules[0]
            self.sensor_name = tmp_modules[0].nick
        else:
            temperature = None
            logger.warning('No temperature sensors found')

        return temperature

    # =================== BASIC UI SETUP ==========================================

    def on_slider_changed(self):
        # determine first plotted data point
        sv = self.horizontalSlider.value()

        self.timeLabel.setText("Show last %s min" % sv)
        self.canvas.set_xmin(-sv)
        self.canvas.p0.setXRange(-sv, 0)
        self.canvas.p0.enableAutoRange(x=False, y=True)

    def update_gui_connection(self, connected):

        if connected:

            # enable controls
            self.t2_edit.setEnabled(True)
            self.r1_edit.setEnabled(True)
            self.r2_checkbox.setEnabled(True)
            self.gf1_edit.setEnabled(True)
            self.gf2_checkbox.setEnabled(True)
            self.gf3_edit.setEnabled(True)
            self.h1_edit.setEnabled(True)
            self.h2_checkbox.setEnabled(True)

        elif not connected:

            # disable controls
            self.t2_edit.setEnabled(False)
            self.r1_edit.setEnabled(False)
            self.r2_checkbox.setEnabled(False)
            self.gf1_edit.setEnabled(False)
            self.gf2_checkbox.setEnabled(False)
            self.gf3_edit.setEnabled(False)
            self.h1_edit.setEnabled(False)
            self.h2_checkbox.setEnabled(False)

    def update_gui(self, readings):
        """
        Parses readings for the MercuryMonitorApp and updates UI accordingly
        """

        # heater signals
        self.h1_label.setText("Heater, %s V:" % readings["HeaterVolt"])
        self.h1_edit.updateValue(readings["HeaterPercent"])

        if self.feed.heater:
            is_heater_auto = readings["HeaterAuto"] == "ON"
            self.h1_edit.setReadOnly(is_heater_auto)
            self.h1_edit.setEnabled(not is_heater_auto)
            self.h2_checkbox.setChecked(is_heater_auto)
            self.h2_checkbox.setEnabled(True)
        else:
            self.h1_edit.setReadOnly(True)
            self.h1_edit.setEnabled(False)
            self.h2_checkbox.setEnabled(False)

        # gas flow signals
        self.gf1_edit.updateValue(readings["FlowPercent"])
        self.gf3_edit.updateValue(readings["FlowMin"])

        if self.feed.gasflow:
            is_gf_auto = readings["FlowAuto"] == "ON"
            self.gf1_edit.setReadOnly(is_gf_auto)
            self.gf1_edit.setEnabled(not is_gf_auto)
            self.gf2_checkbox.setChecked(is_gf_auto)
            self.gf2_checkbox.setEnabled(True)
            self.gf3_edit.setEnabled(True)
        else:
            self.gf1_edit.setEnabled(False)
            self.gf2_checkbox.setEnabled(False)
            self.gf3_edit.setEnabled(False)

        # temperature signals
        self.t1_reading.setText("%s K" % round(readings["Temp"], 3))
        self.t2_edit.updateValue(readings["TempSetpoint"])
        self.r1_edit.updateValue(readings["TempRamp"])

        is_ramp_enable = readings["TempRampEnable"] == "ON"
        self.r2_checkbox.setChecked(is_ramp_enable)

        # alarms
        alarm_str = ""
        for k, v in readings["Alarms"].items():
            alarm_str += "{}: {} ".format(k, v)

        self.alarm_label.setText(alarm_str)

        if alarm_str:
            self.alarm_label.show()
        else:
            self.alarm_label.hide()

    def update_plot(self, readings):
        # append data for plotting
        self.xdata = np.append(self.xdata, time.time())
        self.ydata_tmpr = np.append(self.ydata_tmpr, readings["Temp"])
        self.ydata_gflw = np.append(self.ydata_gflw, readings["FlowPercent"] / 100)
        self.ydata_htr = np.append(self.ydata_htr, readings["HeaterPercent"] / 100)

        # prevent data vector from exceeding MAX_DISPLAY
        self.xdata = self.xdata[-self.MAX_DISPLAY :]
        self.ydata_tmpr = self.ydata_tmpr[-self.MAX_DISPLAY :]
        self.ydata_gflw = self.ydata_gflw[-self.MAX_DISPLAY :]
        self.ydata_htr = self.ydata_htr[-self.MAX_DISPLAY :]

        # convert xData to minutes and set current time to t = 0
        self.xdata_min_zero = (self.xdata - self.xdata[-1]) / 60

        # update plot
        self.canvas.update_data(
            self.xdata_min_zero, self.ydata_tmpr, self.ydata_gflw, self.ydata_htr
        )

    def clear_plot(self):
        # append data for plotting
        self.xdata = np.array([])
        self.xdata_min_zero = np.array([])
        self.ydata_tmpr = np.array([])
        self.ydata_gflw = np.array([])
        self.ydata_htr = np.array([])

        # update plot
        self.canvas.update_data(
            self.xdata, self.ydata_tmpr, self.ydata_gflw, self.ydata_htr
        )

    def display_message(self, text):
        self.parent.display_message(text)

    def display_error(self, text):
        self.parent.display_error(text)

    # =================== LOGGING DATA ============================================

    def setup_logging(self):
        """
        Save temperature history to log file at '~/.CustomXepr/LOG_FILES/' every 10 min.
        """

        os.makedirs(self.parent.log_path, exist_ok=True)

        # set logging file path
        time_str = time.strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = self.parent.log_path / f"{self.sensor_name}_{time_str}.txt"

        # delete old log files
        now = time.time()
        days_to_keep = 7

        for file in os.scandir(self.parent.log_path):
            if file.stat().st_mtime < now - days_to_keep * 24 * 60 * 60:
                if file.is_file():
                    os.remove(file.path)

        # set up periodic logging
        t_save = 10  # time interval to save temperature data (min)
        self.log_timer = QtCore.QTimer()
        self.log_timer.setInterval(t_save * 60 * 1000)
        self.log_timer.setSingleShot(False)  # set to reoccur
        self.log_timer.timeout.connect(self.log_temperature_data)
        self.log_timer.start()

    def save_temperature_data(self, path=None):
        # prompt user for file path if not given
        if path is None:
            text = "Select path for temperature data file:"
            path = QtWidgets.QFileDialog.getSaveFileName(caption=text)
            path = path[0]

        header = "\t".join(
            ["Time (sec)", "Temperature (K)", "Heater (%)", "Gas flow (%)"]
        )

        data_matrix = np.concatenate(
            (
                self.xdata[:, np.newaxis],
                self.ydata_tmpr[:, np.newaxis],
                self.ydata_htr[:, np.newaxis],
                self.ydata_gflw[:, np.newaxis],
            ),
            axis=1,
        )

        # noinspection PyTypeChecker
        np.savetxt(path, data_matrix, delimiter="\t", header=header, fmt="%f")

    def log_temperature_data(self):
        # save temperature data to log file
        if self.mercury.connected:
            self.save_temperature_data(self.log_file)

    # =================== CALLBACKS FOR SETTING CHANGES ===========================

    def change_t_setpoint(self):
        new_t = self.t2_edit.value()

        if 3.5 < new_t < 300:
            self.display_message(f"T_setpoint = {new_t} K")
            self.temperature.loop_tset = new_t
        else:
            self.display_error(
                "Error: Only temperature setpoints between 3.5 K and 300 K allowed."
            )

    def change_ramp(self):
        self.temperature.loop_rset = self.r1_edit.value()
        self.display_message(f"Ramp = {self.r1_edit.value()} K/min")

    def change_ramp_auto(self, checked):
        if checked:
            self.temperature.loop_rena = "ON"
            self.display_message("Ramp is turned ON")
        else:
            self.temperature.loop_rena = "OFF"
            self.display_message("Ramp is turned OFF")

    def change_flow(self):
        self.temperature.loop_fset = self.gf1_edit.value()
        self.display_message(f"Gas flow = {self.gf1_edit.value()}%%")

    def change_flow_min(self):
        self.gasflow.gmin = self.gf3_edit.value()
        self.display_message(f"Gas flow min = {self.gf3_edit.value()}%%")

    def change_flow_auto(self, checked):
        if checked:
            self.temperature.loop_faut = "ON"
            self.display_message("Gas flow is automatically controlled.")
            self.gf1_edit.setReadOnly(True)
            self.gf1_edit.setEnabled(False)
        else:
            self.temperature.loop_faut = "OFF"
            self.display_message("Gas flow is manually controlled.")
            self.gf1_edit.setReadOnly(False)
            self.gf1_edit.setEnabled(True)

    def change_heater(self):
        self.temperature.loop_hset = self.h1_edit.value()
        self.display_message(f"Heater power  = {self.h1_edit.value()}%%")

    def change_heater_auto(self, checked):
        if checked:
            self.temperature.loop_enab = "ON"
            self.display_message("Heater is automatically controlled.")
            self.h1_edit.setReadOnly(True)
            self.h1_edit.setEnabled(False)
        else:
            self.temperature.loop_enab = "OFF"
            self.display_message("Heater is manually controlled.")
            self.h1_edit.setReadOnly(False)
            self.h1_edit.setEnabled(True)


# noinspection PyUnresolvedReferences
class ReadingsTab(QtWidgets.QWidget):

    EXCEPT = ["read", "write", "query", "CAL_INT", "EXCT_TYPES", "TYPES", "clear_cache"]

    def __init__(self, mercury, module):
        super(self.__class__, self).__init__()

        self.module = module
        self.mercury = mercury

        self.name = module.nick
        self.attr = dir(module)

        self.gridLayout = QtWidgets.QGridLayout(self)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout_%s" % self.name)

        self.label = QtWidgets.QLabel(self)
        self.label.setObjectName("label_%s" % self.name)
        self.gridLayout.addWidget(self.label, 0, 0, 1, 2)

        self.comboBox = QtWidgets.QComboBox(self)
        self.comboBox.setObjectName("comboBox_%s" % self.name)
        self.gridLayout.addWidget(self.comboBox, 1, 0, 1, 1)

        self.lineEdit = QtWidgets.QLineEdit(self)
        self.lineEdit.setObjectName("lineEdit_%s" % self.name)
        self.gridLayout.addWidget(self.lineEdit, 1, 1, 1, 1)

        readings = [x for x in self.attr if not (x.startswith("_") or x in self.EXCEPT)]
        self.comboBox.addItems(readings)

        self.comboBox.currentIndexChanged.connect(self.get_reading)
        self.comboBox.currentIndexChanged.connect(self.get_alarms)

        self.get_reading()
        self.get_alarms()

    def get_reading(self):
        """ Gets readings of selected variable in combobox."""

        reading = getattr(self.module, self.comboBox.currentText())
        if isinstance(reading, tuple):
            reading = "".join(map(str, reading))
        reading = str(reading)
        self.lineEdit.setText(reading)

    def get_alarms(self):
        """Gets alarms of associated module."""

        # get alarms for all modules
        try:
            alarm = self.mercury.alarms[self.module.uid]
        except KeyError:
            alarm = "--"

        self.label.setText("Alarms: %s" % alarm)


class ReadingsOverview(QtWidgets.QWidget):
    def __init__(self, mercury, parent=None):
        super(self.__class__, self).__init__(parent=parent)
        self.setWindowTitle("Readings Overview")
        self.resize(500, 142)
        self.masterGrid = QtWidgets.QGridLayout(self)
        self.masterGrid.setObjectName("gridLayout")

        self.mercury = mercury

        # create main tab widget
        self.tabWidget = QtWidgets.QTabWidget(self)
        self.masterGrid.addWidget(self.tabWidget, 0, 0, 1, 1)

        # refresh readings every 3 sec
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.get_readings)
        self.timer.start(3000)

    def update_gui(self):

        # create a tab with combobox and text box for each module
        self.readings_tabs = []

        for module in getattr(self.mercury, "modules", []):
            new_tab = ReadingsTab(self.mercury, module)
            self.readings_tabs.append(new_tab)
            self.tabWidget.addTab(new_tab, module.nick)

        self.tabWidget.setCurrentIndex(0)

    def get_readings(self):
        """
        Getting alarms of selected tab and update its selected reading, only
        if QWidget is not hidden.
        """
        if self.isVisible():
            self.tabWidget.currentWidget().get_reading()
            self.tabWidget.currentWidget().get_alarms()


class _NoModule:
    nick = "None"


class ModulesDialog(QtWidgets.QDialog):
    """
    Provides a user dialog to select which gasflow and heater modules are associated
    with a temperature sensor.
    """

    accepted = QtCore.pyqtSignal(object)

    def __init__(self, mercury, parent=None):
        super(self.__class__, self).__init__(parent=parent)
        uic.loadUi(MODULE_DIALOG_UI_PATH, self)

        self.mercury = mercury
        self.update_gui()

    def update_gui(self):

        self.temp_modules = self._get_modules_for_type(MercuryITC_TEMP)
        self.htr_modules = self._get_modules_for_type(MercuryITC_HTR)
        self.aux_modules = self._get_modules_for_type(MercuryITC_AUX)

        self.htr_modules.append(_NoModule())
        self.aux_modules.append(_NoModule())

        self.comboBoxTEMP.clear()
        self.comboBoxHTR.clear()
        self.comboBoxAUX.clear()

        self.comboBoxTEMP.addItems([m.nick for m in self.temp_modules])
        self.comboBoxHTR.addItems([m.nick for m in self.htr_modules])
        self.comboBoxAUX.addItems([m.nick for m in self.aux_modules])

        # get current modules
        if len(self.temp_modules) > 0:
            self.comboBoxTEMP.setCurrentIndex(0)
            self.comboBoxHTR.setCurrentText(self.temp_modules[0].loop_htr)
            self.comboBoxAUX.setCurrentText(self.temp_modules[0].loop_aux)

        # connect callbacks
        self.comboBoxTEMP.currentIndexChanged.connect(self.on_temp_selected)
        self.buttonBox.accepted.connect(self.on_accept)

    def on_temp_selected(self, index):
        # update content of heater and gasflow combo boxes
        self.comboBoxHTR.setCurrentText(self.temp_modules[index].loop_htr)
        self.comboBoxAUX.setCurrentText(self.temp_modules[index].loop_aux)

    def on_accept(self):
        temp_index = self.comboBoxTEMP.currentIndex()
        htr_nick = self.comboBoxHTR.currentText()
        aux_nick = self.comboBoxAUX.currentText()

        # remove heater and gasflow modules from previous loop
        for module in self.temp_modules:
            if module is not self.temp_modules[temp_index]:
                if module.loop_htr == htr_nick:
                    module.loop_htr = "None"
                if module.loop_aux == aux_nick:
                    module.loop_aux = "None"

        # assign heater and gasflow modules to selected loop
        self.temp_modules[temp_index].loop_htr = htr_nick
        self.temp_modules[temp_index].loop_aux = aux_nick

    def _get_modules_for_type(self, sensor_type):
        modules = getattr(self.mercury, "modules", [])
        return [m for m in modules if type(m) is sensor_type]


def run():

    from mercuryitc import MercuryITC
    from mercurygui.config.main import CONF

    app = QtWidgets.QApplication(sys.argv)

    mercury_address = CONF.get("Connection", "VISA_ADDRESS")
    visa_library = CONF.get("Connection", "VISA_LIBRARY")

    mercury = MercuryITC(mercury_address, visa_library, open_timeout=1)

    mercury_gui = MercuryMonitorApp(mercury)
    mercury_gui.show()

    app.exec_()


if __name__ == "__main__":
    run()
