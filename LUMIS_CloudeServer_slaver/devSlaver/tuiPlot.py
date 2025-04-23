from devSlaver.slaver import slaver
from prompt_toolkit import prompt
from prompt_toolkit.validation import Validator
from terminaltables import AsciiTable
import os
from threading import Event
import time
import keyboard
from dataLayer.calculationTools import ChooseGoodEvent,translateTemperature
import plotext as plt
import numpy as np
from devSlaver import clearTerminal

class plotESInTerminal():
    def __init__(self,local: slaver):
        if local.h5.data.shape[0] > 100:
            board = np.unique(local.h5.data[:100, 38])
        elif local.h5.data.shape[0]  == 0:
            print("Didn't have enough data to plot.")
            return
        else:
            board = np.unique(local.h5.data[:, 38])
        boardNum = np.max(board)

        # 辅助函数——板子层数验证器
        def boardValidatorFunc(text: str):
            if text.isdigit():
                chn = int(text)
                if chn >= 0 and chn <= boardNum:
                    return True
            return False

        boardValidator = Validator.from_callable(
            boardValidatorFunc,
            error_message="you can only choose 0~{}".format(boardNum),
            move_cursor_to_end=True
        )

        self.chooseBoard = int(prompt("choose which board(0~{}): ".format(boardNum), validator=boardValidator))

        # 辅助函数——通道验证器
        def chnValidatorFunc(text: str):
            if text.isdigit():
                chn = int(text)
                if chn >= 0 and chn < 36:
                    return True
            return False

        chnValidator = Validator.from_callable(
            chnValidatorFunc,
            error_message="you can only choose 0~35",
            move_cursor_to_end=True
        )
        self.chooseChn = int(prompt("choose which chn(0~35): ", validator=chnValidator))



        # 开始读取数据和计算
        print("\rshow energy spectrum in terminal:\t\033[33m{}\033[0m\t".format("loading data"), end="")
        data = local.h5.data[:, [self.chooseChn, 38]]


        print("\rshow energy spectrum in terminal:\t\033[33m{}\033[0m\t".format("calculating data"), end="")
        boardIndex = (data[:, 1] == self.chooseBoard) & (data[:, 0] != 0)
        chn = data[boardIndex, 0]
        print("")

        # 计算能谱和边界
        self.maxIndex = data.shape[0]
        self.y, self.x = np.histogram(chn, bins=np.arange(4096))
        self.threshold = 460




        self.terminalCycleTag = Event()

        self.dataStorage = local



    def show(self):
        keyboard.add_hotkey("w", self.enlarge_w)
        keyboard.add_hotkey("d", self.enlarge_d)
        keyboard.add_hotkey("s", self.shrink_s)
        keyboard.add_hotkey("a", self.shrink_a)
        keyboard.add_hotkey("h", self.home_h)
        keyboard.add_hotkey("left", self.move_left)
        keyboard.add_hotkey("up", self.move_up)
        keyboard.add_hotkey("right", self.move_right)
        keyboard.add_hotkey("down", self.move_down)
        keyboard.add_hotkey("t", self.changeThreshold_t)
        keyboard.add_hotkey('q', self.stop)


        self.terminalCycleTag.set()
        self.home_h()

        while self.terminalCycleTag.is_set():
            if self.dataStorage.h5.data.shape[0] > self.maxIndex:
                data = self.dataStorage.h5.data[self.maxIndex:, [self.chooseChn, 38]]
                self.maxIndex += data.shape[0]
                boardIndex = (data[:, 1] == self.chooseBoard) & (data[:, 0] != 0)
                chn = data[boardIndex, 0]
                _y, _ = np.histogram(chn, bins=np.arange(4096))
                self.y += _y
                self.printPlot()
            for i in range(450):
                time.sleep(0.01)
                if not self.terminalCycleTag.is_set():
                    break
        clearTerminal()

    # 热键函数及连接热键
    def enlarge_w(self):
        self.high = (self.up - self.down) * 0.8
        self.up = self.high + self.down
        self.printPlot()

    def enlarge_d(self):
        self.width = (self.right - self.left) * 0.8
        self.right = self.width + self.left
        self.printPlot()

    def shrink_s(self):
        self.high = (self.up - self.down) / 0.8
        self.up = self.high + self.down
        self.printPlot()

    def shrink_a(self):
        self.width = (self.right - self.left) / 0.8
        self.right = self.width + self.left
        self.printPlot()

    def move_up(self):
        high = 0.1 * (self.up - self.down)
        self.up += high
        self.down += high
        self.printPlot()


    def move_down(self):
        high = 0.1 * (self.up - self.down)
        self.up -= high
        self.down -= high
        self.printPlot()

    def move_right(self):
        width = 0.1 * (self.right - self.left)
        self.right += width
        self.left += width
        self.printPlot()

    def move_left(self):
        width = 0.1 * (self.right - self.left)
        self.right -= width
        self.left -= width
        self.printPlot()

    def home_h(self):
        y = np.copy(self.y)
        y[:self.threshold] = 0
        self.right = np.max(self.x)
        self.left = np.min(self.x)
        self.up = np.max(y)
        self.down = np.min(y)
        self.printPlot()

    def changeThreshold_t(self):
        # 辅助函数——验证器
        def thresholdValidatorFunc(text: str):
            if text.isdigit():
                threshold = int(text)
                if threshold >= 0 and threshold < 4096:
                    return True
            return False

        thresholdValidator = Validator.from_callable(
            thresholdValidatorFunc,
            error_message="threshold should be int and less then 4096",
            move_cursor_to_end=True
        )
        self.threshold = int(prompt("change threshold as: ", validator=thresholdValidator))
        self.home_h()

    def stop(self):
        self.terminalCycleTag.clear()
        keyboard.remove_hotkey("w")
        keyboard.remove_hotkey("d")
        keyboard.remove_hotkey("s")
        keyboard.remove_hotkey("a")
        keyboard.remove_hotkey("h")
        keyboard.remove_hotkey("t")
        keyboard.remove_hotkey("left")
        keyboard.remove_hotkey("up")
        keyboard.remove_hotkey("down")
        keyboard.remove_hotkey("right")
        keyboard.remove_hotkey("q")


    def printPlot(self):
        clearTerminal()
        plt.clf()
        y = np.copy(self.y)
        y[:self.threshold] = 0
        plt.ylim(self.down, self.up)
        plt.xlim(self.left, self.right)
        plt.plot(y.tolist(), marker="*", fillx=0,
                 label="board_{} chn_{} threshold:{}".format(self.chooseBoard, self.chooseChn, self.threshold))
        plt.show()



class plotTriggerStatus():
    def __init__(self,local: slaver, terminalCycleTag:Event):
        maxIndex = local.h5.data.shape[0]
        if maxIndex > 200:
            data = local.h5.getData(-2, startIndex=maxIndex - 200)
        else:
            data = local.h5.getData(-2)
        self.goodEvent = ChooseGoodEvent(data)
        self.printPlot()

        terminalCycleTag.set()
        while terminalCycleTag.is_set():
            if local.h5.data.shape[0] > maxIndex:
                data = local.h5.getData(-2,startIndex=maxIndex)
                self.goodEvent = ChooseGoodEvent(data)
                self.printPlot()
            time.sleep(3)

    def printPlot(self):
        bs = ""
        header = []

        for i in range(self.goodEvent.shape[0]):
            header.append("board {}".format(i))
            for j in range(32):
                e = self.goodEvent.iloc[i,j]
                if (j % 2) == 0:
                    if e == 0:
                        bs += "▽"
                    else:
                        bs += "▼"
                        # if e < 400:
                        #     bs += "▼"
                        # elif e < 460:
                        #     bs += "\033[32m▼\033[0m"
                        # elif e < 550:
                        #     bs += "\033[33m▼\033[0m"
                        # else:
                        #     bs += " \033[31m▼\033[0m"
                else:
                    if e == 0:
                        bs += "△"
                    else:
                        bs += "▲"
                        # if e < 400:
                        #     bs += "▲"
                        # elif e < 460:
                        #     bs += "\033[32m▲\033[0m"
                        # elif e < 550:
                        #     bs += "\033[33m▲\033[0m"
                        # else:
                        #     bs += "\031[31m▲\033[0m"
            if (i % 2) == 0:
                bs += "\t"
            else:
                bs += "\n"

        clearTerminal()
        print(bs)

        tem = translateTemperature(self.goodEvent.iloc[:,36].values)

        table = AsciiTable([header,tem.tolist()],title="Temperature")

        print(table.table)


