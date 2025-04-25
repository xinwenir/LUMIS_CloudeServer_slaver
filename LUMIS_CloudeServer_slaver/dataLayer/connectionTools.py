'''
包含与设备通讯的类
'''
import os
import math
import time
import socket
import asyncio
from multiprocessing import Process
import numpy as np
from datetime import datetime
from multiprocessing import Queue, Event, SimpleQueue
from dataLayer.baseCore import h5Data
from dataLayer import sizeUnit_binary
# ----------仪器通讯地址
_devIP = '192.168.10.16'
_TCPport = 24
_UDPport = 4660
# ----------辅助解包------------
# ----------SiPM数据-------------
_gain = int.from_bytes(b'\x20\x00',byteorder='big',signed=True) # 8192
_hit = int.from_bytes(b'\x10\x00',byteorder='big',signed=True) # 4096
_value = int.from_bytes(b'\x0f\xff',byteorder='big',signed=True) # 4095
# -----------陀螺仪与寻北仪----------
class PostureDecode():
    #陀螺仪温度
    @staticmethod
    def gyroTemperature(b: bytes) -> float:
        '''

        :param b:length = 2
        :return: temperature (°C)
        '''
        return int.from_bytes(b, byteorder="big", signed=True) / 340. + 36.53
    #陀螺仪加速度
    @staticmethod
    def gyroAccelerated(b: bytes) -> float:
        '''

        :param b:length = 2
        :return: accelerated (g)
        '''
        return int.from_bytes(b, byteorder="big", signed=True) / 16284.
    #陀螺仪角速度
    @staticmethod
    def gyroAngularVelocity(b: bytes) -> float:
        '''

        :param b:length = 2
        :return: Angular velocity (°/s)
        '''
        return int.from_bytes(b, byteorder="big", signed=True) / 131.
    #寻北仪横倾角
    @staticmethod
    def seekerRoll(b: bytes) -> float:
        '''

        :param b:length = 2
        :return: seeker Roll (°）
        '''
        return int.from_bytes(b, byteorder="little", signed=True) * 0.01
    #寻北仪纵倾角
    @staticmethod
    def seekerPitch(b: bytes) -> float:
        '''

        :param b:length = 2
        :return: seeker Pitch (°)
        '''
        return int.from_bytes(b, byteorder="little", signed=True) * 0.01
    #寻北仪方位角
    @staticmethod
    def seekerAzimuth(b: bytes) -> float:
        '''

        :param b: length = 2
        :return: seeker Azimuth (°)
        '''
        return int.from_bytes(b, byteorder="little", signed=False) * 0.01
    #寻北仪校验和
    @staticmethod
    def seekerCheckSum(bs: bytes, sum: int) -> bool:
        '''

        :param bs:
        :param sum: length = 1
        :return:
        '''
        mask = int.from_bytes(b'\xff', byteorder="big", signed=False)
        i = 0
        for b in bs:
            i += b
            i = i & mask
        i = i & mask
        return i == sum

    #解码大井眼姿态信息
    @staticmethod
    def Decode(source:bytes):
        '''
        ======THE FORMAT OF SOURCE=====
        ------POSTURE PART-------------
        NAME        ROW     SIZE    LOCAL
        gyroT       1ROW    2byte    / 0-1
        gyroA       3ROW    6byte    / 2-7
        gyroAV      3ROW    6byte    / 8-13
        seekerHead  1ROW    2byte    / 14-15
        status      1ROW  1byte    / 16
        Roll        1ROW    2byte    / 17-18
        Pitch       1ROW    2byte    / 19-20
        Azimuth     1ROW    2byte    / 21-22
        checkSum    1ROW  1byte    /23
        TOTAL LENGTH: 24 byte
        :return np.array shape = (11,)
        --------result -----------
        index   name
        0       check
        1       gyroTemperature
        2       gyroXAccelerated
        3       gyroYAccelerated
        4       gyroZAccelerated
        5       gyroXAngularVelocity
        6       gyroYAngularVelocity
        7       gyroZAngularVelocity
        8       SeekerStatus
        9       SeekerRoll
        10      SeekerPitch
        11      SeekerAzimuth
        '''
        result = np.zeros((12,),dtype="float32")
        #陀螺仪数据
        result[1] = PostureDecode.gyroTemperature(source[0:2])
        for i in range(3):
            result[i + 2] = PostureDecode.gyroAccelerated(source[2 + i * 2:4 + i * 2])
            result[i + 5] = PostureDecode.gyroAngularVelocity(source[8 + i * 2:10 + i * 2])
        #寻北仪数据
        if(PostureDecode.seekerCheckSum(source[16:23], source[23])):
            result[0] = 1
            result[8] = source[16]
            result[9] = PostureDecode.seekerRoll(source[17:19])
            result[10] = PostureDecode.seekerPitch(source[19:21])
            result[11] = PostureDecode.seekerAzimuth(source[21:23])
        else:
            result[0] = -1
        return result

#=================================================================
# 集合连接通讯操作的函数
class linkGBT(object):
    # send a short binary command
    # 发送一个较短的二进制命令，一般为两个byte
    @staticmethod
    def sendCommand(command: bytes):
        global _devIP,_TCPport
        try:
            link = socket.socket()
            link.connect((_devIP,_TCPport))
            link.send(command)
            time.sleep(0.1)
            link.close()
            return True,None
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False,e.__str__()

    # send a configuration file as binary data
    # 将文件转换成二进制数据发送
    @staticmethod
    def sendConfigFile(input: str):
        global _devIP,_TCPport

        with open(input,mode="rb") as file:
            data = file.read()
        try:
            link = socket.socket()
            link.connect((_devIP,_TCPport))
            if os.path.splitext(input)[1] == '.lmbc':
                head = 0
                while True:
                    tail = data.find(b'\xee\xee',head)
                    if tail < 0:
                        break
                    link.send(data[head:tail + 2])
                    head = tail + 2
                    time.sleep(0.1)
            else:
                link.send(data)
                time.sleep(0.1)
            link.close()
            return True,None
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False,e.__str__()

# 为数据接收服务所编写的解析二进制数据类
class Lumis_Decode(object):
    def __init__(self):
        # ---- 配置量 ----
        self._readSize = 1024  # 每次读取数据的大小
        self._checkMode = 1 # 解析数据时保留的数据：1-只保留hit数据;2-只保留未hit数据;3-保留所有数据
        self._detectorType = 0 # 解析的探测器类型
        self._dataBackUp = True
        # ---- 统计量 ----
        # 坏包（扔掉的包）计数
        self._empty = 0  # 空包数
        self._interrupt = 0  # 遭受中断的包数
        self._unknow = 0  # 未知情况的包数
        # 数据计数
        self._count = 0  # 接收的正常包的总数目/当前数据的行数
        self._eventCount = 0 # 接收到的事件数
        self._temTID = 1  # 当前包的triggerID
        # ---- 缓存量 ----
        self._binaryBuff = SimpleQueue()   # 存储二进制数据流的缓存队列
        self._eventBuff = []    # 存储单个事件中各个板数据的缓冲列表
        self._statusBuff = {}   # 存储当前下位机状态的元组对象
        self._postureBuff = []  #对于井眼型设备，存储其姿态信息


    # 重新初始化统计量和缓存量
    def reInitialize(self):
        # ---- 统计量 ----
        # 坏包（扔掉的包）计数
        self._empty = 0  # 空包数
        self._interrupt = 0  # 遭受中断的包数
        self._unknow = 0  # 未知情况的包数
        # 数据计数
        self._count = 0  # 接收的正常包的总数目/当前数据的行数
        self._eventCount = 0  # 接收到的事件数
        self._temTID = 1  # 当前包的triggerID
        # ---- 缓存量 ----
        # 清空的数据缓存区数据
        self._binaryBuff = SimpleQueue()
        self._eventBuff.clear()
        self._statusBuff.clear()
        self._postureBuff.clear()

    # 设置每次读取数据最大值的大小
    def setReadSize(self, size: int, unit: sizeUnit_binary = sizeUnit_binary.B):
        self._readSize = size * unit.value

    # 设置解析数据时保留的数据
    def setCheckMode(self, hitCheck: int):
        '''
        设置解析数据时保留的数据
        :param hitCheck: 1-只保留hit数据;2-只保留未hit数据;3-保留所有数据
        :return:
        '''
        if hitCheck in (1,2,3):
            self._checkMode = hitCheck
        else:
            pass

    # 查看解析模式
    def getCheckMode(self):
        return self._checkMode

    # 设置设备类型
    def setDetectorType(self, detectorType: int):
        self._detectorType = detectorType

    # 获取对应的设备类型
    def getDetectorType(self):
        return self._detectorType

    #开启/关闭数据备份
    def enableDataBackup(self,able:bool = True):
        self._dataBackUp = able

    #获取是否备份数据信息
    def getDataBackup(self) -> bool:
        return self._dataBackUp

    #=======返回内部信息量函数===========
    def badPackage(self) -> tuple:
        '''
        返回坏包的数量
        :return: tuple(空包数,中断次数,无法识别包数)
        '''
        return self._empty, self._interrupt, self._unknow

    def eventCount(self) -> tuple:
        '''
        返回采集到的事件数
        :return: tuple(采集到的正常数据包个数, 采集到的有效事件数)
        '''
        return self._count, self._eventCount

    def totalCount(self) -> int:
        '''
        返回接受到到的总数据包个数: 采集到的正常数据包个数+空包数+中断次数
        :return: int
        '''
        return self._count + self._empty + self._interrupt

    def readSize(self) -> int:
        '''
        :return: 每次读取数据的大小
        '''
        return self._readSize

    def devStatus(self) -> dict:
        '''
        返回设备配置状态
        :return: key: boardID; value: tuple(threshold, bias voltage, trigger mode)
        '''
        return self._statusBuff

    # ===============解析二进制数据==============
    def _decodingData(self,source: bytes, hitCheck:int = 1) -> np.array:
        '''
        解析一个SSP2E数据包
        THE FOEMAT OF SOURCE:
        ---------DATA PART-------------
        NAME    ROW     SIZE    LOCAL
        HAED    1ROW    2Bytes  0-1
        HGain   36ROW   72Bytes 2-73
        LGain   36ROW   72Bytes 74-145
        BCID    1ROW    2Bytes  146-147
        ChipID  1ROW    2Bytes  148-149
        Temp    1ROW    2Bytes  150-151
        Trigger 1ROW    2Bytes  151-153
        TAIL    1ROW    4Bytes  154-157
        TOTAL SIZE: 158
        *********DECODED DATA*********
        NAME            LENGTH
        CHARGE          36
        Temp            1
        TrigID          1
        TOTAL LENGTH:   38
        ===============================
        :param source:  158Bytes-Just data part
        :param hitCheck:    1-只保留hit数据;2-只保留未hit数据;3-保留所有数据
        :return: np.array-shape=(39,1),but there are only 38 valid data points.
        @TianHeng 2021/9/4 : new data form will add time tag(show the serial number of this measurement)
            So now:np.array-shape=(40,1),but there are only 38 valid data points.
        @TianHeng 2021/9/4 : data form back to (39,1),
            but take it information in an additional array

        '''
        # check the header and the tail bytes
        if not source[0:2] == b'\xfa\x5a':
            raise ValueError("Packet header does not match.")
        elif not source[154:] == b'\xfe\xee\xfe\xee':
            raise ValueError("Packet tails do not match.")
        charge = np.empty(39, dtype='uint16')  # 存储解析后数据的位置
        # time/LowGain information
        for j in range(36):
            index = j + 37
            temp = int.from_bytes(source[index * 2:(index + 1) * 2], byteorder='big', signed=False)
            if hitCheck == 1:
                charge[35 - j] = (temp & _value) if bool(temp & _hit) else 0
            elif hitCheck == 2:
                charge[35 - j] = (temp & _value) if not bool(temp & _hit) else 0
            elif hitCheck == 3:
                charge[35 - j] = (temp & _value)
        # we will no longer check ChipID
        # temperature: to adapt to array type,we don't translate it.
        temperature = int.from_bytes(source[150:152], byteorder='big', signed=False)
        charge[36] = temperature
        # triggerID,the same triggerID marks the same event,triggerID will add one every times it trigger,
        # when triggerID adds up to 0xffff,the next triggerID will be 0x0000
        triggerID = int.from_bytes(source[152:154], byteorder='big', signed=False)
        charge[37] = triggerID
        return charge

    def _decodingStatus(self,source: bytes) -> list:
        '''
        解析状态信息
        THE FOEMAT OF SOURCE:
        ---------STATUS PART-----------
        TrigDAC 1ROW    2Bytes  156-157 0-1
        INDAC   1ROW    2Bytes  158-159 2-3
        TrigMode1ROW    2Bytes  160-161 4-5
        BoardID 1ROW    2Bytes  162-163 6-7
        TOTAL SIZE: 8
        *********UNPACKED DATA*********
        NAME        LENGTH
        TrigDAC     1
        INDAC       1
        TrigMode    1
        BoardID     1
        TOTAL LENGTH: 4
        ===============================
        :param source: 8Bytes.Just status part.
        :return:    list
        '''
        status = []
        TrigDAC = int.from_bytes(source[:2], byteorder='big', signed=True)
        status.append(TrigDAC)
        INDAC = int.from_bytes(source[2:4], byteorder='big', signed=True)
        status.append(INDAC)
        trigMode = int.from_bytes(source[4:6], byteorder='big', signed=True)
        status.append(trigMode)
        boardID = int(math.log(source[7], 2))
        status.append(boardID)
        return status

    #协程版本的解码数据函数，持续运行直到得到一个event/接收到-1，否则阻塞
    def decodingOneEventData(self,block:bool = True) -> tuple:
        '''
        解析一个事件的数据,当数据不足时会阻塞
        当解析到终止信息-1时会抛出异常
        ======THE FORMAT OF SOURCE=====
        ---------DATA PART-------------[0:158]
        NAME    ROW     SIZE    LOCAL
        HAED    1ROW    2Bytes  0-1
        HGain   36ROW   72Bytes 2-73
        LGain   36ROW   72Bytes 74-145
        BCID    1ROW    2Bytes  146-147
        ChipID  1ROW    2Bytes  148-149
        Temp    1ROW    2Bytes  150-151
        Trigger 1ROW    2Bytes  152-153
        TAIL    1ROW    4Bytes  154-157
        ---------STATUS PART-----------[158:166]
        TrigDAC 1ROW    2Bytes  158-159 0-1
        INDAC   1ROW    2Bytes  160-161 2-3
        TrigMode1ROW    2Bytes  162-163 4-5
        BoardID 1ROW    2Bytes  164-165 6-7
        TOTAL SIZE: 166

        if detector type == 1(which means data has posture information)
        ----------POSTURE PART-----------[166:190
        NAME        ROW     SIZE    LOCAL
        gyroT       1ROW    2byte    166-167 / 0-1
        gyroA       3ROW    6byte    168-173 / 2-7
        gyroAV      3ROW    6byte    174-179 / 8-13
        seekerHead  1ROW    2byte    180-181 / 14-15
        status      1ROW    1byte    182 / 16
        Roll        1ROW    2byte    183-184 / 17-18
        Pitch       1ROW    2byte    185-186 / 19-20
        Azimuth     1ROW    2byte    187-188 / 21-22
        checkSum    1ROW    1byte    189 / 23
        TOTAL SIZE: 166+24 = 190 byte

        ======RETURN DATA FORMAT=====
        shape   (n, 40)
        ---------AXIS 0----------
        board   0~n
        ---------AXIS 1-----------
        NAME            LENGTH
        CHARGE          36
        Temp            1
        TrigID          1
        BOARDID         1
        TimeTage        1
        TOTAL LENGTH:   40
        ---------------------------
        DATA TYPE:  np.array
        dtype:      uint16
        :return: np.array:all the valid board data in one event,shape(n,39)
                np.array: timeTag, shape(n,)
                {if detector type == 1:
                np.array: float, posture information}
        '''
        while block or (not self._binaryBuff.empty()):
            buff = self._binaryBuff.get()
            # 接收到终止信号
            if buff == -1:
                print(buff == -1)
                raise asyncio.CancelledError
            check = self._checkPackageLength(buff)
            #===========处理错误============
            # 遇到未知情况
            if check < 0:
                self._unknow += 1
                continue
            # 如果接收到的是中断
            elif check == 0:
                self._interrupt += 1
                newHead = buff.index(b'\xfa\x5a')
                buff = buff[newHead:]
                self._eventBuff.clear()
                check = self._checkPackageLength(buff)
                continue
            #======= 处理姿态信息
            if self.getDetectorType() == 1 and (check & 4):
                if(check == 5):
                    postureData = PostureDecode.Decode(buff[166:])
                else:
                    postureData = PostureDecode.Decode(buff[18:])
                self._postureBuff.append(postureData)
                check = check & 3
            #======= 接收到的是正常的包
            if check == 1:
                self._count += 1
                chargeData = self._decodingData(buff[:158],self._checkMode)
                statusData = self._decodingStatus(buff[158:])
                # 将boardID载入
                chargeData[38] = statusData[-1]
                # 将设备状态信息更新
                self._statusBuff[statusData[-1]] = tuple(statusData[:-1])
                # 如果在同一个事件中，则将数据存储在事件缓存区中,同时将triggerID改为软件计数器的计数
                if self._temTID == chargeData[37]:
                    chargeData[37] = self._eventCount
                    self._eventBuff.append(chargeData)
                # 接收到的是新的事件
                else:
                    event = np.array(self._eventBuff)
                    self._eventBuff.clear()
                    # 更新当前事件ID和软件计数
                    self._temTID = chargeData[37]
                    self._eventCount += 1
                    #将triggerID改为软件计数器的计数
                    chargeData[37] = self._eventCount
                    self._eventBuff.append(chargeData)
                    # 生成timeTag
                    timeData = np.empty(event.shape[0],dtype="uint64")
                    timeData[:] = time.time()
                    #对于井眼型的数据
                    if self.getDetectorType() == 1:
                        if len(self._postureBuff) > 0:
                            posture = self._postureBuff[0]
                            self._postureBuff.clear()
                        else:
                            posture = None
                        return event,timeData, posture
                    else:
                        return event, timeData
            # 接收到的是空包
            elif check == 2:
                self._empty += 1
                triggerID = int.from_bytes(buff[4:6],byteorder='big',signed=False)
                # 如果接收到的是新事件
                if self._temTID != triggerID:
                    # 更新状态信息
                    statusData = self._decodingStatus(buff[10:18])
                    self._statusBuff[statusData[-1]] = tuple(statusData[:-1])
                    # 获取上一个事件的数据
                    event = np.array(self._eventBuff)
                    self._eventBuff.clear()
                    # 更新当前事件ID和软件计数
                    self._temTID = triggerID
                    self._eventCount += 1
                    # 生成timeTag
                    timeData = np.empty(event.shape[0], dtype="uint64")
                    timeData[:] = time.time()
                    # 对于井眼型的数据
                    if self.getDetectorType() == 1:
                        if len(self._postureBuff) > 0:
                            posture = self._postureBuff[0]
                        else:
                            posture = None
                        return event, timeData, posture
                    else:
                        return event, timeData
        if self.getDetectorType() == 1:
            return None,None,None
        else:
            return None,None

    #非阻塞版本，持续运行直到得到一个
    def decodingOneEventData_nonBlocking(self) -> tuple:
        '''
        解析一个事件的数据,当数据不足时返回（None,None)，不会阻塞
        ======THE FORMAT OF SOURCE=====
        ---------DATA PART-------------
        NAME    ROW     SIZE    LOCAL
        HAED    1ROW    2Bytes  0-1
        HGain   36ROW   72Bytes 2-73
        LGain   36ROW   72Bytes 74-145
        BCID    1ROW    2Bytes  146-147
        ChipID  1ROW    2Bytes  148-149
        Temp    1ROW    2Bytes  150-151
        Trigger 1ROW    2Bytes  151-153
        TAIL    1ROW    4Bytes  154-157
        ---------STATUS PART-----------
        TrigDAC 1ROW    2Bytes  158-159 0-1
        INDAC   1ROW    2Bytes  160-161 2-3
        TrigMode1ROW    2Bytes  162-163 4-5
        BoardID 1ROW    2Bytes  164-165 6-7
        TOTAL SIZE: 166

        ======RETURN DATA FORMAT=====
        shape   (n, 40)
        ---------AXIS 0----------
        board   0~n
        ---------AXIS 1-----------
        NAME            LENGTH
        CHARGE          36
        Temp            1
        TrigID          1
        BOARDID         1
        TimeTage        1
        TOTAL LENGTH:   40
        ---------------------------
        DATA TYPE:  np.array
        dtype:      uint16
        :return: np.array:all the valid board data in one event,shape(n,39) / None
                np.array: timeTag, shape(n,) / None
        '''
        while not self._binaryBuff.empty():
            buff = self._binaryBuff.get()
            check = self._checkPackageLength(buff)
            # 如果接收到的是中断
            if check == 0:
                self._interrupt += 1
                newHead = buff.index(b'\xfa\x5a')
                buff = buff[newHead:]
                self._eventBuff.clear()
                check = self._checkPackageLength(buff)
            # 接收到的是正常的包
            if check == 1:
                self._count += 1
                chargeData = self._decodingData(buff[:-8],self._checkMode)
                statusData = self._decodingStatus(buff[-8:])
                # 将boardID载入
                chargeData[38] = statusData[-1]
                # 将设备状态信息更新
                self._statusBuff[statusData[-1]] = tuple(statusData[:-1])
                # 如果在同一个事件中，则将数据存储在事件缓存区中,同时将triggerID改为软件计数器的计数
                if self._temTID == chargeData[37]:
                    chargeData[37] = self._eventCount
                    self._eventBuff.append(chargeData)
                # 接收到的是新的事件
                else:
                    event = np.array(self._eventBuff)
                    self._eventBuff.clear()
                    # 更新当前事件ID和软件计数
                    self._temTID = chargeData[37]
                    self._eventCount += 1
                    #将triggerID改为软件计数器的计数
                    chargeData[37] = self._eventCount
                    self._eventBuff.append(chargeData)
                    # 生成timeTag
                    timeData = np.empty(event.shape[0],dtype="uint64")
                    timeData[:] = time.time()
                    return event, timeData
            # 接收到的是空包
            elif check == 2:
                self._empty += 1
                triggerID = int.from_bytes(buff[4:6],byteorder='big',signed=False)
                # 如果接收到的是新事件
                if self._temTID != triggerID:
                    # 更新状态信息
                    statusData = self._decodingStatus(buff[-8:])
                    self._statusBuff[statusData[-1]] = tuple(statusData[:-1])
                    # 获取上一个事件的数据
                    event = np.array(self._eventBuff)
                    self._eventBuff.clear()
                    # 更新当前事件ID和软件计数
                    self._temTID = triggerID
                    self._eventCount += 1
                    # 生成timeTag
                    timeData = np.empty(event.shape[0], dtype="uint64")
                    timeData[:] = time.time()
                    return event, timeData
            # 遇到未知情况
            else:
                self._unknow += 1
        #在获取到一个新事件之前，数据已经用完
        return (None,None)

    # ==============辅助函数=============
    def _checkPackageLength(self,source: bytes) -> int:
        '''
        检查二进制数据(SSP2E包+status information)的长度
        :param source: one board binary package
        Mask For Return
        bit:    0  normal package
                1  empty package
                2  with posture info package

        :return: 1 normal package
                 2 empty package
                 5/6 with posture info package
                 0 interrupt package
                 -1 unknown package
        '''
        length = len(source)
        if length == 166:
            return 1
        elif length == 16 or length == 18:
            return 2
        elif self.getDetectorType() == 1 and length == 190:
            return 5
        elif self.getDetectorType() == 1 and length == 42:
            return 6
        elif length > 166:
            try:
                idx = source.index(b'\xfa\x5a', 2)
                if len(source[idx:]):
                    return 0
            except ValueError:
                #print(source.hex('-'))
                return -1
        else:
            return -1

    # =============搜寻在二进制数据中搜寻SSP2E数据包和状态信息包===========
    def findSSP2EIndex(self,source: bytes):
        '''
        搜寻二进制数据包头和包尾
        :param source: raw binary data
        :return: tuple() :list of head index;list of tail index; remained data
        '''
        tail = 0
        headList = []
        tailList = []
        while True:
            try:
                head = source.index(b'\xfa\x5a', tail)
                tail = source.index(b'\xfe\xee\xfe\xee',head)
            except:
                break
            if len(source) < tail+12:
                try:
                    tail = tailList[-1]
                except IndexError:
                    tail = 0
                finally:
                    break
            headList.append(head)
            tailList.append(tail)
        return headList,tailList,source[tail:]

    def loadBinaryData(self,source: bytes) -> bytes:
        '''
        将二进制数据根据SSP2E包切分后放入缓存队列中
        #对于大井眼数据，需要额外寻找是否包含姿态信息
        :param source: raw binary data
        :return: remained data
        '''
        tail = 0
        while True:
            try:
                head = source.index(b'\xfa\x5a', tail)
                tail = source.index(b'\xfe\xee\xfe\xee',head)
            except:
                return source[tail+12:]
            if len(source) < tail + 12:
                return source[head:]
            #大井眼，额外姿态信息只会在
            if(self.getDetectorType() == 1):
                if(len(source) > tail + 12 + 15 and source[tail+12 + 14:tail+12 + 16] == b'\xaa\x55'):
                    buff = source[head:tail + 12 + 24]
                    self._binaryBuff.put(buff)
                    continue
            buff = source[head:tail+12]
            self._binaryBuff.put(buff)

    def putStopOrder(self):
        '''
        在数据队列_binaryBuff中添加一个停止信息None,当解析到None时,会抛出异常
        :return:
        '''
        self._binaryBuff.put(-1)

'''
    需要载入的对象：├│└
'''
#将目标h5文件中的某个分片另存为
def dataBackupProcess(filePath:str, index:int):
    h5 = h5Data(filePath)
    toBackup = h5.getData(index)
    _name = os.path.split(filePath)[1]
    name = os.path.splitext(_name)[0]
    if not os.path.exists("./backup"):
        os.mkdir("./backup")
    backPath = os.path.join("./backup","{}_{}_backup.csv".format(name,index))
    toBackup.to_csv(backPath)

#数据读取线程
def loadDataFromSocket(_s: socket.socket, tag: Event, decodeTool: Lumis_Decode):
    '''
    协程函数：从socket中获取原始数据
    :param _s: 获取数据的socket
    :param tag: 消息队列
    :param _e: 运行状态标志
    :param decodeTool: 解码工具
    :return:
    '''
    try:
        print("start receive data")
        _s.send(b'\xff\x00')
        buff = b''
        with open("./binaryFile","bw") as file:
            while tag.is_set():
                tmpB = _s.recv(decodeTool.readSize())
                file.write(tmpB)
                buff += tmpB
                buff = decodeTool.loadBinaryData(buff)
    finally:
        _s.send(b'\xff\x01')
        time.sleep(0.1)
        _s.close()
        # 当解码进程解析到结束信号时会结束循环
        decodeTool.putStopOrder()
        print('loadDataFromSocket:', 'end')

#数据解码线程
def dataDecode(tag: Event, h5: h5Data, decodeTool: Lumis_Decode):
    '''
    a thread function to decode binary data.
    负责解码数据，将数据写入h5文件，开始时将写入设备配置状态。
    :param h5File: a h5Data object to output data to h5 file
    :param decodeTool: to decode binary data
    :return:
    '''
    h5.startTime()
    t = time.time()
    # 开始解码数据
    try:
        _tmp = decodeTool.decodingOneEventData()
        if len(_tmp) == 2:
            event, timeTag = _tmp
        else:
            event, timeTag, posture = _tmp
        # 对于第一组数据，除将数据导入h5文件中，还会将状态信息导入h5文件
        # 因此避免了第一次判断triggerID为零时判断为置零
        if event.shape[0] != 0:
            eventID = event[0][-2]
            if h5.getDetectorType() == 1:
                h5.addToDataSet(event, timeTag, postureInfo=posture, postureIndex=np.array([eventID]))
            else:
                h5.addToDataSet(event, timeTag)
            h5.addToDataSet(event,timeTag)
        else:
            eventID = 0
        h5.putDeviceStatus(decodeTool.devStatus())
        while tag.is_set():
            if decodeTool.getDetectorType() == 1:
                event, timeTag, posture = decodeTool.decodingOneEventData()
            else:
                event,timeTag = decodeTool.decodingOneEventData()
            # 将数据导入h5文件中（需要检查当前事件是否全为空包）
            if event.shape[0] != 0:
                if event[0][-2] <= eventID:
                    index = h5.newSets()
                    if decodeTool.getDataBackup():
                        #开启新线程来将上一个sheet的数据
                        p = Process(target=dataBackupProcess,args=(h5.file.filename,index-1))
                        p.start()
                eventID = event[0][-2]
                if h5.getDetectorType() == 1:
                    h5.addToDataSet(event, timeTag, postureInfo = posture, postureIndex = np.array([eventID]))
                else:
                    h5.addToDataSet(event, timeTag)
            if time.time() - t > 5:
                h5.flush()
                t = time.time()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print('dataDecode:',e.__str__())
        import traceback
        traceback.print_exc()
    finally:
        h5.stopTime()
        h5.close()
    print('dataDecode:','end')

