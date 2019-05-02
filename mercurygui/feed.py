# -*- coding: utf-8 -*-

"""
Created on Tue Aug 23 11:03:57 2016

@author: Sam Schott  (ss2151@cam.ac.uk)

(c) Sam Schott; This work is licensed under a Creative Commons
Attribution-NonCommercial-NoDerivs 2.0 UK: England & Wales License.

"""
from __future__ import division, absolute_import
from qtpy import QtCore, QtWidgets
import sys
import logging
from mercuryitc.mercury_driver import MercuryITC_TEMP

from mercurygui.config.main import CONF

logger = logging.getLogger(__name__)


class MercuryFeed(QtCore.QObject):
    """
    Provides a data feed from the MercuryiTC with the most important readings of the gas
    flow, heater and temperature modules. This enables other programs to get readings from
    the feed and reduced direct communication with the mercury.

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

        # get default modules to read from
        self.temp_nick = CONF.get('MercuryFeed', 'temperature_module')

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
            # start data collection thread
            self.thread = QtCore.QThread()
            self.worker = DataCollectionWorker(self.refresh, self.mercury, self.temp_nick)
            self.worker.moveToThread(self.thread)
            self.worker.readings_signal.connect(self._get_data)
            self.worker.connected_signal.connect(self.connected_signal.emit)
            self.update_modules(self.temp_nick)
            self.thread.started.connect(self.worker.run)
            self.thread.start()

    def update_modules(self, temp_nick):
        """
        Updates module list after the new modules have been selected.
        """
        self.worker.update_modules(temp_nick)

        self.temperature = self.worker.temperature
        self.heater = self.worker.heater
        self.gasflow = self.worker.gasflow

    def _get_data(self, readings_from_thread):
        self.readings = readings_from_thread
        self.new_readings_signal.emit(self.readings)

    def __repr__(self):
        return '<%s(%s)>' % (type(self).__name__, self.visa_address)


class DataCollectionWorker(QtCore.QObject):

    readings_signal = QtCore.Signal(object)
    connected_signal = QtCore.Signal(bool)

    def __init__(self, refresh, mercury, temp_mod_number):
        QtCore.QObject.__init__(self)
        self.refresh = refresh
        self.mercury = mercury
        self.temp_mod_number = temp_mod_number

        self.readings = {}
        self.update_modules(self.temp_mod_number)

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
        # read temperature data
        self.readings['Temp'] = self.temperature.temp[0]
        self.readings['TempSetpoint'] = self.temperature.loop_tset
        self.readings['TempRamp'] = self.temperature.loop_rset
        self.readings['TempRampEnable'] = self.temperature.loop_rena

        # read heater data
        if self.heater is not None:  # if heater is configured for temperature sensor
            self.readings['HeaterVolt'] = self.heater.volt[0]
            self.readings['HeaterAuto'] = self.temperature.loop_enab
            self.readings['HeaterPercent'] = self.temperature.loop_hset
        else:  # if no heater is configured
            self.readings['HeaterVolt'] = float('nan')
            self.readings['HeaterAuto'] = 'OFF'
            self.readings['HeaterPercent'] = 0  # 'NaN' values are not accepted by spinbox
        # read gas flow data
        if self.gasflow is not None:  # if aux module is configured for temperature sensor
            self.readings['FlowAuto'] = self.temperature.loop_faut
            self.readings['FlowPercent'] = self.gasflow.perc[0]
            self.readings['FlowMin'] = self.gasflow.gmin
            self.readings['FlowSetpoint'] = self.temperature.loop_fset
        else:  # if no aux module is configured
            self.readings['FlowAuto'] = 'OFF'
            self.readings['FlowPercent'] = 0  # 'NaN' values are not accepted by spinbox
            self.readings['FlowMin'] = float('nan')
            self.readings['FlowSetpoint'] = float('nan')

        self.readings_signal.emit(self.readings)

    def update_modules(self, temp_nick):
        """
        Updates module list after the new modules have been selected.
        """
        # find all temperature modules
        temp_mods = [m for m in self.mercury.modules if type(m) == MercuryITC_TEMP]
        if len(temp_mods) == 0:
            raise IOError('The MercuryITC does not have any connected temperature modules.')
        # find the temperature module with given UID, otherwise default to the 1st module
        self.temperature = next((m for m in temp_mods if m.nick == temp_nick), temp_mods[0])

        htr_nick = self.temperature.loop_htr
        aux_nick = self.temperature.loop_aux

        self.heater = next((m for m in self.mercury.modules if m.nick == htr_nick), None)
        self.gasflow = next((m for m in self.mercury.modules if m.nick == aux_nick), None)


if __name__ == '__main__':

    from mercuryitc import MercuryITC

    app = QtWidgets.QApplication(sys.argv)

    address = CONF.get('Connection', 'VISA_ADDRESS')
    mercury_instance = MercuryITC(address)
    feed = MercuryFeed(mercury_instance)

    sys.exit(app.exec_())
