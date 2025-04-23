from devSlaver.slaver import slaver
from prompt_toolkit import prompt,PromptSession
from prompt_toolkit.completion import *
from prompt_toolkit.shortcuts import radiolist_dialog
from terminaltables import AsciiTable
from devSlaver import clearTerminal
import os
from threading import Event
import time
import keyboard
from devSlaver import tuiPlot
import functools
import configparser


#导入/初始化配置文件，文件位置为./config.ini。文件缺失会新建一个默认配置文件
print("Load configure parameter.....")
def getConfig():
    config =  configparser.ConfigParser()
    if(os.path.exists("./config.ini")):
        config.read("./config.ini")
    else:
        config["Path"] = {
            "configureFileDirectory" : "./configureFile",
            "H5Directory" : "./data",
            "configureFilePath" : ""
        }
        config["SlaveStatus"] = {
            "connectServer" : "No",
            "projectName" : "logging",
            "deviceName" : "Device00",
            "serverHost" : "192.168.1.108",
            "serverPort" : "999",
            "serverTimeout" : "55",
            "dataBackup" : "Yes"
        }
        config["DataLayer"] = {
            "detectorType" : "0",
            "measureMode" : "1"
        }
    return  config
config = getConfig()

#初始化
print("Init LUMIS@slaver....")
MySlaver = slaver(
    projectName=config.get("SlaveStatus","projectName"),
    deviceName=config.get("SlaveStatus", "deviceName"),
    detectorType=config.getint("DataLayer","detectorType"),
    serverHost=config.get("SlaveStatus","serverHost"),
    serverPort=config.getint("SlaveStatus","serverPort"),
    serverTimeout=config.getint("SlaveStatus","serverTimeout"),
    configureFilePath=config.get("Path","configureFilePath"),
    enableBackup=config.getboolean("SlaveStatus", "dataBackup")

) #与硬件系统连接/测量, 与服务器连接
terminalCycleTag = Event() # 命令行应用的循环标值类
terminalMainTag = Event() # 退出命令行应用

#中断APP函数
def stopTremApp():
    if terminalCycleTag.is_set():
        terminalCycleTag.clear()
        input("press Enter to main TUI.")
        clearTerminal()

#热键绑定
keyboard.add_hotkey('ctrl+q',stopTremApp)

# 地址路径补全器
configureCompleter = PathCompleter()
dirCompleter = PathCompleter(file_filter=os.path.isdir)

#检查是否能够使用QT来显示
try:
    from devSlaver.graphy import *
    import sys
    print("The Qt module was successfully loaded.")
    app = QApplication(sys.argv)
    # 显示触发情况——基于QT
    def showTriggerStatus_qt():
        win = subPlotWin_singal(MySlaver)
        win.show()
        app.exec_()
    # 显示当前能谱——基于QT
    def showEnergySpectrum_qt():
        win = subPlotWin_singal(MySlaver)
        win.show()
        app.exec_()
except ImportError:
    print("Can't load Qt module.")
    app = None
    # 显示触发情况——基于QT
    def showTriggerStatus_qt():
        print("failed, there is no qt model.")
    # 显示当前能谱——基于QT
    def showEnergySpectrum_qt():
        print("failed, there is no qt model.")

#===================================操作指令函数======================
#设置配置文件——基于命令行的对话框
def getConfigureFile_dialog():
    configList = []
    fileDir = config.get("Path","configureFileDirectory")
    for root, dirs, files in os.walk(fileDir):
        for name in files:
            configList.append(name)
    result = radiolist_dialog(
        title="RadioList dialog",
        text="Which breakfast would you like ?",
        values=[
            (i, configList[i]) for i in range(len(configList))
        ]
    ).run()
    if result is not None:
        MySlaver.setConfigurePath(os.path.join(fileDir,configList[result]))
        config.set("Path","configureFilePath", os.path.join(fileDir,configList[result]))

#设置配置文件--基于命令行文字输入
def getConfigureFile_input():
    text = prompt("configure file path:",completer=configureCompleter)
    if os.path.exists(text):
        MySlaver.setConfigurePath(text)
        config.set("Path", "configureFilePath", text)
    else:
        print("The input path is invalid.")

#持续显示测量状态
def showMeasureStatus():
    if MySlaver.measureStatus.is_set():
        global terminalCycleTag
        terminalCycleTag.set()
        while terminalCycleTag.is_set():
            clearTerminal()
            #标签
            header = ["\033[36m empty package\033[0m",
                      "\033[36m interrupt count\033[0m",
                      "\033[36m unknown package\033[0m",
                      "\033[33m total bad package\033[0m",
                      "\033[36m received package\033[0m",
                      "\033[36m valid event\033[0m",
                      "\033[35m measure time\033[0m"
                      ]
            #值
            values = []
            badPackValues = MySlaver.decodeTool.badPackage()
            sum = 0
            for i in badPackValues:
                values.append(str(i))
                sum += i
            values.append("\033[33m" + str(sum) + "\033[0m") # 添加到第四个，total bad package
            count = MySlaver.decodeTool.eventCount()
            for i in count:
                values.append(str(i)) #第六个，valid event
            useTime = time.time() - MySlaver.h5.timeInfo[0]
            sec = int(useTime % 60)
            min = int(useTime % (60 * 60) / 60)
            hour = int(useTime / (60 * 60))
            timeStr = "\033[35m{:}:{:0>2d}:{:0>2d}\033[0m".format(hour,min,sec)
            values.append(timeStr)  #最后一个，measure time
            badPackTable = AsciiTable([header,values], "bad pack")
            print(badPackTable.table)
            time.sleep(1)
    else:
        print("\033[31mNot yet measured,no information to show!\033[0m")

#打印slaver状态
def printSlaverStatus():
    # ============computer status=============
    # device name and project name
    print("\033[34m device name: \033[35m{}\033[0m".format(MySlaver.name), end="\t")
    print("\033[34m project: \033[35m{}\033[0m".format(MySlaver.project))

    # ============link parameter===============
    # server link
    print("\033[34m server link: {}\033[0m".format(
        ("\033[32m" if MySlaver.linkStatus.is_set() else "\033[31m") + str(MySlaver.linkStatus.is_set())), end="\t")

    # server address
    print("\033[34m server address: \033[0m{}:{}".format(MySlaver.serverHost, MySlaver.serverPort), end="\t")

    # auto connect server
    print("\033[34m auto connect: {}\033[0m".format(
        ("\033[32m" if MySlaver.finalConnect.is_set() else "\033[31m") + str(MySlaver.finalConnect.is_set())))

    # link status
    if MySlaver.linkStatus.is_set():
        # final link time + link status
        print("\033[34m final link time:\033[0m {}; \033[34mlast connect:{}\033[0m".format(
            MySlaver.finalConnectTime,
            ("\033[32m" if config.getboolean("SlaveStatus","connectServer") else "\033[31m") + str(config.getboolean("SlaveStatus","connectServer"))))

    # =========measure parameter=========
    # measure status
    print("\033[34m measuring: {}\033[0m".format(
        ("\033[32m" if MySlaver.measureStatus.is_set() else "\033[31m") + str(MySlaver.measureStatus.is_set())),
        end="\t")

    # measure mode
    checkModeList = ["\033[32m routine data", "\033[33m baseline data", "\033[36m all data"]
    print("\033[34m measure mode:{}\033[0m".format(checkModeList[MySlaver.decodeTool.getCheckMode() - 1]), end="\t")

    # detector type
    detectorTypeList = ["plate", "well log"]
    print("\033[34m detector type:\033[35m {} \033[0m".format(detectorTypeList[MySlaver.detectorType]), end="\t")

    # data backup
    print("\033[34m data backup: {}\033[0m".format(
        "\033[32m enable" if MySlaver.enableDataBackup else "\033[31m disable"))

    # ===========path============
    # configure file path
    print("\033[34m configure file: \033[0m{}".format(MySlaver.configurePath))

    # data file
    print("\033[34m data file: \033[0m{}".format(MySlaver.h5Path if MySlaver.h5Path is not None else "default path"))

#显示当前能谱
def showEnergySpectrum_terminal():
    p = tuiPlot.plotESInTerminal(MySlaver)
    p.show()

#显示触发情况和温度
def showTriggerStatus():
    p = tuiPlot.plotTriggerStatus(MySlaver, terminalCycleTag)

#设置h5文件路径
def setH5Path():
    text = prompt("data file path:", completer=dirCompleter)
    if os.path.exists(text):
        print("The file already exists in the destination path.")
    else:
        name,ex = os.path.splitext(text)
        if ex != ".h5":
            MySlaver.setH5FilePath(name+".h5")
        else:
            MySlaver.setH5FilePath(text)

#设置采集模式的偏函数
def setMeasureMode(mode:int):
    def tmpFunc():
        MySlaver.setCheckMode(mode)
        config.set("DataLayer","measureMode",str(mode))
    return tmpFunc

#设置探测器类型
def setDetectorType(detectorType:int):
    def myFunc():
        MySlaver.setDetectorType(detectorType)
        config.set("DataLayer", "detectortype", str(detectorType))
    return myFunc

#设置是否备份数据
def setEnableDataBackup(enable:bool):
    def func():
        pastSatus = MySlaver.enableDataBackup
        MySlaver.setEnableDataBackup(enable)
        config.set("SlaveStatus","dataBackup","Yes" if enable else "No")
    return func

#退出tui
def quitTUI():
    terminalMainTag.clear()



# 指令映射
orderDic = {"measure":{
                "start": MySlaver.startMeasure,                     #开始测量
                "stop": MySlaver.stopMeasure,                       #结束测量
                "status":showMeasureStatus                          #termapp:持续打印测量状态，包括是否在测量、接收事件情况、测量时间
                       },
            "connectServer": {                                      #连接服务器，此时服务器将接管测量操作
                "start":MySlaver.startLinkServer,
                "stop":MySlaver.stopLinkServer
            },
            "status":printSlaverStatus,                             #打印当前slaver状态，包括是否连接上服务器，是否在测量，配置文件路径，当前h5文件路径(下一次采集的h5路径)
            "show":{                                                #显示当前某道能谱
                "energySpectrum":{
                    "-t":showEnergySpectrum_terminal,
                    "-qt":showEnergySpectrum_qt
                    },
                "triggerEvent":{                                    #显示触发情况
                    "-t":showTriggerStatus,
                    "-qt":showTriggerStatus_qt
                    },
                },
            "set":{
                "configuration": {                                  #设置配置文件
                    "-t":getConfigureFile_input,                    #--terminal
                    "-d":getConfigureFile_dialog,                   #--dialog
                    "default":getConfigureFile_dialog
                    },
                "dataPath": setH5Path,                               #设置h5路径
                "measureMode":{                                     #设置采集模式，routine-只保留hit数据;baseline-只保留未hit数据;all-保留所有数据
                    "routine":setMeasureMode(1),
                    "baseline":setMeasureMode(2),
                    "all":setMeasureMode(3),
                },
                "detectorType":{                                    #设置对应的设备类型， plate：平板型；wellLog：井眼型
                    "plate":setDetectorType(0),
                    "wellLog":setDetectorType(1),
                },
                "dataBackup":{                                      #设置是否备份数据
                    "enable":setEnableDataBackup(True),
                    "disable":setEnableDataBackup(False)
                }
                },
            "close":quitTUI,                                           #关闭退出程序
            "exit":quitTUI,
            "quit":quitTUI
            }

#=============================辅助函数========================
#将字典内的函数转换为None
def removeCall(order:dict):
    d = {}
    for key in order.keys():
        item = order[key]
        if not isinstance(item,dict):
            d[key] = None
        else:
            d[key] = removeCall(item)
    return d
#命令指令转换为补全器
def getCompleter(order:dict):
    its = removeCall(order)
    return NestedCompleter.from_nested_dict(its)
#从输入字符串转换为响应函数
def orderToFunctun(text:str):
    orderList = text.split()
    q = orderDic
    for i in orderList:
        q = q.get(i.strip(),None)
    if isinstance(q, dict):
        return None
    return q

completer = getCompleter(orderDic)




if __name__ == '__main__':
    session = PromptSession()
    terminalMainTag.set()

    #根据配置选择是否自动测试连接服务器
    if(config.getboolean("SlaveStatus","connectServer")):
        #测试是否能链接服务器
        print("check connect to the server:")
        MySlaver.startLinkServer()
        for i in range(int(MySlaver.connectSock.gettimeout())):
            print("\r wait for connect: {}s/{}s".format(i,MySlaver.connectSock.gettimeout()),end='')
            if MySlaver.finalConnect.is_set():
                break
            time.sleep(1)
        print("")
        if MySlaver.finalConnect.is_set():
            print("successfully connect to the server, link model will be maintained.")
        else:
            print("failed to connect with the server, stopping link model.")
            MySlaver.stopLinkServer()
    else:
        print("default set: not connect server auto")

    #配置采集模式与对应的设备
    tmpInt = config.getint("DataLayer","measureMode")
    if tmpInt in [1,2,3]:
        MySlaver.setCheckMode(tmpInt)
    tmpInt = config.getint("DataLayer","detectorType")
    if tmpInt in [0,1]:
        MySlaver.setDetectorType(tmpInt)

    #接收命令行指令的循环
    while terminalMainTag.is_set():
        text = session.prompt('{}@{}#'.format(MySlaver.name,MySlaver.project),completer=completer)
        func = orderToFunctun(text)
        if func is None:
            print("Invalid order-{}".format(text))
        else:
            try:
                func()
            except Exception as e:
                print("failed to run this oder:{}".format(text))
                print("error:{}".format(e.__str__()))
                import traceback
                traceback.print_exc()

    #软件关闭
    if MySlaver.measureStatus.is_set():
        MySlaver.stopMeasure()
    MySlaver.close()
    with open('./config.ini', 'w') as configfile:
        config.write(configfile)
    print("LUMIS successfully close.")
    sys.exit(0)


