# -*- coding: utf-8 -*-
import sys
import pyqtgraph as pg
from pyqtgraph import AxisItem, PlotItem, GraphicsView
from pyqtgraph import getConfigOption
from pyqtgraph import functions as fn
import numpy as np
from qtpy import QtWidgets

pg.setConfigOptions(antialias=True, exitCleanup=False)


class MyAxisItem(AxisItem):

    _textPen = None

    def textPen(self):
        if self._textPen is None:
            return fn.mkPen(getConfigOption('foreground'))
        return fn.mkPen(self._textPen)

    def setTextPen(self, *args, **kwargs):
        """
        Set the pen used for drawing text.
        If no arguments are given, the default foreground color will be used.
        """
        self.picture = None
        if args or kwargs:
            self._textPen = fn.mkPen(*args, **kwargs)
        else:
            self._textPen = fn.mkPen(getConfigOption('foreground'))
        self.labelStyle['color'] = '#' + fn.colorStr(self._textPen.color())[:6]
        self.setLabel()
        self.update()

    def tickSpacing(self, minVal, maxVal, size):

        """Return values describing the desired spacing and offset of ticks.

        This method is called whenever the axis needs to be redrawn and is a
        good method to override in subclasses that require control over tick locations.

        The return value must be a list of tuples, one for each set of ticks::

            [
                (major tick spacing, offset),
                (minor tick spacing, offset),
                (sub-minor tick spacing, offset),
                ...
            ]
        """
        # First check for override tick spacing
        if self._tickSpacing is not None:
            return self._tickSpacing

        dif = abs(maxVal - minVal)
        if dif == 0:
            return []

        # decide optimal minor tick spacing in pixels (this is just aesthetics)
        optimalTickCount = max(2., np.log(size))

        # optimal minor tick spacing
        optimalSpacing = dif / optimalTickCount

        # the largest power-of-10 spacing which is smaller than optimal
        p10unit = 10 ** np.floor(np.log10(optimalSpacing))

        # Determine major/minor tick spacings which flank the optimal spacing.
        intervals = np.array([1., 2., 10., 20., 100.]) * p10unit
        minorIndex = 0
        while intervals[minorIndex+1] <= optimalSpacing:
            minorIndex += 1

        levels = [
            (intervals[minorIndex+2], 0),
            (intervals[minorIndex+1], 0),
        ]

        if self.style['maxTickLevel'] >= 2:
            # decide whether to include the last level of ticks
            minSpacing = min(size / 20., 30.)
            maxTickCount = size / minSpacing
            if dif / intervals[minorIndex] <= maxTickCount:
                levels.append((intervals[minorIndex], 0))

        return levels

    def drawPicture(self, p, axisSpec, tickSpecs, textSpecs):

        p.setRenderHint(p.Antialiasing, False)
        p.setRenderHint(p.TextAntialiasing, True)

        # draw long line along axis
        pen, p1, p2 = axisSpec
        p.setPen(pen)
        p.drawLine(p1, p2)
        p.translate(0.5, 0)  # resolves some damn pixel ambiguity

        # draw ticks
        for pen, p1, p2 in tickSpecs:
            p.setPen(pen)
            p.drawLine(p1, p2)

        # Draw all text
        if self.tickFont is not None:
            p.setFont(self.tickFont)
        p.setPen(self.textPen())
        for rect, flags, text in textSpecs:
            p.drawText(rect, flags, text)

        p.setPen(pen)

    def _updateMaxTextSize(self, x):
        # Informs that the maximum tick size orthogonal to the axis has
        # changed; we use this to decide whether the item needs to be resized
        # to accomodate.
        if self.orientation in ['left', 'right']:
            if x > self.textWidth or x < self.textWidth-10:
                self.textWidth = x
                if self.style['autoExpandTextSpace'] is True:
                    self._updateWidth()
        else:
            if x > self.textHeight or x < self.textHeight-10:
                self.textHeight = x
                if self.style['autoExpandTextSpace'] is True:
                    self._updateHeight()


class TemperatureHistoryPlot(GraphicsView):

    GREEN = (0, 204, 153)
    BLUE = (100, 171, 246)
    RED = (221, 61, 53)

    LIGHT_BLUE = BLUE + (51, )
    LIGHT_RED = RED + (51, )

    if sys.platform == 'darwin':
        LW = 3
    else:
        LW = 1.5

    _xmin = -1
    _xmax = round(-0.002*_xmin, 4)

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
            axisItems1[pos] = MyAxisItem(orientation=pos, maxTickLength=5)
            axisItems2[pos] = MyAxisItem(orientation=pos, maxTickLength=5)

        self.p0 = PlotItem(axisItems=axisItems1)
        self.p1 = PlotItem(axisItems=axisItems2)
        self.set_xmin(-1.)
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
                ax.setStyle(maxTickLevel=1, autoExpandTextSpace=False,
                            tickTextOffset=4)
                if pos in ['left', 'right']:
                    ax.setStyle(tickTextWidth=text_width + 5)

            p.getAxis('top').setTicks([])
            p.getAxis('right').setTicks([])

        # get total axis width and make accessible to the outside
        self.y_axis_width = self.p0.getAxis('left').maximumWidth() + 1

        # set visibility and width of axes
        self.p0.getAxis('bottom').setVisible(False)
        self.p0.getAxis('bottom').setHeight(0)
        self.p1.getAxis('left').setTicks([])
        self.p1.getAxis('top').setHeight(0)

        # set auto range and mouse panning / zooming
        self.p0.enableAutoRange(x=True, y=True)
        self.p1.enableAutoRange(x=False, y=False)
        self.p0.setMouseEnabled(x=True, y=True)
        self.p1.setMouseEnabled(x=True, y=False)

        # set default ranges to start
        self.p0.setXRange(self._xmin, self._xmax, 4)
        self.p0.setYRange(5, 300)
        self.p0.setLimits(xMin=self._xmin, xMax=self._xmax, yMin=0, yMax=500, minYRange=2.1)
        self.p1.setYRange(-0.02, 1.02)
        self.p1.setLimits(xMin=self._xmin, xMax=self._xmax, yMin=-0.02, yMax=1.02, minYRange=1.04)

        # link x-axes
        self.p1.setXLink(self.p0)

        # override default padding with constant 0.2% padding
        self.p0.vb.suggestPadding = lambda x: 0.002
        self.p1.vb.suggestPadding = lambda x: 0.002

        # enable downsampling and clipping to improve plot performance
        self.p0.setDownsampling(ds=True, auto=True, mode='subsample')
        self.p0.setClipToView(True)

        self.p1.setDownsampling(ds=True, auto=True, mode='subsample')
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

        self.p_htr_0 = self.p1.plot([self.get_xmin(), 0], [0, 0],
                                    pen=pg.mkPen(self.RED, width=self.LW))
        self.p_gflw_0 = self.p1.plot([self.get_xmin(), 0], [0, 0],
                                     pen=pg.mkPen(self.BLUE, width=self.LW))

    def update_data(self, x_data, y_data_t, y_data_g, y_data_h):
        self.p_tempr.setData(x_data, y_data_t)
        self.p_gflw.setData(x_data, y_data_g)
        self.p_htr.setData(x_data, y_data_h)

        y_data_baseline = np.zeros_like(x_data)
        self.p_htr_0.setData(x_data, y_data_baseline)
        self.p_htr_0.setData(x_data, y_data_baseline)

    def set_xmin(self, value):
        self._xmin = value
        self._xmax = round(-0.002*value, 4)
        self.p0.setLimits(xMin=self._xmin, xMax=self._xmax, yMin=0, yMax=500, minYRange=2.1)
        self.p1.setLimits(xMin=self._xmin, xMax=self._xmax, yMin=-0.02, yMax=1.02, minYRange=1.04)

    def get_xmin(self):
        return self._xmin


if __name__ == '__main__':

    import sys

    app = QtWidgets.QApplication(sys.argv)
    app.aboutToQuit.connect(app.deleteLater)

    view = TemperatureHistoryPlot()
    view.show()

    app.exec_()
