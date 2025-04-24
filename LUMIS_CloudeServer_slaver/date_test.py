from dataLayer import *
import socket
import asyncio
import threading
import json
from dataLayer.connectionTools import *
from threading import Event
import devSlaver
import time
from multiprocessing import Queue, Event, SimpleQueue
from prompt_toolkit import prompt,PromptSession
from prompt_toolkit.completion import *
from prompt_toolkit.shortcuts import radiolist_dialog
from terminaltables import AsciiTable

class test:
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

        #设备状态
        self.measureStatus = Event()
        self.decodeTool = Lumis_Decode()

        #数据存储和配置文件
        self.h5Path = None
        self.h5 = h5Data("./data/tmpData50.h5", "r")
        #线程
        self.dataReceiveThread = None
        self.dataDecodeThread = None

    #数据读取线程
    def loadDataFromSocket1(self, tag: Event, decodeTool: Lumis_Decode):
        '''
        协程函数：从socket中获取原始数据
        :param _s: 获取数据的socket
        :param tag: 消息队列
        :param _e: 运行状态标志
        :param decodeTool: 解码工具
        :return:
        '''
        buff = b''
        with open("./binaryFile","bw") as file:
            while tag.is_set():
                tmpB = b'\xfa\x5a\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\xfe\xee\xfe\xee\xaa\xaa\xaa\xaa'
                file.write(tmpB)
                buff += tmpB
                time.sleep(10)
                buff = decodeTool.loadBinaryData(buff)

    #数据解码线程
    def dataDecode1(self,tag: Event, h5: h5Data, decodeTool: Lumis_Decode):
        '''
        a thread function to decode binary data.
        负责解码数据，将数据写入h5文件，开始时将写入设备配置状态。
        :param h5File: a h5Data object to output data to h5 file
        :param decodeTool: to decode binary data
        :return:
        '''
        h5.startTime()
        t = time.time()
        while tag.is_set():
            time.sleep(5)
            
        # 开始解码数据
        # try:
        #     _tmp = decodeTool.decodingOneEventData()
        #     if len(_tmp) == 2:
        #         event, timeTag = _tmp
        #     else:
        #         event, timeTag, posture = _tmp
        #     # 对于第一组数据，除将数据导入h5文件中，还会将状态信息导入h5文件
        #     # 因此避免了第一次判断triggerID为零时判断为置零
        #     if event.shape[0] != 0:
        #         eventID = event[0][-2]
        #         if h5.getDetectorType() == 1:
        #             h5.addToDataSet(event, timeTag, postureInfo=posture, postureIndex=np.array([eventID]))
        #         else:
        #             h5.addToDataSet(event, timeTag)
        #         h5.addToDataSet(event,timeTag)
        #     else:
        #         eventID = 0
        #     h5.putDeviceStatus(decodeTool.devStatus())
        #     print("zaizai")
        #     while tag.is_set():
        #         if decodeTool.getDetectorType() == 1:
        #             event, timeTag, posture = decodeTool.decodingOneEventData()
        #         else:
        #             event,timeTag = decodeTool.decodingOneEventData()
        #         # 将数据导入h5文件中（需要检查当前事件是否全为空包）
        #         if event.shape[0] != 0:
        #             if event[0][-2] <= eventID:
        #                 index = h5.newSets()
        #                 if decodeTool.getDataBackup():
        #                     #开启新线程来将上一个sheet的数据
        #                     p = Process(target=dataBackupProcess,args=(h5.file.filename,index-1))
        #                     p.start()
        #             eventID = event[0][-2]
        #             if h5.getDetectorType() == 1:
        #                 h5.addToDataSet(event, timeTag, postureInfo = posture, postureIndex = np.array([eventID]))
        #             else:
        #                 h5.addToDataSet(event, timeTag)
        #         if time.time() - t > 5:
        #             h5.flush()
        #             t = time.time()
        # except asyncio.CancelledError:
        #     pass
        # except Exception as e:
        #     print('dataDecode:',e.__str__())
        #     import traceback
        #     traceback.print_exc()
        # finally:
        #     h5.stopTime()
        #     h5.close()
        # print('dataDecode:','end')

    #=============与下位机LUMIS@core交互==========
    #开始测量
    def startMeasure(self):
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
        self.h5 = h5Data(self._h5Path, "w",detectorType=0)

        s = socket.socket()

        #开始测量-两个线程
        self.dataReceiveThread = threading.Thread(target=self.loadDataFromSocket1,args=(self.measureStatus,self.decodeTool))
        self.dataDecodeThread = threading.Thread(target=self.dataDecode1,args=(self.measureStatus,self.h5,self.decodeTool))
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
        self.h5 = h5Data(self._h5Path, "w", detectorType=0)
        # 重启线程
        self.measureStatus.set()
        self.dataReceiveThread = threading.Thread(target=self.loadDataFromSocket1, args=(self.measureStatus, self.decodeTool))
        self.dataDecodeThread = threading.Thread(target=self.dataDecode1, args=(self.measureStatus,self.h5, self.decodeTool))
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



if __name__ == '__main__':
    print("开始测量")
    measure = test()
    measure.startMeasure()


