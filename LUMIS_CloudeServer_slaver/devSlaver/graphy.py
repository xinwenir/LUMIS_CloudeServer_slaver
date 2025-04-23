from UI.PlotUI import Ui_Form
import pyqtgraph as pg
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import numpy as np
from devSlaver.slaver import slaver
from copy import copy
from dataLayer import calculationTools
import dataLayer


#单通道能谱图像
class subPlotWin_singal(Ui_Form,QWidget):
    def __init__(self,local: slaver,*args):
        super(subPlotWin_singal, self).__init__(*args)
        self.slaver = local
        self.setupUi(self)
        self.retranslateUi(self)
        self.setMore()
        self.setEvent()

    def setMore(self):
        self.plotItem = pg.PlotItem()   # 图像对象
        self.plotDataItem = pg.PlotDataItem()   # 图像数据对象
        self.bars = np.arange(2**12)    # x轴数据
        self.graphicsView.setBackground("w")    # 设置背景为白色
        self.graphicsView.setCentralItem(self.plotItem)
        self.plotItem.addItem(self.plotDataItem)
        self.spinBox_baseLine.setValue(435)     # 设置默认的基线
        self.horizontalSlider_baseLine.setValue(435)
        self.plotItem.showGrid(True,True)
        #设置板子数
        if self.slaver.h5.data.shape[0] > 100:
            board = np.unique(self.slaver.h5.data[:100, 38])
        else:
            board = np.unique(self.slaver.h5.data[:, 38])
        boardNum = np.max(board)
        self.spinBox_board.setMaximum(boardNum)
        #初始化数据
        data = self.slaver.h5.getData(-2)
        self.index = data.shape[0]
        self.ESdata = calculationTools.ToEnergySpectrumData(data)
        self.plotUpdate()
        #定时更新数据
        self.timber = QTimer()
        self.timber.timeout.connect(self.dataUpdate)
        self.timber.start(5*10**3)



    def setEvent(self):
        # change base line
        self.spinBox_baseLine.valueChanged.connect(self.changeBaseLine)
        self.horizontalSlider_baseLine.valueChanged.connect(self.changeBaseLine)
        self.spinBox_board.valueChanged.connect(self.plotUpdate)
        self.spinBox_channel.valueChanged.connect(self.plotUpdate)

    # 更新数据
    @pyqtSlot()
    def dataUpdate(self):
        data = self.slaver.h5.getData(-2,self.index)
        self.index += data.shape[0]
        self.ESdata += calculationTools.ToEnergySpectrumData(data)
        self.plotUpdate()

    # 更新图像
    def plotUpdate(self):
        # 获取仓库中能谱
        y = copy(self.ESdata[self.spinBox_board.value(),self.spinBox_channel.value()])
        np.place(y, self.bars[:-1] < self.spinBox_baseLine.value(),[0])
        self.label_count.setText(str(np.sum(y)))
        self.plotDataItem.setData(self.bars[:-1], y, fillLevel=0, fillOutline=False, brush=(0,0,255,150),
                                  pen = pg.mkPen((0,0,255,150)))

    # 更改基线
    @pyqtSlot(int)
    def changeBaseLine(self,new: int):
        self.spinBox_baseLine.setValue(new)
        self.horizontalSlider_baseLine.setValue(new)
        self.plotUpdate()

#触发事件图像
class boardBarsPlot(QWidget):
    def __init__(self,*args, boardNum: int):
        super(boardBarsPlot, self).__init__(*args)
        self.boardNum = boardNum
        self.setMore()
        self.setEvent()

    def setMore(self):
        self.setGeometry(300, 300, 1400, 150)
        self.boardData = np.zeros(32,'int64')
        self.setMinimumSize(850, 120)
        self.barSize = 5
        palette = QPalette()
        palette.setColor(self.backgroundRole(), QColor(255,255,255))
        self.setPalette(palette)

    def setEvent(self):
        pass

    def mousePressEvent(self, a0: QMouseEvent) -> None:
        super(boardBarsPlot, self).mousePressEvent(a0)
        print(a0.pos())

    # 设置数据
    def setBoardData(self, data: np.array):
        if data.shape[0] >= 36 and len(data.shape) == 1:
            self.boardData = data
        else:
            raise ValueError('The shape of argument(data) should be (36+,)')

    # 绘图事件
    def paintEvent(self, a0: QPaintEvent) -> None:
        #super(boardBarsPlot, self).paintEvent(a0)
        qp = QPainter()
        qp.begin(self)
        self.drawingTitile(qp)
        self.drawingTriangle(qp)
        self.drawingHistogram(qp)
        qp.end()

    # 辅助函数：绘制标题
    def drawingTitile(self, qp: QPainter):
        pen = QPen(Qt.black)
        qp.setPen(pen)
        qp.setFont(QFont('SimSun', 8))
        rect = QRect(
            QPoint(int(0.2/34 * self.size().width()),int(2 / 10 * self.size().height())),
            QPoint(int(1/34 * self.size().width()), int(6 / 10 * self.size().height()))
        )
        qp.drawText(rect, Qt.AlignCenter, '第\n{}\n层'.format(self.boardNum))

    # 辅助函数：绘制直方图函数
    def drawingHistogram(self, qp: QPainter):
        # 绘制x轴
        pen = QPen(Qt.black)
        qp.setPen(pen)
        line = QLine(
            int(1/34 * self.size().width()), int(4.5 / 10 * self.size().height()),
            int(33/34 * self.size().width()),int(4.5 / 10 * self.size().height())
                     )
        qp.drawLine(line)
        # 绘制标签
        if self.size().width() > 1500:
            fontPointSize = 8
        elif self.size().width() > 1000:
            fontPointSize = 5 + (self.size().width() - 1000) / 166
        else:
            fontPointSize = 5
        qp.setFont(QFont('SimSun', fontPointSize))
        for i in range(32):
            rect = QRect(
                QPoint(int((i + 0.5)/34 * self.size().width()), int(4.5 / 10 * self.size().height())),
                QPoint(int((i + 2.5) / 34 * self.size().width()), int(4.5 / 10 * self.size().height() + 15))
                         )
            qp.drawText(rect, Qt.AlignCenter, str(dataLayer._Index[i]))
            len = QLine(
                QPoint(int((i+1.5)/34 * self.size().width()), int(4.5 / 10 * self.size().height() + 2)),
                QPoint(int((i + 1.5) / 34 * self.size().width()), int(4.5 / 10 * self.size().height()))
            )
            qp.drawLine(len)
        # 绘制数据bar
        pen = QPen(QColor(0, 0, 0, alpha=0))
        qp.setPen(pen)
        brush = QBrush(QColor('#0497DE'))
        qp.setBrush(brush)

        maxHeight = 0.5 / 10 * self.size().height() - 4.5 / 10 * self.size().height() - 1
        for i in range(32):
            if self.boardData[i] != 0:
                h = maxHeight * self.boardData[i] / 1000
                rect = QRect(
                    QPoint(int((i+1.5)/34 * self.size().width() - self.barSize), int(4.5 / 10 * self.size().height() - 1 + h)),
                    QPoint(int((i+1.5)/34 * self.size().width() + self.barSize), int(4.5 / 10 * self.size().height() - 1))
                )
                qp.drawRect(rect)

    #辅助函数：绘制三角形
    def drawingTriangle(self,qp: QPainter):
        up = True
        for i in range(32):
            # 设置颜色变化
            if self.boardData[i] == 0:
                brush = QBrush(QColor('#37DE6A'))
            elif self.boardData[i] > 800:
                brush = QBrush(QColor(255, 0, 0))
            else:
                r = int((800 - self.boardData[i]) / (800 - 150) * 255)
                brush = QBrush(QColor(255, r, r))
            qp.setBrush(brush)

            pen = QPen(Qt.white, 1, Qt.SolidLine)
            qp.setPen(pen)

            polygon = self.trianglePointF(i, up)
            up = not up
            qp.drawConvexPolygon(polygon)
            fontPointSize = int(1 / 150 * (self.size().width() ** 2 + self.size().width() ** 2) ** 0.5 - 3)
            qp.setFont(QFont('SimSun', fontPointSize))

            rect = QRect(
                QPoint(int((i + 0.5) / 34 * self.size().width()), int(6 / 10 * self.size().height())),
                QPoint(int((i + 2.5) / 34 * self.size().width()), int(9 / 10 * self.size().height()))
            )
            qp.drawText(rect, Qt.AlignCenter, str(self.boardData[i]))

    # 辅助函数：返回第i个三角形对象
    def trianglePointF(self, vertex_x: int, upsideDown: bool):
        p = vertex_x + 0.5
        if upsideDown:
            return QPolygonF([
                QPoint(int(p / 34 * self.size().width()), int(6 / 10 * self.size().height())),
                QPoint(int((p + 2) / 34 * self.size().width()), int(6 / 10 * self.size().height())),
                QPoint(int((p + 1) / 34 * self.size().width()), int(9 / 10 * self.size().height()))
            ])
        else:
            return QPolygonF([
                QPoint(int(p / 34 * self.size().width()), int(9 / 10 * self.size().height())),
                QPoint(int((p + 2) / 34 * self.size().width()), int(9 / 10 * self.size().height())),
                QPoint(int((p + 1) / 34 * self.size().width()), int(6 / 10 * self.size().height()))
            ])


class subPlotWin_eventTrackShow(QScrollArea):
    def __init__(self, local: slaver,*args):
        super(subPlotWin_eventTrackShow, self).__init__(*args)
        self.slaver = local
        self.setMore()


    def setMore(self):
        self.setWindowTitle('触发事件')
        self.boardList = []
        self.containerWidget = QWidget()
        #获取层数
        if self.slaver.h5.data.shape[0] > 100:
            board = np.unique(self.slaver.h5.data[:100, 38])
        elif self.slaver.h5.data.shape[0]  == 0:
            print("Didn't have enough data to plot.")
            return
        else:
            board = np.unique(self.slaver.h5.data[:, 38])
        boardNum = np.max(board)+1

        self.containerWidget.setMinimumSize(700, 140 * boardNum +10)
        self.containerWidget.setLayout(QVBoxLayout(self.containerWidget))
        for i in range(boardNum):
            b = boardBarsPlot(boardNum=i)
            self.boardList.append(b)
            self.containerWidget.layout().addWidget(b)
        self.setWidget(self.containerWidget)

        # 获取第一次的数据
        self.index_memory = self.slaver.h5.data.shape[0]
        if self.index_memory > 200:
            data = self.slaver.h5.getData(-2, startIndex=self.index_memory - 200)
        else:
            data = self.slaver.h5.getData(-2)
        goodEvent = calculationTools.ChooseGoodEvent(data)
        self.setData(goodEvent.values)
        self.containerWidget.repaint()

        #设置定时更新数据
        self.timer = QTimer()
        self.timer.timeout.connect(self.dataUpdate)
        self.timer.start(5*1000)


    def setData(self, data: np.array):
        if data.shape[1] >= 38:
            for i in range(data.shape[0]):
                self.boardList[i].setBoardData(data[i])
        else:
            raise ValueError('The shape of argument(data) should be (39,1~8)')


    def dataUpdate(self):
        data = self.slaver.h5.getData(-2,startIndex=self.index_memory)
        self.index_memory += data.shape[0]
        event = calculationTools.ChooseGoodEvent(data)
        self.setData(event.values)
        self.containerWidget.repaint()


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    sl = slaver()
    win = subPlotWin_singal(sl)
    win.show()
    print("stop")
    app.exec_()
    print("close")


