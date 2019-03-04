# -*- coding: utf-8 -*-

"""
Created on Tue Aug 23 11:03:57 2016

@author: Sam Schott  (ss2151@cam.ac.uk)

(c) Sam Schott; This work is licensed under a Creative Commons
Attribution-NonCommercial-NoDerivs 2.0 UK: England & Wales License.

"""

# system imports
from __future__ import division, print_function, absolute_import
import sys
import os
import platform
import subprocess
import pkg_resources as pkgr
import time
import numpy as np
import logging
from qtpy import QtGui, QtCore, QtWidgets, uic

# local imports
from mercurygui.feed import MercuryFeed
from mercurygui.connection_dialog import ConnectionDialog
from mercurygui.utils.led_indicator_widget import LedIndicator
from mercurygui.utils.pyqtplot_canvas import TemperatureHistoryPlot
from mercurygui.config.main import CONF

MPL_STYLE_PATH = pkgr.resource_filename('mercurygui', 'figure_style.mplstyle')
MAIN_UI_PATH = pkgr.resource_filename('mercurygui', 'main.ui')

logger = logging.getLogger(__name__)


class MercuryMonitorApp(QtWidgets.QMainWindow):

    def __init__(self, feed):
        super(self.__class__, self).__init__()
        uic.loadUi(MAIN_UI_PATH, self)

        self.feed = feed

        # create popup Widgets
        self.connection_dialog = ConnectionDialog(self, feed.mercury)
        self.readingsWindow = None

        # create LED indicator
        self.led = LedIndicator(self)
        self.statusbar.addPermanentWidget(self.led)
        self.led.setChecked(False)

        # set up figure for plotting
        self.canvas = TemperatureHistoryPlot()
        self.gridLayoutCanvas.addWidget(self.canvas)
        self.horizontalSlider.valueChanged.connect(self.on_slider_changed)

        # adapt text edit colors to graph colors
        self.t1_reading.setStyleSheet('color:rgb%s' % str(tuple(self.canvas.GREEN)))
        self.gf1_edit.setStyleSheet('color:rgb%s' % str(tuple(self.canvas.BLUE)))
        self.h1_edit.setStyleSheet('color:rgb%s' % str(tuple(self.canvas.RED)))
        self.gf1_unit.setStyleSheet('color:rgb%s' % str(tuple(self.canvas.BLUE)))
        self.h1_unit.setStyleSheet('color:rgb%s' % str(tuple(self.canvas.RED)))

        # set up data vectors for plot
        self.xdata = np.array([])
        self.xdata_zero = np.array([])
        self.ydata_tmpr = np.array([])
        self.ydata_gflw = np.array([])
        self.ydata_htr = np.array([])

        # restore previous window geometry
        self.restore_geometry()
        # Connect menu bar actions
        self.set_up_menubar()
        # set input validators for all fields
        self.set_input_validators()

        # check if mercury is connected, connect slots
        self.display_message('Looking for Mercury at %s...' % self.feed.visa_address)
        if self.feed.mercury.connected:
            self.update_gui_connection(connected=True)

        # start (stop) updates of GUI when mercury is connected (disconnected)
        # adjust clickable buttons upon connect / disconnect
        self.feed.connected_signal.connect(self.update_gui_connection)

        # get new readings when available, send as out signals
        self.feed.new_readings_signal.connect(self.fetch_readings)
        # update plot when new data arrives
        self.feed.new_readings_signal.connect(self.on_new_readings)
        # check for overheating when new data arrives
        self.feed.new_readings_signal.connect(self._check_overheat)

        # set up logging to file
        self.setup_logging()

# =================== BASIC UI SETUP ==========================================

    def restore_geometry(self):
        x = CONF.get('Window', 'x')
        y = CONF.get('Window', 'y')
        w = CONF.get('Window', 'width')
        h = CONF.get('Window', 'height')

        self.setGeometry(x, y, w, h)

    def save_geometry(self):
        geo = self.geometry()
        CONF.set('Window', 'height', geo.height())
        CONF.set('Window', 'width', geo.width())
        CONF.set('Window', 'x', geo.x())
        CONF.set('Window', 'y', geo.y())

    def exit_(self):
        self.feed.exit_()
        self.save_geometry()
        self.deleteLater()

    def closeEvent(self, event):
        self.exit_()

    def set_up_menubar(self):
        """
        Connects menu bar items to callbacks, sets their initial activation.
        """
        # connect to callbacks
        self.showLogAction.triggered.connect(self.on_log_clicked)
        self.exitAction.triggered.connect(self.exit_)
        self.readingsAction.triggered.connect(self.on_readings_clicked)
        self.connectAction.triggered.connect(self.feed.connect)
        self.disconnectAction.triggered.connect(self.feed.disconnect)
        self.updateAddressAction.triggered.connect(self.connection_dialog.open)

        # initially disable menu bar items, will be enabled later individually
        self.connectAction.setEnabled(True)
        self.disconnectAction.setEnabled(False)
        self.modulesAction.setEnabled(False)
        self.readingsAction.setEnabled(False)

    def on_slider_changed(self):
        # determine first plotted data point
        if self.xdata.size == 0:
            x_min = -self.horizontalSlider.value()
        else:
            x_min = max(-self.horizontalSlider.value(), self.xdata_zero[0])

        self.timeLabel.setText('Show last %s min' % self.horizontalSlider.value())
        self.canvas.set_xmin(x_min)
        self.canvas.p0.autoBtnClicked()
        self.canvas.p1.autoBtnClicked()

    @QtCore.Slot(bool)
    def update_gui_connection(self, connected):
        if connected:
            self.display_message('Connection established.')
            self.led.setChecked(True)

            # enable / disable menu bar items
            self.connectAction.setEnabled(False)
            self.disconnectAction.setEnabled(True)
            self.modulesAction.setEnabled(True)
            self.readingsAction.setEnabled(True)

            # connect user input to change mercury settings
            self.t2_edit.returnPressed.connect(self.change_t_setpoint)
            self.r1_edit.returnPressed.connect(self.change_ramp)
            self.r2_checkbox.clicked.connect(self.change_ramp_auto)
            self.gf1_edit.returnPressed.connect(self.change_flow)
            self.gf2_checkbox.clicked.connect(self.change_flow_auto)
            self.h1_edit.returnPressed.connect(self.change_heater)
            self.h2_checkbox.clicked.connect(self.change_heater_auto)

        elif not connected:
            self.display_error('Connection lost.')
            logger.info('Connection to MercuryiTC lost.')
            self.led.setChecked(False)

            # enable / disable menu bar items
            self.connectAction.setEnabled(True)
            self.disconnectAction.setEnabled(False)
            self.modulesAction.setEnabled(False)
            self.readingsAction.setEnabled(False)

            # disconnect user input from mercury
            self.t2_edit.returnPressed.disconnect(self.change_t_setpoint)
            self.r1_edit.returnPressed.disconnect(self.change_ramp)
            self.r2_checkbox.clicked.disconnect(self.change_ramp_auto)
            self.gf1_edit.returnPressed.disconnect(self.change_flow)
            self.gf2_checkbox.clicked.disconnect(self.change_flow_auto)
            self.h1_edit.returnPressed.disconnect(self.change_heater)
            self.h2_checkbox.clicked.disconnect(self.change_heater_auto)

    def set_input_validators(self):
        """ Sets validators for input fields"""
        self.t2_edit.setValidator(QtGui.QDoubleValidator())
        self.r1_edit.setValidator(QtGui.QDoubleValidator())
        self.gf1_edit.setValidator(QtGui.QDoubleValidator())
        self.h1_edit.setValidator(QtGui.QDoubleValidator())

    def display_message(self, text):
        self.statusbar.showMessage('%s' % text, 5000)

    def display_error(self, text):
        self.statusbar.showMessage('%s' % text)

    @QtCore.Slot(object)
    def fetch_readings(self, readings):
        """
        Parses readings for the MercuryMonitorApp and updates UI accordingly
        """
        # heater signals
        self.h1_label.setText('Heater, %s V:' % readings['HeaterVolt'])
        self.h1_edit.updateValue(readings['HeaterPercent'])

        is_heater_auto = readings['HeaterAuto'] == 'ON'
        self.h1_edit.setReadOnly(is_heater_auto)
        self.h1_edit.setEnabled(not is_heater_auto)
        self.h2_checkbox.setChecked(is_heater_auto)

        # gas flow signals
        self.gf1_edit.updateValue(readings['FlowPercent'])
        self.gf1_label.setText('Gas flow (min = %s%%):' % readings['FlowMin'])

        is_gf_auto = readings['FlowAuto'] == 'ON'
        self.gf2_checkbox.setChecked(is_gf_auto)
        self.gf1_edit.setEnabled(not is_gf_auto)
        self.gf1_edit.setReadOnly(is_gf_auto)

        # temperature signals
        self.t1_reading.setText('%s K' % round(readings['Temp'], 3))
        self.t2_edit.updateValue(readings['TempSetpoint'])
        self.r1_edit.updateValue(readings['TempRamp'])

        is_ramp_enable = readings['TempRampEnable'] == 'ON'
        self.r2_checkbox.setChecked(is_ramp_enable)

    @QtCore.Slot(object)
    def on_new_readings(self, readings):
        # append data for plotting
        self.xdata = np.append(self.xdata, time.time())
        self.ydata_tmpr = np.append(self.ydata_tmpr, readings['Temp'])
        self.ydata_gflw = np.append(self.ydata_gflw, readings['FlowPercent'] / 100)
        self.ydata_htr = np.append(self.ydata_htr, readings['HeaterPercent'] / 100)

        # prevent data vector from exceeding 86400 entries (~24h)
        self.xdata = self.xdata[-86400:]
        self.ydata_tmpr = self.ydata_tmpr[-86400:]
        self.ydata_gflw = self.ydata_gflw[-86400:]
        self.ydata_htr = self.ydata_htr[-86400:]

        # convert xData to minutes and set current time to t = 0
        self.xdata_zero = (self.xdata - max(self.xdata)) / 60

        self.update_plot()

    @QtCore.Slot()
    def update_plot(self):
        # determine first plotted data point
        if self.xdata.size == 0:
            x_min = -self.horizontalSlider.value()
        else:
            x_min = max(-self.horizontalSlider.value(), self.xdata_zero[0])

        # update plot
        self.canvas.update_data(self.xdata_zero, self.ydata_tmpr,
                                self.ydata_gflw, self.ydata_htr)
        self.canvas.set_xmin(x_min)

# =================== LOGGING DATA ============================================

    def setup_logging(self):
        """
        Set up logging of temperature history to files.
        Save temperature history to log file at '~/.CustomXepr/LOG_FILES/'
        after every 10 min.
        """
        # find user home directory
        home_path = os.path.expanduser('~')
        self.logging_path = os.path.join(home_path, '.mercurygui', 'LOG_FILES')

        # create folder '~/.CustomXepr/LOG_FILES' if not present
        if not os.path.exists(self.logging_path):
            os.makedirs(self.logging_path)
        # set logging file path
        self.log_file = os.path.join(self.logging_path, 'temperature_log ' +
                                     time.strftime("%Y-%m-%d_%H-%M-%S") + '.txt')

        t_save = 10  # time interval to save temperature data in min
        self.new_file = True  # create new log file for every new start
        self.save_timer = QtCore.QTimer()
        self.save_timer.setInterval(t_save*60*1000)
        self.save_timer.setSingleShot(False)  # set to reoccur
        self.save_timer.timeout.connect(self.log_temperature_data)
        self.save_timer.start()

    def save_temperature_data(self, path=None):
        # prompt user for file path if not given
        if path is None:
            text = 'Select path for temperature data file:'
            path = QtWidgets.QFileDialog.getSaveFileName(caption=text)
            path = path[0]

        if not path.endswith('.txt'):
            path += '.txt'

        title = 'temperature trace, saved on ' + time.strftime('%d/%m/%Y') + '\n'
        heater_vlim = self.feed.heater.vlim
        header = '\t'.join(['Time (sec)', 'Temperature (K)',
                            'Heater (%% of %sV)' % heater_vlim, 'Gas flow (%)'])

        data_matrix = np.concatenate((self.xdata[:, np.newaxis],
                                      self.ydata_tmpr[:, np.newaxis],
                                      self.ydata_htr[:, np.newaxis],
                                      self.ydata_gflw[:, np.newaxis]), axis=1)

        # noinspection PyTypeChecker
        np.savetxt(path, data_matrix, delimiter='\t', header=title + header)

    def log_temperature_data(self):
        # save temperature data to log file
        if self.feed.mercury.connected:
            self.save_temperature_data(self.log_file)

# =================== CALLBACKS FOR SETTING CHANGES ===========================

    @QtCore.Slot()
    def change_t_setpoint(self):
        new_t = self.t2_edit.value()

        if 3.5 < new_t < 300:
            self.display_message('T_setpoint = %s K' % new_t)
            self.feed.control.t_setpoint = new_t
        else:
            self.display_error('Error: Only temperature setpoints between ' +
                               '3.5 K and 300 K allowed.')

    @QtCore.Slot()
    def change_ramp(self):
        self.feed.control.ramp = self.r1_edit.value()
        self.display_message('Ramp = %s K/min' % self.r1_edit.value())

    @QtCore.Slot(bool)
    def change_ramp_auto(self, checked):
        if checked:
            self.feed.control.ramp_enable = 'ON'
            self.display_message('Ramp is turned ON')
        else:
            self.feed.control.ramp_enable = 'OFF'
            self.display_message('Ramp is turned OFF')

    @QtCore.Slot()
    def change_flow(self):
        self.feed.control.flow = self.gf1_edit.value()
        self.display_message('Gas flow  = %s%%' % self.gf1_edit.value())

    @QtCore.Slot(bool)
    def change_flow_auto(self, checked):
        if checked:
            self.feed.control.flow_auto = 'ON'
            self.display_message('Gas flow is automatically controlled.')
            self.gf1_edit.setReadOnly(True)
            self.gf1_edit.setEnabled(False)
        else:
            self.feed.control.flow_auto = 'OFF'
            self.display_message('Gas flow is manually controlled.')
            self.gf1_edit.setReadOnly(False)
            self.gf1_edit.setEnabled(True)

    @QtCore.Slot()
    def change_heater(self):
        self.feed.control.heater = self.h1_edit.value()
        self.display_message('Heater power  = %s%%' % self.h1_edit.value())

    @QtCore.Slot(bool)
    def change_heater_auto(self, checked):
        if checked:
            self.feed.control.heater_auto = 'ON'
            self.display_message('Heater is automatically controlled.')
            self.h1_edit.setReadOnly(True)
            self.h1_edit.setEnabled(False)
        else:
            self.feed.control.heater_auto = 'OFF'
            self.display_message('Heater is manually controlled.')
            self.h1_edit.setReadOnly(False)
            self.h1_edit.setEnabled(True)

    @QtCore.Slot(object)
    def _check_overheat(self, readings):
        if readings['Temp'] > 310:
            self.display_error('Over temperature!')
            self.feed.control.heater_auto = 'OFF'
            self.feed.control.heater = 0

# ========================== CALLBACKS FOR MENU BAR ===========================

    @QtCore.Slot()
    def on_readings_clicked(self):
        # create readings overview window if not present
        if self.readingsWindow is None:
            self.readingsWindow = ReadingsOverview(self.feed.mercury)
        # show it
        self.readingsWindow.show()

    @QtCore.Slot()
    def on_log_clicked(self):
        """
        Opens directory with log files with current log file selected.
        """

        if platform.system() == 'Windows':
            os.startfile(self.logging_path)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', self.logging_path])
        else:
            subprocess.Popen(['xdg-open', self.logging_path])


# noinspection PyUnresolvedReferences
class ReadingsTab(QtWidgets.QWidget):

    EXCEPT = ['read', 'write', 'query', 'CAL_INT', 'EXCT_TYPES',
              'TYPES', 'clear_cache']

    def __init__(self, mercury, module):
        super(self.__class__, self).__init__()

        self.module = module
        self.mercury = mercury

        self.name = module.nick
        self.attr = dir(module)

        self.gridLayout = QtWidgets.QGridLayout(self)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName('gridLayout_%s' % self.name)

        self.label = QtWidgets.QLabel(self)
        self.label.setObjectName('label_%s' % self.name)
        self.gridLayout.addWidget(self.label, 0, 0, 1, 2)

        self.comboBox = QtWidgets.QComboBox(self)
        self.comboBox.setObjectName('comboBox_%s' % self.name)
        self.gridLayout.addWidget(self.comboBox, 1, 0, 1, 1)

        self.lineEdit = QtWidgets.QLineEdit(self)
        self.lineEdit.setObjectName('lineEdit_%s' % self.name)
        self.gridLayout.addWidget(self.lineEdit, 1, 1, 1, 1)

        readings = [x for x in self.attr if not (x.startswith('_') or x in self.EXCEPT)]
        self.comboBox.addItems(readings)

        self.comboBox.currentIndexChanged.connect(self.get_reading)
        self.comboBox.currentIndexChanged.connect(self.get_alarms)

        self.get_reading()
        self.get_alarms()

    def get_reading(self):
        """ Gets readings of selected variable in combobox."""

        reading = getattr(self.module, self.comboBox.currentText())
        if isinstance(reading, tuple):
            reading = ''.join(map(str, reading))
        reading = str(reading)
        self.lineEdit.setText(reading)

    def get_alarms(self):
        """Gets alarms of associated module."""

        # get alarms for all modules
        address = self.module.address.split(':')
        short_address = address[1]
        if self.module.nick == 'LOOP':
            short_address = short_address.split('.')
            short_address = short_address[0] + '.loop1'
        try:
            alarm = self.mercury.alarms[short_address]
        except KeyError:
            alarm = '--'

        self.label.setText('Alarms: %s' % alarm)


class ReadingsOverview(QtWidgets.QDialog):

    def __init__(self, mercury):
        super(self.__class__, self).__init__()
        self.mercury = mercury
        self.setupUi(self)

        # refresh readings every 3 sec
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.get_readings)
        self.timer.start(3000)

    def setupUi(self, Form):
        Form.setObjectName('Mercury ITC Readings Overview')
        Form.resize(500, 142)
        self.masterGrid = QtWidgets.QGridLayout(Form)
        self.masterGrid.setObjectName('gridLayout')

        # create main tab widget
        self.tabWidget = QtWidgets.QTabWidget(Form)
        self.tabWidget.setObjectName('tabWidget')

        # create a tab with combobox and text box for each module
        self.readings_tabs = []

        for module in self.mercury.modules:
            new_tab = ReadingsTab(self.mercury, module)
            self.readings_tabs.append(new_tab)
            self.tabWidget.addTab(new_tab, module.nick)

        # add tab widget to main grid
        self.masterGrid.addWidget(self.tabWidget, 0, 0, 1, 1)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def get_readings(self):
        """
        Getting alarms of selected tab and update its selected reading, only
        if QWidget is not hidden.
        """
        if self.isVisible():
            self.tabWidget.currentWidget().get_reading()
            self.tabWidget.currentWidget().get_alarms()


def run(test_data=''):

    from mercuryitc import MercuryITC
    from mercurygui.config.main import CONF

    mercury_address = CONF.get('Connection', 'VISA_ADDRESS')
    visa_library = CONF.get('Connection', 'VISA_LIBRARY')

    mercury = MercuryITC(mercury_address, visa_library, open_timeout=1)

    app = QtWidgets.QApplication(sys.argv)
    app.aboutToQuit.connect(app.deleteLater)

    feed = MercuryFeed(mercury)
    mercury_gui = MercuryMonitorApp(feed)
    mercury_gui.show()

    if test_data != '':
        data_matrix = np.loadtxt(test_data, skiprows=2)
        mercury_gui.xdata = np.array(data_matrix[:, 0])
        mercury_gui.ydata_tmpr = np.array(data_matrix[:, 1])
        mercury_gui.ydata_htr = np.array(data_matrix[:, 2])
        mercury_gui.ydata_gflw = np.array(data_matrix[:, 3])
        mercury_gui.xdata_zero = (mercury_gui.xdata - max(mercury_gui.xdata)) / 60.0

        mercury_gui.update_plot()

    app.exec_()


if __name__ == '__main__':
    run('/Users/samschott/Documents/Python/PopulateGUI/temperature_log 2019-02-13_22-35-23.txt')
