# -*- coding: utf-8 -*-
"""
@author: Sam Schott  (ss2151@cam.ac.uk)

(c) Sam Schott; This work is licensed under a Creative Commons
Attribution-NonCommercial-NoDerivs 2.0 UK: England & Wales License.

"""
import sys
import pyqtgraph as pg
from pyqtgraph import AxisItem, PlotItem, GraphicsView
from pyqtgraph import functions as fn
from qtpy import QtWidgets, QtCore, QtGui

from .pyqt_labutils.dark_mode_support import LINE_COLOR_DARK, LINE_COLOR_LIGHT, isDarkWindow


pg.setConfigOptions(antialias=True, exitCleanup=False)


class TemperatureHistoryPlot(GraphicsView):

    GREEN = (0, 204, 153)
    BLUE = (100, 171, 246)
    RED = (221, 61, 53)

    LIGHT_BLUE = BLUE + (51,)
    LIGHT_RED = RED + (51,)

    if sys.platform == 'darwin':
        LW = 3
    else:
        LW = 1.5

    _xmin = -1
    _xmax = round(-0.006*_xmin, 4)

    def __init__(self):
        GraphicsView.__init__(self)

        # create layout
        self.layout = pg.GraphicsLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(-1.)
        self.layout.layout.setRowPreferredHeight(1, 200)
        self.layout.layout.setRowPreferredHeight(2, 20)
        self.setBackground(None)
        self.setCentralItem(self.layout)

        # create axes and apply formatting
        axisItems1 = dict()
        axisItems2 = dict()

        for pos in ['bottom', 'left', 'top', 'right']:
            axisItems1[pos] = AxisItem(orientation=pos, maxTickLength=-4)
            axisItems2[pos] = AxisItem(orientation=pos, maxTickLength=-4)

        self.p0 = PlotItem(axisItems=axisItems1)
        self.p1 = PlotItem(axisItems=axisItems2)
        self.layout.addItem(self.p0, 0, 0, 5, 1)
        self.layout.addItem(self.p1, 5, 0, 1, 1)

        # estimate maximum width of x-labels and set axis width accordingly
        label = QtWidgets.QLabel('299')
        text_width = label.fontMetrics().boundingRect(label.text()).width()

        for p in [self.p0, self.p1]:
            p.vb.setBackgroundColor('w')
            p.setContentsMargins(1., 0., 1., 0.)
            for pos in ['bottom', 'left', 'top', 'right']:
                ax = p.getAxis(pos)
                ax.setZValue(0)  # draw on top of patch
                ax.setVisible(True)  # make all axes visible
                ax.setPen(width=self.LW*2/3, color=0.5)  # grey spines and ticks
                ax.setTextPen('k')  # black text
                ax.setStyle(
                    maxTickLevel=1,
                    autoExpandTextSpace=False,
                    tickTextOffset=4
                )
                if pos in ['left', 'right']:
                    ax.setStyle(tickTextWidth=text_width + 5)

            p.getAxis('top').setTicks([])
            p.getAxis('right').setTicks([])

        # light grey for internal spine
        self.p1.getAxis('top').setPen(width=self.LW*2/3, color=LINE_COLOR_LIGHT)

        # get total axis width and make accessible to the outside
        self.y_axis_width = self.p0.getAxis('left').maximumWidth() + 1

        # set visibility and width of axes
        self.p0.getAxis('bottom').setVisible(False)
        self.p0.getAxis('bottom').setHeight(0)
        self.p1.getAxis('left').setTicks([])
        self.p1.getAxis('top').setHeight(0)

        # set default ranges to start
        self.p0.setXRange(self._xmin, self._xmax, 4)
        self.p0.setYRange(5, 300)
        self.p0.setLimits(xMin=self._xmin, xMax=self._xmax,
                          yMin=0, yMax=500, minYRange=2.1)
        self.p1.setYRange(-0.02, 1.02)
        self.p1.setLimits(xMin=self._xmin, xMax=self._xmax,
                          yMin=-0.05, yMax=1.05, minYRange=1.1)

        # link x-axes
        self.p1.setXLink(self.p0)

        # override default padding with constant 0.2% padding
        self.p0.vb.suggestPadding = lambda x: 0.006
        self.p1.vb.suggestPadding = lambda x: 0.006

        # set auto range and mouse panning / zooming
        self.p0.enableAutoRange(x=True, y=True)
        self.p1.enableAutoRange(x=False, y=False)
        self.p0.setMouseEnabled(x=True, y=True)
        self.p1.setMouseEnabled(x=True, y=False)

        # enable downsampling and clipping to improve plot performance
        self.p0.setDownsampling(auto=True, mode='subsample')
        self.p0.setClipToView(True)

        self.p1.setDownsampling(auto=True, mode='subsample')
        self.p1.setClipToView(True)

        # create plot items
        self.p_tempr = self.p0.plot([self.get_xmin(), 0], [-1, -1],
                                    pen=pg.mkPen(self.GREEN, width=self.LW))
        self.p_htr = self.p1.plot([self.get_xmin(), 0], [0, 0],
                                  pen=pg.mkPen(self.RED, width=self.LW),
                                  fillLevel=0, fillBrush=self.LIGHT_RED)
        self.p_gflw = self.p1.plot([self.get_xmin(), 0], [0, 0],
                                   pen=pg.mkPen(self.BLUE, width=self.LW),
                                   fillLevel=0, fillBrush=self.LIGHT_BLUE)

        # update colors
        self.update_darkmode()

    def update_data(self, x_data, y_data_t, y_data_g, y_data_h):
        self.p_tempr.setData(x_data, y_data_t)
        self.p_gflw.setData(x_data, y_data_g)
        self.p_htr.setData(x_data, y_data_h)

    def set_xmin(self, value):
        self._xmin = value
        self._xmax = round(-0.006*value, 4)
        self.p0.setLimits(xMin=self._xmin, xMax=self._xmax,
                          yMin=0, yMax=500, minYRange=2.1)
        self.p1.setLimits(xMin=self._xmin, xMax=self._xmax,
                          yMin=-0.05, yMax=1.05, minYRange=1.1)

    def get_xmin(self):
        return self._xmin

    def changeEvent(self, QEvent):

        if QEvent.type() == QtCore.QEvent.PaletteChange:
            self.update_darkmode()

    def update_darkmode(self):

        # get colors
        bg_color = self.palette().color(QtGui.QPalette.Base)
        bg_color_rgb = [bg_color.red(), bg_color.green(), bg_color.blue()]
        font_color = self.palette().color(QtGui.QPalette.Text)
        font_color_rgb = [font_color.red(), font_color.green(), font_color.blue()]

        # set colors
        self.setBackground(None)
        for p in [self.p0, self.p1]:
            p.vb.setBackgroundColor(bg_color_rgb)
            for pos in ['bottom', 'left', 'top', 'right']:
                ax = p.getAxis(pos)
                ax.setTextPen(fn.mkColor(font_color_rgb))  # black text

        c = LINE_COLOR_DARK if isDarkWindow() else LINE_COLOR_LIGHT
        self.p1.getAxis('top').setPen(width=self.LW*2/3, color=c)


if __name__ == '__main__':

    import sys

    app = QtWidgets.QApplication(sys.argv)
    app.aboutToQuit.connect(app.deleteLater)

    view = TemperatureHistoryPlot()
    view.show()

    app.exec_()
