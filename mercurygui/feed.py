# -*- coding: utf-8 -*-
"""
@author: Sam Schott  (ss2151@cam.ac.uk)

(c) Sam Schott; This work is licensed under a Creative Commons
Attribution-NonCommercial-NoDerivs 2.0 UK: England & Wales License.

"""
from PyQt5 import QtCore, QtWidgets
import sys
import logging
from mercuryitc.mercury_driver import MercuryITC_TEMP

from mercurygui.config.main import CONF

logger = logging.getLogger(__name__)


class MercuryFeed(QtCore.QObject):
    """
    Provides a data feed from the MercuryiTC with the most important readings of the gas
    flow, heater and temperature modules. This enables other programs to get readings from
    the feed and reduces direct communication with the mercury.

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
        >>> from mercurygui.feed import MercuryFeed
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
    """

    new_readings_signal = QtCore.pyqtSignal(dict)
    connected_signal = QtCore.pyqtSignal(bool)

    def __init__(self, mercury, refresh=1):
        super(self.__class__, self).__init__()

        self.refresh = refresh
        self.mercury = mercury
        self.rm = mercury.rm

        # start worker in thread
        self.thread = QtCore.QThread()
        self.worker = DataCollectionWorker(self.refresh, self.mercury)
        self.worker.moveToThread(self.thread)
        self.worker.readings_signal.connect(self._get_data)
        self.worker.connected_signal.connect(self.connected_signal.emit)

        self.thread.started.connect(self.worker.run)
        self.thread.start()

        self.connected = False

    # BASE FUNCTIONALITY CODE

    def connect(self):
        if not self.mercury.connected:
            self.mercury.connect()

        if self.mercury.connected:
            self.worker.running = True
            self.connected = True
            self.connected_signal.emit(True)
        else:
            self.worker.running = False
            self.connected = False

    def disconnect(self):
        self.connected_signal.emit(False)
        self.worker.running = False
        self.connected = False
        self.mercury.disconnect()

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

    @property
    def temperature_module_nick(self):
        return self.worker.temp_nick

    @property
    def temperature(self):
        return self.worker.temperature

    @property
    def heater(self):
        return self.worker.heater

    @property
    def gasflow(self):
        return self.worker.gasflow

    def select_temp_sensor(self, nick):
        """
        Updates module list after the new modules have been selected.
        """
        self.worker.select_temp_sensor(nick)

    def _get_data(self, readings_from_thread):
        self.readings = readings_from_thread
        self.new_readings_signal.emit(self.readings)

    def __repr__(self):
        return '<{}({})>'.format(self.__class__.__name__, self.mercury)


class DataCollectionWorker(QtCore.QObject):

    readings_signal = QtCore.pyqtSignal(object)
    connected_signal = QtCore.pyqtSignal(bool)

    def __init__(self, refresh, mercury):
        QtCore.QObject.__init__(self)

        self.refresh = refresh
        self.mercury = mercury
        self.temp_nick = CONF.get("MercuryFeed", "temperature_module")

        self.temperature = None
        self.heater = None
        self.gasflow = None

        self.readings = {}

        self.running = False
        self.terminate = False

    def run(self):
        while not self.terminate:
            if self.running:
                try:
                    if not self.temperature:
                        self.select_temp_sensor(self.temp_nick)

                    self.get_readings()
                    QtCore.QThread.sleep(int(self.refresh))
                except Exception:
                    self.connected_signal.emit(False)
                    self.running = False
                    logger.warning('Connection to MercuryiTC lost.')

            elif not self.running:
                QtCore.QThread.msleep(int(self.refresh*1000))

    def get_readings(self):

        # update assigned modules
        htr_nick = self.temperature.loop_htr
        aux_nick = self.temperature.loop_aux

        self.heater = next((m for m in self.mercury.modules if m.nick == htr_nick), None)
        self.gasflow = next((m for m in self.mercury.modules if m.nick == aux_nick), None)

        # read temperature data
        self.readings['Temp'] = self.temperature.temp[0]
        self.readings['TempSetpoint'] = self.temperature.loop_tset
        self.readings['TempRamp'] = self.temperature.loop_rset
        self.readings['TempRampEnable'] = self.temperature.loop_rena

        # read heater data
        if self.heater:  # if heater is configured for temperature sensor
            self.readings['HeaterVolt'] = self.heater.volt[0]
            self.readings['HeaterAuto'] = self.temperature.loop_enab
            self.readings['HeaterPercent'] = self.temperature.loop_hset
        else:  # if no heater is configured
            self.readings['HeaterVolt'] = float('nan')
            self.readings['HeaterAuto'] = 'OFF'
            self.readings['HeaterPercent'] = 0  # 'NaN' values are not accepted by spinbox

        # read gas flow data
        if self.gasflow:  # if aux module is configured for temperature sensor
            self.readings['FlowAuto'] = self.temperature.loop_faut
            self.readings['FlowPercent'] = self.gasflow.perc[0]
            self.readings['FlowMin'] = self.gasflow.gmin
            self.readings['FlowSetpoint'] = self.temperature.loop_fset
        else:  # if no aux module is configured
            self.readings['FlowAuto'] = 'OFF'
            self.readings['FlowPercent'] = 0  # 'NaN' values are not accepted by spinbox
            self.readings['FlowMin'] = float('nan')
            self.readings['FlowSetpoint'] = float('nan')

        # read alarms
        alarms = self.mercury.alarms

        uids = [m.uid for m in (self.temperature, self.gasflow, self.heater) if m]

        for key in list(alarms.keys()):
            if key not in uids:
                del alarms[key]

        self.readings['Alarms'] = alarms

        self.readings_signal.emit(self.readings)

    def select_temp_sensor(self, temp_nick):
        """
        Updates module list after the new modules have been selected.
        """
        # find all temperature modules
        tmp_modules = list(
            m for m in self.mercury.modules if type(m) is MercuryITC_TEMP
        )

        # find match for given nick
        match = next((m for m in tmp_modules if m.nick == temp_nick), None)

        if match:
            self.temperature = match
        elif tmp_modules:
            print(
                'Temperature sensor "{}" not found, choosing first module'.format(
                    temp_nick
                )
            )
            self.temperature = tmp_modules[0]
            self.temp_nick = tmp_modules[0].nick
        else:
            raise RuntimeError("No temperature modules found")

        CONF.set("MercuryFeed", "temperature_module", self.temp_nick)


if __name__ == '__main__':

    from mercuryitc import MercuryITC

    app = QtWidgets.QApplication(sys.argv)

    address = CONF.get('Connection', 'VISA_ADDRESS')
    mercury_instance = MercuryITC(address)
    feed = MercuryFeed(mercury_instance)

    sys.exit(app.exec_())
