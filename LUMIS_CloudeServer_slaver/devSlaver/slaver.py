from dataLayer import *
import socket
import asyncio
import threading
import json
from dataLayer.connectionTools import *
from threading import Event
import devSlaver
import time
_devIP = '192.168.10.16'
_TCPport = 24

class slaver():
    def __init__(self,**kwargs):
        """
        param:
            projectName:str  项目名称
            deviceName:str
            detectorType:int 探测器种类：0.平板型设备；1.井眼型设备(具有额外的寻北仪数据与陀螺仪数据)
            serverHost:str
            serverPort:int
            serverTimeout:int
            configureFilePath:str

        """
        #设备信息
        self.project = kwargs.get("projectName",devSlaver.projectName)
        self.name = kwargs.get("deviceName",devSlaver.deviceName)
        self.serialNumber = devSlaver.serialNumber

        #设备状态
        self.measureStatus = Event()
        self.linkStatus = Event()
        self.finalConnectTime = None
        self.finalConnect = Event()
        self.runTag = Event()
        self.runTag.set()
        self.decodeTool = Lumis_Decode()

        # 解码模式
        if("detectorType" in kwargs.keys()):
            self.decodeTool.setDetectorType(kwargs.get("detectorType"))
        if("checkMode" in kwargs.keys()):
            self.decodeTool.setCheckMode(kwargs.get("checkMode"))
        if("enableBackup" in kwargs.keys()):
            self.decodeTool.enableDataBackup(kwargs.get("enableBackup"))


        #与服务器的TCP连接
        self.serverHost = kwargs.get("serverHost", devSlaver.Host)
        self.serverPort = kwargs.get("serverPort", devSlaver.Port)
        self.connectSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connectSock.settimeout(kwargs.get("serverTimeout",55))
        self.serverTimeout = kwargs.get("serverTimeout",55)


        #数据存储和配置文件
        self.configurePath = kwargs.get("configureFilePath","./configureFile/Configuration#4567_4layer_coincidence_calibrated.dat")
        self.h5Path = None
        self.h5 = h5Data("./data/tmpData50.h5", "r")


        #用于设置
        self.infoQueue = Queue()

        #线程
        self.dataReceiveThread = None
        self.dataDecodeThread = None
        self.serverConnectThread = None

#==============解码模式============
    @property
    def checkMode(self):
        return self.decodeTool.getCheckMode()

    @property
    def detectorType(self):
        return self.decodeTool.getDetectorType()

    @property
    def enableDataBackup(self):
        return self.decodeTool.getDataBackup()

    def setCheckMode(self,values:int):
        self.decodeTool.setCheckMode(values)

    def setDetectorType(self,values:int):
        self.decodeTool.setDetectorType(values)

    def setEnableDataBackup(self,enable:bool):
        self.decodeTool.enableDataBackup(enable)



#=============与下位机LUMIS@core交互==========
    #开始测量
    def startMeasure(self):
        #对于井眼型设备需要发送“主板给从板上电”指令
        if self.detectorType == 1:
            print("sending order to LUMIS@core:\033[32m power on the slave board \033[0m")
            reply,message = linkGBT.sendCommand(devSlaver.turnOnPower)
            if not reply:
                print(message)
                return 0, message
            print("")

        #发送时钟同步指令
        print("sending order to LUMIS@core:\033[32m clock synchronization\033[0m")
        reply, message = linkGBT.sendCommand(devSlaver.clockSynch)
        if not reply:
            print(message)
            return 0, message
        print("")

        # 发送时钟同步指令后需等待一段事件才能发送复位指令
        waitingTime = 15
        for i in range(waitingTime):
            print("\rwaiting for clock synchronization:[\033[32m{}\033[33m{}\033[0m] {}s/{}s".format(
                "#"*i,"="*(waitingTime-i),i,waitingTime)
                  ,end="")
            time.sleep(1)
        print("")

        # 发送复位指令
        print("sending order to LUMIS@core:\033[32m reset elink\033[0m")
        reply, message = linkGBT.sendCommand(devSlaver.reset)
        if not reply:
            print(message)
            return 1, message
        time.sleep(0.1)

        # 发送复位spiroc指令
        print("sending order to LUMIS@core:\033[32m reset spiroc\033[0m")
        reply, message = linkGBT.sendConfigFile("./dependence/reset_spiroc.dat")
        if not reply:
            print(message)
            return 2, message

        # 发送复位spiroc指令后需等待一段事件才能发送配置指令
        for i in range(waitingTime):
            print("\rwait for reset spiroc:[\033[32m{}\033[33m{}\033[0m] {}s/{}s".format(
                "#"*i,"="*(waitingTime-i),i,waitingTime)
                , end="")
            time.sleep(1)
        print("")

        #发送配置指令
        print("sending configuration to LUMIS@core:\033[32m {}\033[0m".format(self.configurePath))
        reply, message = linkGBT.sendConfigFile(self.configurePath)
        if not reply:
            print(message)
            return 3, message

        # 新建h5文件
        self.measureStatus.set()
        self.h5.close()
        if self.h5Path is None:
            fileName = "tmpData{}.h5"
            if not os.path.exists("./data"):
                os.mkdir("./data")
                name = fileName.format("")
            else:
                i = 0
                name = fileName.format("")
                while os.path.exists(os.path.join("./data", name)):
                    i += 1
                    name = fileName.format(i)
            self._h5Path = os.path.join("./data", name)
        else:
            self._h5Path = self.h5Path
        print("h5文件名:", self._h5Path)
        self.h5 = h5Data(self._h5Path, "w",detectorType=self.detectorType)

        # 与LUMIS@core建立TCP连接
        s = socket.socket()
        try:
            s.connect((_devIP, _TCPport))
        except Exception as e:
            print("dataReceive error:", e.__str__())
            return 4, e.__str__()

        #开始测量-两个线程
        self.dataReceiveThread = threading.Thread(target=loadDataFromSocket,args=(s,self.measureStatus,self.decodeTool))
        self.dataDecodeThread = threading.Thread(target=dataDecode,args=(self.h5,self.decodeTool))
        self.dataReceiveThread.start()
        self.dataDecodeThread.start()

        # 启动时间监控线程
        self.time_monitor_thread = threading.Thread(target=self.monitor_time, args=(s,))
        self.time_monitor_thread.start()

    # 检测如果超过午夜24点，重启线程 dataReceiveThread 与 dataDecodeThread
    def monitor_time(self, s):
        import datetime
        now = datetime.datetime.now()
        #midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        midnight = now.replace(hour=7, minute=40, second=0, microsecond=0)
        if now > midnight:
            midnight += datetime.timedelta(days=1)
        print("midnight:", midnight)
        delta = (midnight - now).total_seconds()
        print("剩余时间:", delta)
        time.sleep(delta)
        print("时间到准备停止当前线程")
        # 停止当前线程
        self.measureStatus.clear()
        self.dataReceiveThread.join()
        print("step1")
        self.dataDecodeThread.join()
        print("step2")
        print("停止当前线程")
        # 关闭当前h5文件
        self.h5.close()


        # 生成新的文件名
        fileName = "tmpData{}.h5"
        i = 0
        name = fileName.format("")
        while os.path.exists(os.path.join("./data", name)):
            i += 1
            name = fileName.format(i)
        self._h5Path = os.path.join("./data", name)
        print("新的文件名：", self._h5Path)
        self.h5 = h5Data(self._h5Path, "w", detectorType=self.detectorType)

        # 重启线程
        self.measureStatus.set()
        self.dataReceiveThread = threading.Thread(target=loadDataFromSocket, args=(s, self.measureStatus, self.decodeTool))
        self.dataDecodeThread = threading.Thread(target=dataDecode, args=(self.h5, self.decodeTool))
        self.dataReceiveThread.start()
        self.dataDecodeThread.start()
        print("线程重启")
        # 继续监控时间
        self.monitor_time(s)

    #结束测量
    def stopMeasure(self):
        self.measureStatus.clear()
        if self.dataReceiveThread is not None:
            print("waiting for data receive thread stop.")
            self.dataReceiveThread.join()
            self.dataDecodeThread.join()
            self.time_monitor_thread.join()
            print("data receive thread has stopped!")
        else:
            print("data receive thread didn't run.")

    #设置配置文件路径
    def setConfigurePath(self,path: str):
        with open(path, "rb") as file:
            pass
        self.configurePath = path

    #设置h5文件路径
    def setH5FilePath(self,path: str):
        self.h5Path = path

#=============作为终端IoT使用================
    # 辅助函数：连接服务器
    def linkServer(self):
        # 与服务器的TCP连接
        self.connectSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connectSock.settimeout(self.serverTimeout)
        self.connectSock.connect((self.serverHost, self.serverPort))
        self.linkStatus.set()
        info = {"devType": 0,
                "devInfo": {
                "name": self.name,
                "project": self.project,
                "serialNumber": self.serialNumber,}}
        msg = json.dumps(info)
        self.connectSock.sendall(bytes(msg + "\n", "utf-8"))
        reMsg = self.getMsgFromServer()
        if not reMsg.get("return", False):
            self.connectSock.close()
            return False
        else:
            return True

    # 辅助函数：一次连接任务
    def oneConnectForServer(self):
        while self.linkStatus.is_set():
            reMsg = self.getMsgFromServer()
            self.finalConnectTime = time.strftime("%Y-%m-%d, %H:%M:%S", time.localtime())
            k = reMsg.keys()
            if "heartBeat" in k:
                info = {"status_measure": self.measureStatus.is_set()}
                if self.measureStatus.is_set():
                    info["dataTag"] = os.path.split(self._h5Path)[-1].split(".")[0]
                msg = json.dumps(info)
                self.connectSock.sendall(bytes(msg + "\n", "utf-8"))
            if "askForInfo" in k:
                devInfo = self.h5.getDeviceStatus()
                while len(devInfo) == 0:
                    devInfo = self.h5.getDeviceStatus()
                info = {"start_time": float(self.h5.timeInfo[0]), "device_status": devInfo}
                msg = json.dumps(info)
                self.connectSock.sendall(bytes(msg + "\n", "utf-8"))
            if "askForData" in k:
                line = reMsg["askForData"]
                Ndata = self.h5.getData(-2, line)
                if Ndata.shape[0] > 10000:
                    Ldata = Ndata.iloc[:10000].values.astype(int).tolist()
                    info = {"data": Ldata,"remained":True}
                else:
                    Ldata = Ndata.values.astype(int).tolist()
                    info = {"data": Ldata}
                msg = json.dumps(info)
                self.connectSock.sendall(bytes(msg + "\n", "utf-8"))
                del Ndata,Ldata,info
            if "switch" in k:
                switch = reMsg["switch"]
                if switch != self.measureStatus.is_set():
                    if switch:
                        self.startMeasure()
                    else:
                        self.stopMeasure()
                info = {"switch": True}
                msg = json.dumps(info)
                self.connectSock.sendall(bytes(msg + "\n", "utf-8"))
            if "connectHalt" in k:
                break

    # 线程函数：接收服务端
    def threadForServer(self):
        while self.linkStatus.is_set():
            try:
                if self.linkServer():
                    self.finalConnectTime = time.strftime("%Y-%m-%d, %H:%M:%S",time.localtime())
                    self.finalConnect.set()
                    self.oneConnectForServer()
                else:
                    self.finalConnect.clear()
                self.connectSock.close()
            except Exception as e:
                import traceback
                print("server link error:",e.__str__())
                traceback.print_exc()
                self.finalConnect.clear()
            finally:
                time.sleep(5)

    # 开始连接服务器
    def startLinkServer(self):
        self.linkStatus.set()
        self.serverConnectThread = threading.Thread(target=self.threadForServer)
        self.serverConnectThread.start()

    # 结束服务器连接
    def stopLinkServer(self):
        if self.linkStatus.is_set():
            self.linkStatus.clear()
            self.serverConnectThread.join()

    #辅助函数：接收从server发来的字符串
    def getMsgFromServer(self) -> dict:
        if self.infoQueue.empty():
            msgList = []
            msg = str(self.connectSock.recv(1024), "utf-8")
            msgList.append(msg)
            while len(msg) == 0 or msg[-1] != "\n":
                msg = str(self.connectSock.recv(1024), "utf-8")
                msgList.append(msg)
                if not self.linkStatus.is_set():
                    break
            smsg = "".join(msgList).strip()
            smsg = smsg.split("\n")
            if len(smsg) > 1:
                for i in range(1,len(smsg)):
                    self.infoQueue.put(json.loads(smsg[i]))
            return json.loads(smsg[0])
        else:
            return self.infoQueue.get()

    def close(self):
        if self.linkStatus.is_set():
            self.stopLinkServer()
        self.h5.close()

if __name__ == '__main__':
    sl = slaver()
    while True:
        t = input("#:")
        if t.strip() == "start":
            sl.startMeasure()
            print("starting")
        elif t.strip() == "stop":
            sl.stopMeasure()
            break
        elif t.strip() == "status":
            badPack = sl.decodeTool.badPackage()
            count = sl.decodeTool.eventCount()
            info = "-----BAD PACKAGE-----\n" \
                   "empty package:{}\n" \
                   "interrupt count:{}\n" \
                   "unknown package:{}\n" \
                   "total bad package:{}\n" \
                   "-----EVENT COUNT-----\n" \
                   "received package:{}\n" \
                   "valid event:{}\n" \
                   "---------------------".format(
                *badPack,
                badPack[0] + badPack[1] + badPack[2],
                *count
            )
            print(info)
        else:
            print("eorro input",t)

