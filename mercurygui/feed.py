# -*- coding: utf-8 -*-

"""
Created on Tue Aug 23 11:03:57 2016

@author: Sam Schott  (ss2151@cam.ac.uk)

(c) Sam Schott; This work is licensed under a Creative Commons
Attribution-NonCommercial-NoDerivs 2.0 UK: England & Wales License.

"""
from __future__ import division, absolute_import
from qtpy import QtCore, QtWidgets, uic
import sys
import os
import logging

from mercurygui.config.main import CONF

logger = logging.getLogger(__name__)


class MercuryFeed(QtCore.QObject):
    """
    Provides a data feed from the MercuryiTC with the most important readings
    of the gas flow, heater, temperature sensor and control loop modules. This
    enables other programs to get readings from the feed and reduced direct
    communication with the mercury.

    New data from the selected modules is emitted by the :attr:`new_readings_signal`
    as a dictionary with entries:

    - Heater data:
        'HeaterVolt'       # current heater voltage in V (float)
        'HeaterAuto'       # automatic or manual control of heater (bool)
        'HeaterPercent'    # heater percentage of maximum (float)

    - Gas flow data:
        'FlowAuto'         # automatic or manual control of needle valve (bool)
        'FlowPercent'      # actual needle valve opening in percent (float)
        'FlowMin'          # needle valve minimum allowed opening (float)
        'FlowSetpoint'     # needle valve opening setpoint in percent (float)

    - Temperature data:
        'Temp'             # actual temperature in K (float)
        'TempSetpoint'     # temperature setpoint in K (float)
        'TempRamp'         # temperature ramp speed in K/min (float)
        'TempRampEnable'   # ramp enabled or disabled (bool)

    You can receive the emitted readings as follows:

        >>> from mercuryitc import MercuryITC
        >>> from mercurygui import MercuryFeed
        >>> # connect to mercury and start data feed
        >>> m = MercuryITC('VISA_ADDRESS')
        >>> feed = MercuryFeed(m)
        >>> # example function that prints temperature reading
        >>> def print_temperature(readings):
        ...     print('T = %s Kelvin' % readings['Temp'])
        >>> # connect signal to function
        >>> connection = feed.new_readings_signal.connect(print_temperature)

    :func:`print_temperature` will then be executed with the emitted readings
    dictionary as argument every time a new signal is emitted.

    :class:`MercuryFeed` will also handle maintaining the connection for you:: it will
    periodically try to find the MercuryiTC if not connected, and emit warnings
    when it looses an established connection.
    """

    new_readings_signal = QtCore.Signal(dict)
    notify_signal = QtCore.Signal(str)
    connected_signal = QtCore.Signal(bool)

    def __init__(self, mercury, refresh=1):
        super(self.__class__, self).__init__()

        self.refresh = refresh
        self.mercury = mercury
        self.visa_address = mercury.visa_address
        self.visa_library = mercury.visa_library
        self.rm = mercury.rm

        self.thread = None
        self.worker = None

        if self.mercury.connected:
            self.start_worker()
            self.connected_signal.emit(True)

    # BASE FUNCTIONALITY CODE

    def disconnect(self):
        # stop worker thread
        if self.worker:
            self.worker.running = False

        # disconnect mercury
        self.connected_signal.emit(False)
        self.mercury.disconnect()

    def connect(self):
        # connect to mercury
        if not self.mercury.connected:
            self.mercury.connect()

        if self.mercury.connected:
            # start / resume worker
            self.start_worker()
            self.connected_signal.emit(True)

    def exit_(self):
        if self.worker:
            self.worker.running = False
            self.worker.terminate = True
            self.thread.terminate()
            self.thread.wait()

        if self.mercury.connected:
            self.mercury.disconnect()
            self.connected_signal.emit(False)
        self.deleteLater()

# CODE TO INTERACT WITH MERCURYITC

    def start_worker(self):
        """
        Start a thread to periodically update readings.
        """
        if self.worker and self.thread:
            self.worker.running = True
        else:
            self.dialog = SensorDialog(self.mercury.modules)
            self.dialog.accepted.connect(self.update_modules)

            # start data collection thread
            self.thread = QtCore.QThread()
            self.worker = DataCollectionWorker(self.refresh, self.mercury,
                                               self.dialog.modNumbers)
            self.worker.moveToThread(self.thread)
            self.worker.readings_signal.connect(self._get_data)
            self.worker.connected_signal.connect(self.connected_signal.emit)
            self.thread.started.connect(self.worker.run)
            self.update_modules(self.dialog.modNumbers)
            self.thread.start()

    def update_modules(self, mod_numbers):
        """
        Updates module list after the new modules have been selected in dialog.
        """
        self.gasflow = self.mercury.modules[mod_numbers['gasflow']]
        self.heater = self.mercury.modules[mod_numbers['heater']]
        self.temperature = self.mercury.modules[mod_numbers['temperature']]
        self.control = self.mercury.modules[mod_numbers['temperature'] + 1]

        # send new modules to thread if running
        self.worker.update_modules(mod_numbers)

    def _get_data(self, readings_from_thread):
        self.readings = readings_from_thread
        self.new_readings_signal.emit(self.readings)

    def __repr__(self):
        return '<%s(%s)>' % (type(self).__name__, self.visa_address)


class SensorDialog(QtWidgets.QDialog):
    """
    Provides a user dialog to select the modules for the feed.
    """

    accepted = QtCore.Signal(object)

    def __init__(self, mercury_modules):
        super(self.__class__, self).__init__()
        uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                'module_dialog.ui'), self)

        num = len(mercury_modules)
        temp_modules_nick = []
        self.temp_modules = []
        gas_modules_nick = []
        self.gas_modules = []
        heat_modules_nick = []
        self.heat_modules = []

        self.modNumbers = {}

        for i in range(num-1, -1, -1):
            address = mercury_modules[i].address
            type_ = address.split(':')[-1]
            nick = mercury_modules[i].nick
            if type_ == 'AUX':
                gas_modules_nick.append(nick)
                self.gas_modules.append(i)
            elif type_ == 'HTR':
                heat_modules_nick.append(nick)
                self.heat_modules.append(i)
            elif type_ == 'TEMP':
                if nick not in temp_modules_nick:
                    temp_modules_nick.append(nick)
                    self.temp_modules.append(i)

        self.comboBox.addItems(temp_modules_nick)
        self.comboBox_2.addItems(gas_modules_nick)
        self.comboBox_3.addItems(heat_modules_nick)

        # get default modules
        self.comboBox.setCurrentIndex(CONF.get('MercuryFeed', 'temperature_module'))
        self.comboBox_2.setCurrentIndex(CONF.get('MercuryFeed', 'gasflow_module'))
        self.comboBox_3.setCurrentIndex(CONF.get('MercuryFeed', 'heater_module'))

        self.modNumbers['temperature'] = self.temp_modules[self.comboBox.currentIndex()]
        self.modNumbers['gasflow'] = self.gas_modules[self.comboBox_2.currentIndex()]
        self.modNumbers['heater'] = self.heat_modules[self.comboBox_3.currentIndex()]

        self.buttonBox.accepted.connect(self._on_accept)

    def _on_accept(self):
        self.modNumbers['temperature'] = self.temp_modules[self.comboBox.currentIndex()]
        self.modNumbers['gasflow'] = self.gas_modules[self.comboBox_2.currentIndex()]
        self.modNumbers['heater'] = self.heat_modules[self.comboBox_3.currentIndex()]

        # update default modules
        CONF.set('MercuryFeed', 'temperature_module', self.comboBox.currentIndex())
        CONF.set('MercuryFeed', 'gasflow_module', self.comboBox_2.currentIndex())
        CONF.set('MercuryFeed', 'heater_module', self.comboBox_3.currentIndex())

        self.accepted.emit(self.modNumbers)


class DataCollectionWorker(QtCore.QObject):

    readings_signal = QtCore.Signal(object)
    connected_signal = QtCore.Signal(bool)

    def __init__(self, refresh, mercury, mod_numbers):
        QtCore.QObject.__init__(self)
        self.refresh = refresh
        self.mercury = mercury
        self.mod_numbers = mod_numbers

        self.readings = {}
        self.update_modules(self.mod_numbers)

        self.running = True
        self.terminate = False

    def run(self):
        while not self.terminate:
            if self.running:
                try:
                    # proceed with full update
                    self.get_readings()
                    # sleep until next scheduled refresh
                    QtCore.QThread.sleep(int(self.refresh))
                except Exception:
                    # emit signal if connection is lost
                    self.connected_signal.emit(False)
                    # stop worker thread
                    self.running = False
                    self.mercury.connected = False
                    logger.warning('Connection to MercuryiTC lost.')
            elif not self.running:
                QtCore.QThread.msleep(int(self.refresh*1000))
                if self.mercury.connected:
                    self.running = True

    def get_readings(self):
        # read heater data
        self.readings['HeaterVolt'] = self.heater.volt[0]
        self.readings['HeaterAuto'] = self.control.heater_auto
        self.readings['HeaterPercent'] = self.control.heater

        # read gas flow data
        self.readings['FlowAuto'] = self.control.flow_auto
        self.readings['FlowPercent'] = self.gasflow.perc[0]
        self.readings['FlowMin'] = self.gasflow.gmin
        self.readings['FlowSetpoint'] = self.control.flow

        # read temperature data
        self.readings['Temp'] = self.temperature.temp[0]
        self.readings['TempSetpoint'] = self.control.t_setpoint
        self.readings['TempRamp'] = self.control.ramp
        self.readings['TempRampEnable'] = self.control.ramp_enable

        self.readings_signal.emit(self.readings)

    def update_modules(self, mod_numbers):
        """
        Updates module list after the new modules have been selected in dialog.
        """
        self.gasflow = self.mercury.modules[mod_numbers['gasflow']]
        self.heater = self.mercury.modules[mod_numbers['heater']]
        self.temperature = self.mercury.modules[mod_numbers['temperature']]
        self.control = self.mercury.modules[mod_numbers['temperature'] + 1]


if __name__ == '__main__':

    from mercuryitc import MercuryITC

    app = QtWidgets.QApplication(sys.argv)

    address = CONF.get('Connection', 'VISA_ADDRESS')
    m = MercuryITC(address)
    feed = MercuryFeed(m)

    sys.exit(app.exec_())
