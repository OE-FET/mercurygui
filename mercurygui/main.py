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
from PyQt5 import QtCore, QtWidgets, uic
from mercuryitc.mercury_driver import MercuryITC_TEMP, MercuryITC_HTR, MercuryITC_AUX

# local imports
from mercurygui.feed import MercuryFeed
from mercurygui.pyqt_labutils import LedIndicator, ConnectionDialog
from mercurygui.pyqtplot_canvas import TemperatureHistoryPlot
from mercurygui.config.main import CONF

MAIN_UI_PATH = pkgr.resource_filename('mercurygui', 'main.ui')

logger = logging.getLogger(__name__)


# noinspection PyArgumentList
class MercuryMonitorApp(QtWidgets.QMainWindow):

    QUIT_ON_CLOSE = True

    MAX_DISPLAY = 24*60*60

    def __init__(self, mercury):
        super(self.__class__, self).__init__()
        uic.loadUi(MAIN_UI_PATH, self)

        self.mercury = mercury
        self.feed = MercuryFeed(mercury)

        # sent Title font size relative to the system's default size
        scaling = 1.8
        font = self.labelTitle.font()
        defaultFontSize = QtWidgets.QLabel('test').font().pointSize()
        fontSize = round(defaultFontSize*scaling, 1)
        font.setPointSize(fontSize)
        self.labelTitle.setFont(font)

        # create popup Widgets
        self.connectionDialog = ConnectionDialog(self, self.mercury, CONF)
        self.readingsDialog = None
        self.modulesDialog = None

        # create LED indicator
        self.led = LedIndicator(self)
        self.statusbar.addPermanentWidget(self.led)
        self.led.setChecked(False)

        # set up temperature plot, adjust window margins accordingly
        self.canvas = TemperatureHistoryPlot()
        self.gridLayoutCanvas.addWidget(self.canvas)
        w = self.canvas.y_axis_width
        self.gridLayoutTop.setContentsMargins(w, 0, w, 0)
        self.gridLayoutBottom.setContentsMargins(w, 0, w, 0)
        self.horizontalSlider.setMaximum(self.MAX_DISPLAY/60)

        # connect slider to plot
        self.horizontalSlider.valueChanged.connect(self.on_slider_changed)

        # adapt text edit colors to graph colors
        self.t1_reading.setStyleSheet('color:rgb%s' % str(self.canvas.GREEN))
        self.gf1_edit.setStyleSheet('color:rgb%s' % str(self.canvas.BLUE))
        self.h1_edit.setStyleSheet('color:rgb%s' % str(self.canvas.RED))
        self.gf1_edit.setMinimalStep(0.1)
        self.h1_edit.setMinimalStep(0.1)

        # set up data vectors for plot
        self.xdata = np.array([])
        self.xdata_min_zero = np.array([])
        self.ydata_tmpr = np.array([])
        self.ydata_gflw = np.array([])
        self.ydata_htr = np.array([])

        # restore previous window geometry
        self.restore_geometry()

        # connect to callbacks
        self.modulesAction.triggered.connect(self.on_module_selection_clicked)
        self.showLogAction.triggered.connect(self.on_log_clicked)
        self.exitAction.triggered.connect(self.exit_)
        self.readingsAction.triggered.connect(self.on_readings_clicked)
        self.connectAction.triggered.connect(self.feed.connect)
        self.disconnectAction.triggered.connect(self.feed.disconnect)
        self.updateAddressAction.triggered.connect(self.connectionDialog.open)

        self.t2_edit.returnPressed.connect(self.change_t_setpoint)
        self.r1_edit.returnPressed.connect(self.change_ramp)
        self.r2_checkbox.clicked.connect(self.change_ramp_auto)
        self.gf1_edit.returnPressed.connect(self.change_flow)
        self.gf2_checkbox.clicked.connect(self.change_flow_auto)
        self.h1_edit.returnPressed.connect(self.change_heater)
        self.h2_checkbox.clicked.connect(self.change_heater_auto)

        # initially disable menu bar items, will be enabled later individually
        self.connectAction.setEnabled(True)
        self.disconnectAction.setEnabled(False)
        self.modulesAction.setEnabled(False)
        self.readingsAction.setEnabled(False)

        self.build_sensor_menu()

        # initially disable controls, will be enabled later individually
        self.t2_edit.setEnabled(False)
        self.r1_edit.setEnabled(False)
        self.r2_checkbox.setEnabled(False)
        self.gf1_edit.setEnabled(False)
        self.gf2_checkbox.setEnabled(False)
        self.h1_edit.setEnabled(False)
        self.h2_checkbox.setEnabled(False)

        # check if mercury is connected, connect slots
        self.display_message('Looking for temperature controller at %s...' %
                             self.mercury.visa_address)
        self.update_gui_connection(self.feed.connected)

        # start (stop) updates of GUI when mercury is connected (disconnected)
        # adjust clickable buttons upon connect / disconnect
        self.feed.connected_signal.connect(self.update_gui_connection)

        # get new readings every second, update UI
        self.feed.new_readings_signal.connect(self.update_controls)
        self.feed.new_readings_signal.connect(self.update_plot)

        # set up logging to file
        self.setup_logging()

        self.feed.connect()

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
        if self.QUIT_ON_CLOSE:
            self.exit_()
        else:
            self.hide()

    def on_slider_changed(self):
        # determine first plotted data point
        sv = self.horizontalSlider.value()

        self.timeLabel.setText('Show last %s min' % sv)
        self.canvas.set_xmin(-sv)
        self.canvas.p0.setXRange(-sv, 0)
        self.canvas.p0.enableAutoRange(x=False, y=True)

    def build_sensor_menu(self):
        self.sensorMenu = QtWidgets.QMenu()
        self.sensorActionGroup = QtWidgets.QActionGroup(self)

        for nick in self._get_nicks(MercuryITC_TEMP):
            action = QtWidgets.QAction(nick)
            action.setData(nick)
            action.setCheckable(True)
            action.setChecked(nick == self.feed.temperature.nick)
            self.sensorMenu.addAction(action)
            self.sensorActionGroup.addAction(action)
            self.sensorActionGroup.triggered.connect(self.on_sensor_selected)

        self.sensorAction.setMenu(self.sensorMenu)

    @QtCore.pyqtSlot(bool)
    def update_gui_connection(self, connected):

        if connected:
            self.display_message('Connection established.')
            self.led.setChecked(True)

            # enable / disable menu bar items
            self.connectAction.setEnabled(False)
            self.disconnectAction.setEnabled(True)
            self.modulesAction.setEnabled(True)
            self.readingsAction.setEnabled(True)
            self.sensorAction.setEnabled(True)

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
            self.display_error('Connection lost.')
            logger.info('Connection to MercuryiTC lost.')
            self.led.setChecked(False)

            # enable / disable menu bar items
            self.connectAction.setEnabled(True)
            self.disconnectAction.setEnabled(False)
            self.modulesAction.setEnabled(False)
            self.readingsAction.setEnabled(False)

            # disable controls
            self.t2_edit.setEnabled(False)
            self.r1_edit.setEnabled(False)
            self.r2_checkbox.setEnabled(False)
            self.gf1_edit.setEnabled(False)
            self.gf2_checkbox.setEnabled(False)
            self.gf3_edit.setEnabled(False)
            self.h1_edit.setEnabled(False)
            self.h2_checkbox.setEnabled(False)

        self.build_sensor_menu()

    def display_message(self, text):
        self.statusbar.showMessage('%s' % text, 5000)

    def display_error(self, text):
        self.statusbar.showMessage('%s' % text)

    @QtCore.pyqtSlot(object)
    def update_controls(self, readings):
        """
        Parses readings for the MercuryMonitorApp and updates UI accordingly
        """

        # heater signals
        self.h1_label.setText('Heater, %s V:' % readings['HeaterVolt'])
        self.h1_edit.updateValue(readings['HeaterPercent'])

        if self.feed.heater:
            is_heater_auto = readings['HeaterAuto'] == 'ON'
            self.h1_edit.setReadOnly(is_heater_auto)
            self.h1_edit.setEnabled(not is_heater_auto)
            self.h2_checkbox.setChecked(is_heater_auto)
            self.h2_checkbox.setEnabled(True)
        else:
            self.h1_edit.setReadOnly(True)
            self.h1_edit.setEnabled(False)
            self.h2_checkbox.setEnabled(False)

        # gas flow signals
        self.gf1_edit.updateValue(readings['FlowPercent'])
        self.gf3_edit.updateValue(readings['FlowMin'])

        if self.feed.gasflow:
            is_gf_auto = readings['FlowAuto'] == 'ON'
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
        self.t1_reading.setText('%s K' % round(readings['Temp'], 3))
        self.t2_edit.updateValue(readings['TempSetpoint'])
        self.r1_edit.updateValue(readings['TempRamp'])

        is_ramp_enable = readings['TempRampEnable'] == 'ON'
        self.r2_checkbox.setChecked(is_ramp_enable)

        # alarms
        alarm_str = ''
        for k, v in readings['Alarms'].items():
            alarm_str += '{}: {} '.format(k, v)

        if alarm_str:
            self.alarm_label.setText('Alarms: ' + alarm_str)
            self.alarm_label.setStyleSheet('QLabel { color : red; }')
        else:
            self.alarm_label.setText('Alarms: --')
            self.alarm_label.setStyleSheet('')

    @QtCore.pyqtSlot(object)
    def update_plot(self, readings):
        # append data for plotting
        self.xdata = np.append(self.xdata, time.time())
        self.ydata_tmpr = np.append(self.ydata_tmpr, readings['Temp'])
        self.ydata_gflw = np.append(self.ydata_gflw, readings['FlowPercent'] / 100)
        self.ydata_htr = np.append(self.ydata_htr, readings['HeaterPercent'] / 100)

        # prevent data vector from exceeding MAX_DISPLAY
        self.xdata = self.xdata[-self.MAX_DISPLAY:]
        self.ydata_tmpr = self.ydata_tmpr[-self.MAX_DISPLAY:]
        self.ydata_gflw = self.ydata_gflw[-self.MAX_DISPLAY:]
        self.ydata_htr = self.ydata_htr[-self.MAX_DISPLAY:]

        # convert xData to minutes and set current time to t = 0
        self.xdata_min_zero = (self.xdata - self.xdata[-1]) / 60

        # update plot
        self.canvas.update_data(self.xdata_min_zero, self.ydata_tmpr,
                                self.ydata_gflw, self.ydata_htr)

    def clear_plot(self):
        # append data for plotting
        self.xdata = np.array([])
        self.xdata_min_zero = np.array([])
        self.ydata_tmpr = np.array([])
        self.ydata_gflw = np.array([])
        self.ydata_htr = np.array([])

        # update plot
        self.canvas.update_data(self.xdata, self.ydata_tmpr,
                                self.ydata_gflw, self.ydata_htr)

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

        # delete old log files
        now = time.time()
        days_to_keep = 7

        for f in os.listdir(self.logging_path):
            f = os.path.join(self.logging_path, f)
            if os.stat(f).st_mtime < now - days_to_keep*24*60*60:
                if os.path.isfile(f):
                    os.remove(f)

        # set up periodic logging
        t_save = 10  # time interval to save temperature data (min)
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

        header = '\t'.join(['Time (sec)', 'Temperature (K)',
                            'Heater (%)', 'Gas flow (%)'])

        data_matrix = np.concatenate((self.xdata[:, np.newaxis],
                                      self.ydata_tmpr[:, np.newaxis],
                                      self.ydata_htr[:, np.newaxis],
                                      self.ydata_gflw[:, np.newaxis]), axis=1)

        # noinspection PyTypeChecker
        np.savetxt(path, data_matrix, delimiter='\t', header=title + header, fmt='%f')

    def log_temperature_data(self):
        # save temperature data to log file
        if self.feed.connected:
            self.save_temperature_data(self.log_file)

# =================== CALLBACKS FOR SETTING CHANGES ===========================

    @QtCore.pyqtSlot()
    def change_t_setpoint(self):
        new_t = self.t2_edit.value()

        if 3.5 < new_t < 300:
            self.display_message('T_setpoint = %s K' % new_t)
            self.feed.temperature.loop_tset = new_t
        else:
            self.display_error('Error: Only temperature setpoints between ' +
                               '3.5 K and 300 K allowed.')

    @QtCore.pyqtSlot()
    def change_ramp(self):
        self.feed.temperature.loop_rset = self.r1_edit.value()
        self.display_message('Ramp = %s K/min' % self.r1_edit.value())

    @QtCore.pyqtSlot(bool)
    def change_ramp_auto(self, checked):
        if checked:
            self.feed.temperature.loop_rena = 'ON'
            self.display_message('Ramp is turned ON')
        else:
            self.feed.temperature.loop_rena = 'OFF'
            self.display_message('Ramp is turned OFF')

    @QtCore.pyqtSlot()
    def change_flow(self):
        self.feed.temperature.loop_fset = self.gf1_edit.value()
        self.display_message('Gas flow = %s%%' % self.gf1_edit.value())

    @QtCore.pyqtSlot()
    def change_flow_min(self):
        self.feed.gasflow.gmin = self.gf3_edit.value()
        self.display_message('Gas flow min = %s%%' % self.gf3_edit.value())

    @QtCore.pyqtSlot(bool)
    def change_flow_auto(self, checked):
        if checked:
            self.feed.temperature.loop_faut = 'ON'
            self.display_message('Gas flow is automatically controlled.')
            self.gf1_edit.setReadOnly(True)
            self.gf1_edit.setEnabled(False)
        else:
            self.feed.temperature.loop_faut = 'OFF'
            self.display_message('Gas flow is manually controlled.')
            self.gf1_edit.setReadOnly(False)
            self.gf1_edit.setEnabled(True)

    @QtCore.pyqtSlot()
    def change_heater(self):
        self.feed.temperature.loop_hset = self.h1_edit.value()
        self.display_message('Heater power  = %s%%' % self.h1_edit.value())

    @QtCore.pyqtSlot(bool)
    def change_heater_auto(self, checked):
        if checked:
            self.feed.temperature.loop_enab = 'ON'
            self.display_message('Heater is automatically controlled.')
            self.h1_edit.setReadOnly(True)
            self.h1_edit.setEnabled(False)
        else:
            self.feed.temperature.loop_enab = 'OFF'
            self.display_message('Heater is manually controlled.')
            self.h1_edit.setReadOnly(False)
            self.h1_edit.setEnabled(True)

# ========================== CALLBACKS FOR MENU BAR ===========================

    def on_sensor_selected(self, action):

        nick = action.data()

        try:
            self.feed.select_temp_sensor(nick)
        except IOError:
            # the selected module name does not exists -> rebuild our list
            self.build_sensor_menu()
        else:
            self.clear_plot()

    @QtCore.pyqtSlot()
    def on_readings_clicked(self):
        # create readings overview window if not present
        if self.readingsDialog is None:
            self.readingsDialog = ReadingsOverview(self.mercury)
        # show it
        self.readingsDialog.show()

    @QtCore.pyqtSlot()
    def on_module_selection_clicked(self):
        # create readings overview window if not present
        if self.modulesDialog is None:
            self.modulesDialog = ModulesDialog(self.mercury)
        # show it
        self.modulesDialog.open()

    @QtCore.pyqtSlot()
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

    def _get_nicks(self, sensor_type):
        if self.feed.connected:
            return list(m.nick for m in self.mercury.modules if type(m) == sensor_type)
        else:
            return []


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
        try:
            alarm = self.mercury.alarms[self.module.uid]
        except KeyError:
            alarm = '--'

        self.label.setText('Alarms: %s' % alarm)


class ReadingsOverview(QtWidgets.QDialog):

    def __init__(self, mercury, parent=None):
        super(self.__class__, self).__init__(parent=parent)
        self.setWindowTitle('Readings Overview')
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


class _NoModule:
    nick = 'None'


class ModulesDialog(QtWidgets.QDialog):
    """
    Provides a user dialog to select the modules for the feed.
    """

    accepted = QtCore.pyqtSignal(object)

    def __init__(self, mercury, parent=None):
        super(self.__class__, self).__init__(parent=parent)
        uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                'module_dialog.ui'), self)

        self.mercury = mercury

        self.temp_modules = self._get_modules_for_type(MercuryITC_TEMP)
        self.htr_modules = self._get_modules_for_type(MercuryITC_HTR)
        self.aux_modules = self._get_modules_for_type(MercuryITC_AUX)

        self.htr_modules.append(_NoModule())
        self.aux_modules.append(_NoModule())

        self.comboBoxTEMP.addItems([m.nick for m in self.temp_modules])
        self.comboBoxHTR.addItems([m.nick for m in self.htr_modules])
        self.comboBoxAUX.addItems([m.nick for m in self.aux_modules])

        # get current modules
        self.comboBoxTEMP.setCurrentIndex(0)
        self.comboBoxHTR.setCurrentText(self.temp_modules[0].loop_htr)
        self.comboBoxAUX.setCurrentText(self.temp_modules[0].loop_aux)

        # connect callbacks
        self.comboBoxTEMP.currentIndexChanged.connect(self.on_temp_selected)
        self.buttonBox.accepted.connect(self.on_accept)

    @QtCore.pyqtSlot(int)
    def on_temp_selected(self, index):
        # update content of heater and gasflow combo boxes
        self.comboBoxHTR.setCurrentText(self.temp_modules[index].loop_htr)
        self.comboBoxAUX.setCurrentText(self.temp_modules[index].loop_aux)

    @QtCore.pyqtSlot()
    def on_accept(self):
        # assign new heater and gasflow modules
        temp_index = self.comboBoxTEMP.currentIndex()
        htr_index = self.comboBoxHTR.currentIndex()
        aux_index = self.comboBoxAUX.currentIndex()

        self.temp_modules[temp_index].loop_htr = self.htr_modules[htr_index].nick
        self.temp_modules[temp_index].loop_aux = self.aux_modules[aux_index].nick

    def _get_modules_for_type(self, sensor_type):

        return [m for m in self.mercury.modules if type(m) is sensor_type]


def run():

    from mercuryitc import MercuryITC
    from mercurygui.config.main import CONF

    app = QtWidgets.QApplication(sys.argv)

    mercury_address = CONF.get('Connection', 'VISA_ADDRESS')
    visa_library = CONF.get('Connection', 'VISA_LIBRARY')

    mercury = MercuryITC(mercury_address, visa_library, open_timeout=1)

    mercury_gui = MercuryMonitorApp(mercury)
    mercury_gui.show()

    app.exec_()


if __name__ == '__main__':
    run()
