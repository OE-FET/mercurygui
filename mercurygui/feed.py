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
    flow, heater and temperature modules.
    """

    readings_signal = QtCore.pyqtSignal(dict)
    connected_signal = QtCore.pyqtSignal(bool)

    def __init__(self, mercury, temperature, refresh=1):
        super(self.__class__, self).__init__()

        self.mercury = mercury

        # start worker in thread
        self.thread = QtCore.QThread()
        self.worker = DataCollectionWorker(refresh, self.mercury, temperature)
        self.worker.moveToThread(self.thread)
        self.worker.readings_signal.connect(self.readings_signal.emit)
        self.worker.connected_signal.connect(self.connected_signal.emit)

        self.thread.started.connect(self.worker.run)
        self.thread.start()

    @property
    def refresh(self):
        return self.worker.refresh

    @refresh.setter
    def refresh(self, seconds):
        self.worker.refresh = seconds

    @property
    def temperature(self):
        return self.worker.temperature

    @temperature.setter
    def temperature(self, module):
        self.worker.temperature = module

    @property
    def heater(self):
        return self.worker.heater

    @property
    def gasflow(self):
        return self.worker.gasflow

    def exit_(self):
        if self.worker:
            self.worker.terminate = True
            self.thread.terminate()
            self.thread.wait()

        if self.mercury.connected:
            self.mercury.disconnect()
            self.connected_signal.emit(False)

        self.deleteLater()

    def __repr__(self):
        return "<{}({})>".format(self.__class__.__name__, self.mercury)


class DataCollectionWorker(QtCore.QObject):

    readings_signal = QtCore.pyqtSignal(object)
    connected_signal = QtCore.pyqtSignal(bool)

    def __init__(self, refresh, mercury, temperature_module):
        QtCore.QObject.__init__(self)

        self.mercury = mercury

        self.temperature = temperature_module
        self.gasflow = None
        self.heater = None

        self.terminate = False
        self.refresh = refresh
        self.readings = {}

    def run(self):
        while not self.terminate:
            try:
                self.get_readings()
                QtCore.QThread.msleep(int(self.refresh * 1000))
            except Exception:
                self.connected_signal.emit(False)

    def get_readings(self):

        # update assigned modules
        htr_nick = self.temperature.loop_htr
        aux_nick = self.temperature.loop_aux

        self.heater = next(
            (m for m in self.mercury.modules if m.nick == htr_nick), None
        )
        self.gasflow = next(
            (m for m in self.mercury.modules if m.nick == aux_nick), None
        )

        # read temperature data
        self.readings["Temp"] = self.temperature.temp[0]
        self.readings["TempSetpoint"] = self.temperature.loop_tset
        self.readings["TempRamp"] = self.temperature.loop_rset
        self.readings["TempRampEnable"] = self.temperature.loop_rena

        # read heater data
        if self.heater:  # if heater is configured for temperature sensor
            self.readings["HeaterVolt"] = self.heater.volt[0]
            self.readings["HeaterAuto"] = self.temperature.loop_enab
            self.readings["HeaterPercent"] = self.temperature.loop_hset
        else:  # if no heater is configured
            self.readings["HeaterVolt"] = float("nan")
            self.readings["HeaterAuto"] = "OFF"
            self.readings["HeaterPercent"] = 0  # 'NaN' values are not accepted by spinbox

        # read gas flow data
        if self.gasflow:  # if aux module is configured for temperature sensor
            self.readings["FlowAuto"] = self.temperature.loop_faut
            self.readings["FlowPercent"] = self.gasflow.perc[0]
            self.readings["FlowMin"] = self.gasflow.gmin
            self.readings["FlowSetpoint"] = self.temperature.loop_fset
        else:  # if no aux module is configured
            self.readings["FlowAuto"] = "OFF"
            self.readings["FlowPercent"] = 0  # 'NaN' values are not accepted by spinbox
            self.readings["FlowMin"] = float("nan")
            self.readings["FlowSetpoint"] = float("nan")

        # read alarms
        alarms = self.mercury.alarms

        uids = [m.uid for m in (self.temperature, self.gasflow, self.heater) if m]

        for key in list(alarms.keys()):
            if key not in uids:
                del alarms[key]

        self.readings["Alarms"] = alarms

        self.readings_signal.emit(self.readings)
