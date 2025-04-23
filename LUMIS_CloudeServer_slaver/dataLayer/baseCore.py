'''
包含一些基础使用的数据对象
'''
import numpy as np
import pandas as pd
from datetime import datetime
import h5py
from dataLayer import _Index
import time

__all__ = ['h5Data']


class h5Data(object):
    '''
    For different h5 file, choose it correspondingly reader/writer.
    now support plate detector<0> and log detector<1>
    '''
    def __init__(self, path:str, mode:str = 'r', detectorType:int = 0,MainVersion:int = 1,**kwargs):
        if mode[0] == 'w':
            self.detectorType = detectorType
            if(detectorType == 0):
                self.Engine = h5Data_plate(path,mode,MainVersion) # 平面型探测器的数据采集到H5
            elif(detectorType == 1):
                self.Engine = h5Data_log(path,mode,MainVersion) # 井眼型探测器的数据采集到H5
        elif mode[0] == 'r':
            file = h5py.File(path, mode=mode, libver='latest', swmr=True)
            # 根据设备型号选择读取引擎
            infoGroup: h5py.Group = file['info']
            if("detectorType" in infoGroup.attrs):
                self.detectorType = infoGroup.attrs["detectorType"]
            else:
                self.detectorType = 0
            file.close()
            if(self.detectorType == 0):
                self.Engine = h5Data_plate(path,mode)
            elif(self.detectorType == 1):
                self.Engine = h5Data_log(path,mode)

    # ==========基本信息==========
    def version(self) -> int:
        return self.Engine.mainVersion

    def getDetectorType(self) -> int:
        return self.detectorType

    def startTime(self) -> datetime:
        return self.Engine.startTime()

    def stopTime(self) -> datetime:
        return self.Engine.stopTime()

    def totalTime(self) -> float:
        return self.Engine.totalTime()

    def putDeviceStatus(self,status: dict):
        self.Engine.putDeviceStatus(status)

    def getDeviceStatus(self) -> list:
        return self.Engine.getDeviceStatus()

    #============数据==============
    def addToDataSet(self, value: np.array, timeTag = None,**kwargs):
        self.Engine.addToDataSet(value,timeTag,**kwargs)

    def getData(self, index: int = -1, startIndex: int = 0, dtype = 'int64') -> pd.DataFrame:
        return  self.Engine.getData(index, startIndex, dtype)

    #============内部=============
    def getSetsIndex(self) -> int:
        return self.Engine.getSetsIndex()

    def getReadMode(self) -> bool:
        return self.Engine.getReadMode()

    def getFileName(self) -> str:
        return self.Engine.getFileName()

    #============辅助=============
    def flush(self):
        return self.Engine.flush()

    def newSets(self):
        return self.Engine.newSets()

    def close(self):
        return self.Engine.close()

    #===========井眼型数据的姿态信息==========
    def getPosture(self,triggerIDStart: int = None, triggerIDStop:int = None ):
        if self.getDetectorType() == 1:
            return self.Engine.getPosture(triggerIDStart, triggerIDStop)
        else:
            print("Error: --getPosture-- only for WELLLOG!!!")
            return 0

    def getFinalPosture(self):
        if self.getDetectorType() == 1:
            return self.Engine.getFinalPosture()

    #=========继承内部引擎的成员变量========
    @property
    def file(self):
        return self.Engine.file

    @property
    def timeInfo(self):
        return self.Engine.timeInfo

    @property
    def statusInfo(self):
        return self.Engine.statusInfo

    @property
    def data(self):
        return self.Engine.data

    @property
    def timeTag(self):
        return self.Engine.timeTag

    @property
    def index(self):
        return self.Engine.index

    @property
    def postureInfo(self):
        if self.detectorType == 1:
            return self.Engine.postureInfo

    @property
    def postureIndex(self):
        if self.detectorType == 1:
            return self.Engine.postureIndex



# 操作h5文件
class h5Data_plate(object):
    '''├│└
    =========FORMAT OF H5 FILE========
    root
     ├info(group)
    {| ├["version"] int
     | ├["detectorType"]=0 }<version >= 1>
     │ ├time(dataset)
     │ │ ├start time <float64>
     │ │ ├stop time <float64>
     │ │ └total time <float64>
     │ └device_status(dataset) <uint16>
     │   ├trigger mode
     │   ├board 0 threshold
     │   ├~~~~~~~
     │   ├board 7 threshold
     │   ├board 0 bias voltage
     │   ├~~~~~
     │   └board 7 bias voltage
     └dataGroup(group)
        ├data(dataSet)
        │ └data<uint16>
        ├timeTag(dataSet)
        │ └timeTag<uint64>
        └index(dataSet)
          └index<int64>

    ===========FORMAT OF DATA===========
    columnIndex:    0-35        36              37          38
    name            chn_{}      temperature     triggerID   boardID
    note            Energy

    ===========FORMAT OF TIME TAG========
    only one column: timeTag

    ===========FORMAT OF INDEX==========
    only one row
    columnIndex:    0                   1-INF
    note:           count of data row   each reset row


    '''
    classMainVersion = 1
    subVersion = 0
    def __init__(self, path: str, mode: str = 'r',MainVersion:int = 1):
        '''
        :param path: the path of h5 file
        :param mode: "w" or "r"
        :param MainVersion: the main version of plate
        内部参数：
            file:h5文件
            readMode:是否是读模式
            SetsIndex:数据集的索引
            dataIndex:数据集的数据索引
        ==========dataset==========
            timeInfo:'time'
            statusInfo:'device_status'

            data:'data',数据
            timeTag:'timeTag', 时间标签
            index:'index'-----数据存储结构：为线性数组，第一个数据(索引为0)为当前数据总行数，
                        之后的每一个都是triggerID置零时的索引(第一个triggerID为0时的索引)
                        index的shape和重置次数对应
        '''

        if mode[0] == 'w':
            self.mainVersion = MainVersion
            if (self.mainVersion > self.classMainVersion):
                raise Exception("h5Data maximum version<{}> support lower then require version<{}>".format(self.classMainVersion,self.mainVersion))
            self.file = h5py.File(path, mode=mode, libver='latest')
            self.readMode = False
            # 写模式单独参数
            self.dataIndex = 0 # 当前写到第几行
            self.setsIndex = 0 # 当前存在几次triggerID置零
            # 存储信息
            infoGroup = self.file.create_group('info') # 信息组
            if(self.mainVersion > 0):
                infoGroup.attrs["version"] = self.mainVersion # 存储版本信息
                infoGroup.attrs["detectorType"] = 0 #存储设备型号信息
            self.timeInfo = infoGroup.create_dataset('time', shape=(3, ), maxshape=(None,), dtype='float64') # 开始时间、结束时间、各分片运行时间
            self.statusInfo = infoGroup.create_dataset('device_status', shape=(17,), dtype='uint16') # 各个板的状态信息
            # 数据信息
            dataGroup = self.file.create_group('dataGroup')  # 数据组
            self.data = dataGroup.create_dataset('data', shape=(5000,39), maxshape=(None,39), dtype='uint16')
            self.timeTag = dataGroup.create_dataset('timeTag', shape=(5000,), maxshape=(None,), dtype='uint64')
            self.index = dataGroup.create_dataset('index', shape=(1,), maxshape=(None,), dtype='int64')
            # 设置为single writer multiply reader 模式
            self.file.swmr_mode = True
        elif mode[0] == 'r':
            self.file = h5py.File(path, mode=mode, libver='latest', swmr=True)
            self.readMode = True
            # 存储信息
            infoGroup:h5py.Group = self.file['info']
            self.timeInfo = infoGroup['time']
            self.statusInfo = infoGroup['device_status']
            # 获取h5文件的版本/低版本reader不能load高版本的文件
            if "version" in infoGroup.attrs:
                self.mainVersion = infoGroup.attrs["version"]
                if(self.mainVersion > self.classMainVersion):
                    self.file.close()
                    raise Exception("you can't use lower version<{}> reader to load this file(minimum version<{}> require)".format(self.classMainVersion,self.mainVersion))
            else:
                self.mainVersion = 0
            # 数据信息
            dataGroup = self.file['dataGroup']
            self.data = dataGroup['data']
            self.timeTag = dataGroup['timeTag']
            self.index = dataGroup['index']

    #===========信息==========
    # 添加开始时间
    def startTime(self) -> datetime:
        '''
        "w":add start time (now time) to h5 file,and return it
        "r":just return start time (from h5)
        :return: start time
        '''
        if self.readMode:
            start = datetime.fromtimestamp(self.timeInfo[0])
            return start
        else:
            self.start = datetime.now()
            self.timeInfo[0] = self.start.timestamp()
            return self.start

    # 添加结束时间和总运行时间,并关闭h5文件
    def stopTime(self) -> datetime:
        '''
        "w":add stop time (now time) and total running time to h5 file,and return it
        "r":just return stop time (from h5)
        :return: stop time
        '''
        if self.readMode:
            stop = datetime.fromtimestamp(self.timeInfo[1])
            return stop
        else:
            stop = datetime.now()
            t = stop.timestamp() - self.start.timestamp()
            self.timeInfo[1] = stop.timestamp()
            self.timeInfo[2] = t
            self.close()
            return stop

    # 返回总运行时间
    def totalTime(self) -> float:
        '''
        "w":raise Exception
        "r": get total running time (from h5)
        :return: total running time (unit:s)
        '''
        return self.timeInfo[1] - self.timeInfo[0]

    # 录入设备状态信息
    def putDeviceStatus(self,status: dict):
        '''
        "w": write device configuration state to h5 file
        "r": raise Exception
        :param status:dict:key:boardID;value:tuple(threshold, biasVoltage, triggerMode)
        :return: 
         ├trigger mode
         ├board 0 threshold
         ├~~~~~~~
         ├board 7 threshold
         ├board 0 bias voltage
         ├~~~~~
         └board 7 bias voltage
        '''
        # print(status)
        triggerMode = status[0][2]
        self.statusInfo[0] = triggerMode
        for i in range(8):# boardID: 0--7
            t = status.get(i, (0, 0, 0)) # 若boardID=i不存在，返回默认元组(0,0,0)
            self.statusInfo[i+1] = t[0] # threshold
            self.statusInfo[i+9] = t[1] # biasVoltage

    # 获取h5文件中存储的设备状态信息
    def getDeviceStatus(self) -> list:
        '''
        :return: dict:key:boardID;value:list(threshold, bias voltage, trigger mode)
        '''
        status = []
        triggerMode = int(self.statusInfo[0])
        for i in range(8):
            threshold = int(self.statusInfo[i + 1])
            biasVoltage = int(self.statusInfo[i + 9])
            if threshold == 0 and biasVoltage == 0:
                break
            else:
                status.append([threshold, biasVoltage, triggerMode])
        return status

    #===============数据=================
    # 将数据添加到h5数据集中
    def addToDataSet(self, value: np.array, timeTag = None,**kwargs):
        '''
        "w": add data to h5 file
        "r": raise Exception
        :param value: data,type:np.array,dtype:'uint16',shape:(n,39)
                    column 0-38 will be pushed into group(data), column 39 will be pushed into group(timeTag)
        :param NewSets: if it set as True,h5 file will create a new data set to contain data
        :return:
        '''
        # 如果数据集的长度不够，则扩展5000行
        if self.dataIndex + value.shape[0] <= self.data.shape[0]:
            self.data.resize(self.data.shape[0] + 5000, axis=0)
            self.timeTag.resize(self.data.shape[0] + 5000, axis=0)
        # 数据存储
        self.data.write_direct(value, source_sel=np.s_[0:value.shape[0]],
                               dest_sel=np.s_[self.dataIndex:value.shape[0]+self.dataIndex])
        if timeTag is not None:
            self.timeTag.write_direct(timeTag, source_sel=np.s_[0:value.shape[0]],
                               dest_sel=np.s_[self.dataIndex:value.shape[0]+self.dataIndex])
        self.dataIndex += value.shape[0]
        self.index[0] = self.dataIndex

    # 读取h5文件中的数据
    def getData(self, index: int = -1, startIndex: int = 0, dtype = 'int64') -> pd.DataFrame:
        '''
            read data in h5 file
            :param index: When the index greater than or equal to 0, the corresponding set of data will be returned.
            when the index equal to -1,all the data will be returned.
            when the index equal to -2,all the data will be returned and the triggerID in returned data has been accumulated.
            :param startIndex: data will be returned from the startIndex
            :return:
        '''
        if index + 1 > self.index.shape[0] or index < -2:
            raise ValueError('index({}) out of range (-2-{})'.format(index, self.index.shape[0] - 1))
        if startIndex > self.index[0]:
            raise ValueError('startIndex({}) out of range (0-{})'.format(startIndex, self.index[0]))
        # ========特殊索引========
        if index == -1:
            set = self.data[startIndex:self.index[0]]
            timetage = self.timeTag[startIndex:self.index[0]].reshape((-1,1))
            # 合并能量信息和时间信息-shape——>(-1,40)
            set = np.append(set,timetage,axis=1)
            # print("getData:{}".format(set))
            _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
            return _d
        elif index == -2:
            _d = pd.DataFrame(columns=_Index, dtype=dtype)
            for i in range(self.index.shape[0]):
                _s = self.getData(i,startIndex=startIndex)
                _s['triggerID'] = _s['triggerID'] + i * 65535
                _d =_d._append(_s, ignore_index=True)
            return _d
        # ========普通索引========
        if index == 0:      #选择第一个数据集时
            if self.index.shape[0] == 1:
                stop = self.index[0]
            else:
                stop = self.index[1]
            if startIndex >= stop:
                _d = pd.DataFrame(columns=_Index, dtype=dtype)
            else:
                set = np.empty((stop - startIndex, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - startIndex,), dtype='int64')
                self.timeTag.read_direct(timetag,source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1,1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
        elif index + 1 == self.index.shape[0]:      # 选择最后一个数据集时
            stop = self.index[0]
            start = self.index[index]
            if startIndex >= stop:
                _d = pd.DataFrame(columns=_Index, dtype=dtype)
            elif startIndex < start:
                set = np.empty((stop - start, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - start,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
            else:
                set = np.empty((stop - startIndex, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - startIndex,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
        else:       # 选择中间数据集时
            # 当判断到此时，index比self.index.shape[0]至少小2，比最大索引小1，index+1不会超出边界
            start = self.index[index]
            stop = self.index[index+1]
            if startIndex >= stop:
                _d = pd.DataFrame(columns=_Index, dtype=dtype)
            elif startIndex < start:
                set = np.empty((stop - start, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - start,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
            else:
                set = np.empty((stop - startIndex, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - startIndex,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
        return _d

    #==============内部=============
    # 获取triggerID重置次数
    def getSetsIndex(self) -> int:
        return self.setsIndex

    # 获取读取模式
    def getReadMode(self) -> bool:
        return self.readMode

    # 获取文件路径/文件名
    def getFileName(self) -> str:
        return self.file.filename
    #=============辅助===============
    # 将存储在缓冲区的数据输出到磁盘中去
    def flush(self):
        if self.readMode:
            self.data.refresh()
            self.timeTag.refresh()
            self.index.refresh()
            self.timeInfo.refresh()
            self.statusInfo.refresh()
        else:
            self.file.flush()

    # 表示triggerID重置，添加重置处索引并添加分片时间
    def newSets(self):
        '''
        set reset triggerID in index
        '''
        self.setsIndex += 1
        self.index.resize(self.index.shape[0]+1,axis=0)
        self.timeInfo.resize(self.timeInfo.shape[0]+1, axis=0)
        # 添加分片时间
        self.index[self.setsIndex] = self.dataIndex
        self.timeInfo[self.timeInfo.shape[0]-1] = datetime.now().timestamp()
        return self.setsIndex

    # 关闭h5文件流
    def close(self):
        if self.file:
            if not self.readMode:
                print('h5 index:',self.dataIndex)
                self.data.resize(self.dataIndex, axis=0)
            self.file.close()

class h5Data_log(object):
    '''├│└
    =========FORMAT OF H5 FILE========
    root
     ├info(group)
     | ├["version"] int
     | ├["detectorType"]=1
     │ ├time(dataset)
     │ │ ├start time<float64>
     │ │ ├stop time<float64>
     │ │ └total time<float64>
     │ ├movingPosture(dataset)
     │ │ └postureData<float64>
     │ ├movingPostureIndex(dataset)
     │ │ └postureIndex<uint16>
     │ └device_status(dataset)<uint16>
     │   ├trigger mode
     │   ├board 0 threshold
     │   ├~~~~~~~
     │   ├board 7 threshold
     │   ├board 0 bias voltage
     │   ├~~~~~
     │   └board 7 bias voltage
     └dataGroup(group)
        ├data(dataSet)
        │ └data<uint16>
        ├timeTag(dataSet)
        │ └timeTag<uint64>
        └index(dataSet)
          └index<int64>


     ===========FORMAT OF DATA===========
    columnIndex:    0-35        36              37          38
    name            chn_{}      temperature     triggerID   boardID
    note            Energy

    ===========FORMAT OF TIME TAG========
    only one column: timeTag

    ===========FORMAT OF INDEX==========
    only one row
    columnIndex:    0                   1-INF
    note:           count of data row   each reset row

    ===========FORMAT OF POSTURE DATA========
    columnIndex:    0           1               2                   3                   4
    name:           checkSum    gyroTemperature gyroXAccelerated    gyroYAccelerated    gyroZAccelerated
    note:

    columnIndex:    5                       6                       7                       8
    name:           gyroXAngularVelocity    gyroYAngularVelocity    gyroZAngularVelocity    SeekerStatus
    note:

    columnIndex:    9               10              11
    name:           SeekerRoll      SeekerPitch     SeekerAzimuth
    note:

    ===========FORMAT OF POSTURE INDEX======
    only one column: event index
    '''
    classMainVersion = 1
    subVersion = 0
    def __init__(self, path: str, mode: str = 'r', MainVersion: int = 1):
        '''
        :param path: the path of h5 file
        :param mode: "w" or "r"
        :param MainVersion: the main version of plate
        内部参数：
            file:h5文件
            readMode:是否是读模式
            SetsIndex:数据集的索引
            dataIndex:数据集的数据索引
        ==========dataset==========
            timeInfo:'time'
            statusInfo:'device_status'

            data:'data',数据
            timeTag:'timeTag', 时间标签
            index:'index'-----数据存储结构：为线性数组，第一个数据(索引为0)为当前数据总行数，
                        之后的每一个都是triggerID置零时的索引(第一个triggerID为0时的索引)
                        index的shape和重置次数对应
        '''

        if mode[0] == 'w':
            self.mainVersion = MainVersion
            if (self.mainVersion > self.classMainVersion):
                raise Exception(
                    "h5Data maximum version<{}> support lower then require version<{}>".format(self.classMainVersion,
                                                                                               self.mainVersion))
            self.file = h5py.File(path, mode=mode, libver='latest')
            self.readMode = False
            # 写模式单独参数
            self.dataIndex = 0  # 当前写到第几行
            self.setsIndex = 0  # 当前存在几次triggerID置零
            self.eventIndex = 0 # 当前写到第几个事件，记录扩展姿态信息长度
            # 存储信息
            infoGroup = self.file.create_group('info')  # 信息组
            infoGroup.attrs["version"] = self.mainVersion  # 存储版本信息
            infoGroup.attrs["detectorType"] = 1  # 存储设备型号信息
            self.timeInfo = infoGroup.create_dataset('time', shape=(3,), maxshape=(None,),
                                                     dtype='float64')  # 开始时间、结束时间、各分片运行时间
            self.statusInfo = infoGroup.create_dataset('device_status', shape=(17,), dtype='uint16')  # 各个板的状态信息
            self.postureInfo = infoGroup.create_dataset('movingPosture', shape=(5000,12),maxshape=(None,12), dtype='float32') # 姿态信息
            self.postureIndex = infoGroup.create_dataset('movingPostureIndex', shape=(5000,), maxshape=(None,),dtype='uint64') # 事件索引
            # 数据信息
            dataGroup = self.file.create_group('dataGroup')  # 数据组
            self.data = dataGroup.create_dataset('data', shape=(5000, 39), maxshape=(None, 39), dtype='uint16')
            self.timeTag = dataGroup.create_dataset('timeTag', shape=(5000,), maxshape=(None,), dtype='uint64')
            self.index = dataGroup.create_dataset('index', shape=(1,), maxshape=(None,), dtype='int64')
            # 设置为single writer multiply reader 模式
            self.file.swmr_mode = True
        elif mode[0] == 'r':
            self.file = h5py.File(path, mode=mode, libver='latest', swmr=True)
            self.readMode = True
            # 存储信息
            infoGroup: h5py.Group = self.file['info']
            self.timeInfo = infoGroup['time']
            self.statusInfo = infoGroup['device_status']
            self.postureInfo = infoGroup['movingPosture']
            self.postureIndex = infoGroup['movingPostureIndex']
            # 获取h5文件的版本/低版本reader不能load高版本的文件
            if "version" in infoGroup.attrs:
                self.mainVersion = infoGroup.attrs["version"]
                if (self.mainVersion > self.classMainVersion):
                    self.file.close()
                    raise Exception(
                        "you can't use lower version<{}> reader to load this file(minimum version<{}> require)".format(
                            self.classMainVersion, self.mainVersion))
            else:
                self.mainVersion = 0
            # 数据信息
            dataGroup = self.file['dataGroup']
            self.data = dataGroup['data']
            self.timeTag = dataGroup['timeTag']
            self.index = dataGroup['index']

    # ===========信息==========
    # 添加开始时间
    def startTime(self) -> datetime:
        '''
        "w":add start time (now time) to h5 file,and return it
        "r":just return start time (from h5)
        :return: start time
        '''
        if self.readMode:
            start = datetime.fromtimestamp(self.timeInfo[0])
            return start
        else:
            self.start = datetime.now()
            self.timeInfo[0] = self.start.timestamp()
            return self.start

    # 添加结束时间和总运行时间,并关闭h5文件
    def stopTime(self) -> datetime:
        '''
        "w":add stop time (now time) and total running time to h5 file,and return it
        "r":just return stop time (from h5)
        :return: stop time
        '''
        if self.readMode:
            stop = datetime.fromtimestamp(self.timeInfo[1])
            return stop
        else:
            stop = datetime.now()
            t = stop.timestamp() - self.start.timestamp()
            self.timeInfo[1] = stop.timestamp()
            self.timeInfo[2] = t
            self.close()
            return stop

    # 返回总运行时间
    def totalTime(self) -> float:
        '''
        "w":raise Exception
        "r": get total running time (from h5)
        :return: total running time (unit:s)
        '''
        return self.timeInfo[1] - self.timeInfo[0]

    # 录入设备状态信息
    def putDeviceStatus(self, status: dict):
        '''
        "w": write device configuration state to h5 file
        "r": raise Exception
        :param status:dict:key:boardID;value:tuple(threshold, biasVoltage, triggerMode)
        :return:
        '''
        # print(status)
        triggerMode = status[0][2]
        self.statusInfo[0] = triggerMode
        for i in range(8):
            t = status.get(i, (0, 0, 0))
            self.statusInfo[i + 1] = t[0]
            self.statusInfo[i + 9] = t[1]

    # 获取h5文件中存储的设备状态信息
    def getDeviceStatus(self) -> list:
        '''
        :return: dict:key:boardID;value:list(threshold, bias voltage, trigger mode)
        '''
        status = []
        triggerMode = int(self.statusInfo[0])
        for i in range(8):
            threshold = int(self.statusInfo[i + 1])
            biasVoltage = int(self.statusInfo[i + 9])
            if threshold == 0 and biasVoltage == 0:
                break
            else:
                status.append([threshold, biasVoltage, triggerMode])
        return status

    # 获取最后的姿态数据
    def getFinalPosture(self) -> pd.DataFrame:
        index = self.findPostureEnd()
        result = pd.DataFrame(data=self.postureInfo[index:index+1],
                              index=self.postureIndex[index:index+1],
                              columns=["checkSum", "gyroTemperature",
                                       "gyroXAccelerated", "gyroYAccelerated", "gyroZAccelerated",
                                       "gyroXAngularVelocity", "gyroYAngularVelocity", "gyroZAngularVelocity",
                                       "SeekerStatus", "SeekerRoll", "SeekerPitch", "SeekerAzimuth"])
        return result

    # ===============数据=================
    # 将数据添加到h5数据集中
    def addToDataSet(self, value: np.array, timeTag:np.array=None, postureInfo: np.array = None,postureIndex: np.array = None, **kwargs):
        '''
        "w": add data to h5 file
        "r": raise Exception
        :param value: data,type:np.array,dtype:'uint16',shape:(n,39)
                    column 0-38 will be pushed into group(data), column 39 will be pushed into group(timeTag)
        :param timeTag: time of each row (n,)
        :param postureInfo: posture of each event (m, 11). m is the count of event;
        :param NewSets: if it set as True,h5 file will create a new data set to contain data
        :return:
        '''
        # 如果数据集的长度不够，则扩展5000行
        if self.dataIndex + value.shape[0] >= self.data.shape[0]:
            self.data.resize(self.data.shape[0] + 5000, axis=0)
            self.timeTag.resize(self.data.shape[0] + 5000, axis=0)
        # 数据存储
        self.data.write_direct(value, source_sel=np.s_[0:value.shape[0]],
                               dest_sel=np.s_[self.dataIndex:value.shape[0] + self.dataIndex])
        if timeTag is not None:
            self.timeTag.write_direct(timeTag, source_sel=np.s_[0:value.shape[0]],
                                      dest_sel=np.s_[self.dataIndex:value.shape[0] + self.dataIndex])
        self.dataIndex += value.shape[0]
        self.index[0] = self.dataIndex
        if postureInfo is not None:
            # 如果姿态数据集的长度不够，则扩展5000行
            if self.eventIndex + postureInfo.shape[0] >= self.postureInfo.shape[0]:
                self.postureInfo.resize(self.postureInfo.shape[0]+5000,axis=0)
                self.postureIndex.resize(self.postureInfo.shape[0]+5000,axis=0)
            self.postureInfo.write_direct(postureInfo, source_sel=np.s_[0:postureInfo.shape[0]],
                                          dest_sel=np.s_[self.eventIndex:postureInfo.shape[0] + self.eventIndex])
            self.postureIndex.write_direct(postureIndex + 65536 * self.getSetsIndex(), source_sel=np.s_[0:postureIndex.shape[0]],
                                           dest_sel=np.s_[self.eventIndex:postureIndex.shape[0]+ self.eventIndex])

            self.eventIndex += postureIndex.shape[0]

    # 读取h5文件中的数据
    def getData(self, index: int = -1, startIndex: int = 0, dtype='int64') -> pd.DataFrame:
        '''
            read data in h5 file
            :param index: When the index greater than or equal to 0, the corresponding set of data will be returned.
            when the index equal to -1,all the data will be returned.
            when the index equal to -2,all the data will be returned and the triggerID in returned data has been accumulated.
            :param startIndex: data will be returned from the startIndex
            :return:
        '''
        if index + 1 > self.index.shape[0] or index < -2:
            raise ValueError('index({}) out of range (-2-{})'.format(index, self.index.shape[0] - 1))
        if startIndex > self.index[0]:
            raise ValueError('startIndex({}) out of range (0-{})'.format(startIndex, self.index[0]))
        # ========特殊索引========
        if index == -1:
            set = self.data[startIndex:self.index[0]]
            timetage = self.timeTag[startIndex:self.index[0]].reshape((-1, 1))
            # 合并能量信息和时间信息-shape——>(-1,40)
            set = np.append(set, timetage, axis=1)
            # print("getData:{}".format(set))
            _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
            return _d
        elif index == -2:
            _d = pd.DataFrame(columns=_Index, dtype=dtype)
            for i in range(self.index.shape[0]):
                _s = self.getData(i, startIndex=startIndex)
                _s['triggerID'] = _s['triggerID'] + i * 65535
                _d = _d._append(_s, ignore_index=True)
            return _d
        # ========普通索引========
        if index == 0:  # 选择第一个数据集时
            if self.index.shape[0] == 1:
                stop = self.index[0]
            else:
                stop = self.index[1]
            if startIndex >= stop:
                _d = pd.DataFrame(columns=_Index, dtype=dtype)
            else:
                set = np.empty((stop - startIndex, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - startIndex,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
        elif index + 1 == self.index.shape[0]:  # 选择最后一个数据集时
            stop = self.index[0]
            start = self.index[index]
            if startIndex >= stop:
                _d = pd.DataFrame(columns=_Index, dtype=dtype)
            elif startIndex < start:
                set = np.empty((stop - start, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - start,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
            else:
                set = np.empty((stop - startIndex, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - startIndex,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
        else:  # 选择中间数据集时
            # 当判断到此时，index比self.index.shape[0]至少小2，比最大索引小1，index+1不会超出边界
            start = self.index[index]
            stop = self.index[index + 1]
            if startIndex >= stop:
                _d = pd.DataFrame(columns=_Index, dtype=dtype)
            elif startIndex < start:
                set = np.empty((stop - start, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - start,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
            else:
                set = np.empty((stop - startIndex, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - startIndex,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
        return _d

    # 获取姿态信息
    def getPosture(self,triggerIDStart: int = None, triggerIDStop:int = None ):
        if triggerIDStop is not None:
            stopIdx = self.findPostureIndex(triggerIDStop)
        else:
            stopIdx = self.findPostureEnd()+1
        if triggerIDStart is not None:
            startIdx = self.findPostureIndex(triggerIDStart)
        else:
            startIdx = 0
        if startIdx is None:
            return None
        if stopIdx is None:
            stopIdx = self.findPostureEnd()+1
        result = pd.DataFrame(data=self.postureInfo[startIdx:stopIdx],
                              index=self.postureIndex[startIdx:stopIdx],
                              columns=["checkSum","gyroTemperature",
                                       "gyroXAccelerated","gyroYAccelerated","gyroZAccelerated",
                                       "gyroXAngularVelocity","gyroYAngularVelocity","gyroZAngularVelocity",
                                       "SeekerStatus","SeekerRoll","SeekerPitch","SeekerAzimuth"])
        return result

    #======姿态数据辅助函数=======
    #通过二分法查找最后一个姿态的索引
    def findPostureEnd(self):
        if not self.readMode:
            return self.eventIndex
        right = self.postureIndex.shape[0]-1
        left = 0
        i = self.postureIndex[right]
        if i != 0:
            return right
        while (right > left):
            mid = (int)((left + right) / 2)
            i = self.postureIndex[mid]
            if (i == 0):
                right = mid - 1
            else:
                left = mid + 1
        if(self.postureIndex[left] == 0):
            return left-1
        else:
            return left

    # 通过二分法查找triggerID索引位置
    def findPostureIndex(self,triggerID:int):
        right = self.findPostureEnd()
        left = 0
        while(right > left):
            mid = (int) ((left + right) / 2)
            i = self.postureIndex[mid]
            if(i < triggerID):
                left = mid + 1
            elif(i > triggerID):
                right = mid - 1
            else:
                return mid
        return left

    # ==============内部=============
    # 获取triggerID重置次数
    def getSetsIndex(self) -> int:
        return self.setsIndex

    # 获取读取模式
    def getReadMode(self) -> bool:
        return self.readMode

    # 获取文件路径/文件名
    def getFileName(self) -> str:
        return self.file.filename

    # =============辅助===============
    # 将存储在缓冲区的数据输出到磁盘中去
    def flush(self):
        if self.readMode:
            self.data.refresh()
            self.timeTag.refresh()
            self.index.refresh()
            self.timeInfo.refresh()
            self.statusInfo.refresh()
        else:
            self.file.flush()

    # 表示triggerID重置，添加重置处索引并添加分片时间
    def newSets(self):
        '''
        set reset triggerID in index
        '''
        self.setsIndex += 1
        self.index.resize(self.index.shape[0] + 1, axis=0)
        self.timeInfo.resize(self.timeInfo.shape[0] + 1, axis=0)
        # 添加分片时间
        self.index[self.setsIndex] = self.dataIndex
        self.timeInfo[self.timeInfo.shape[0] - 1] = datetime.now().timestamp()
        return self.setsIndex

    # 关闭h5文件流
    def close(self):
        if self.file:
            if not self.readMode:
                print('h5 index:', self.dataIndex, "posture index:", self.eventIndex)
                self.data.resize(self.dataIndex, axis=0)
                self.timeTag.resize(self.dataIndex,axis=0)
                self.postureIndex.resize(self.eventIndex,axis=0)
                self.postureInfo.resize(self.eventIndex,axis=0)
            self.file.close()

# 一个存储文件路径
class filePath(object):
    def __init__(self, **kwargs):
        self.p = kwargs.get("path",'')

    def get(self) -> str:
        return self.p

    def set(self,value: str):
        self.p = value

# server操作h5文件
class LUMISData():
    def __init__(self, path: str, mode: str = 'r',**kwargs):
        if mode[0] == 'w':
            self.file = h5py.File(path, mode=mode, libver='latest')
            self.readMode = False
            # 文件信息
            self.file.attrs["version"] = "0.2"
            self.file.attrs["project"] = kwargs.get("project", "unknown")
            self.file.attrs["create time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            self.file.attrs["note"] = ""
        if mode[0] == 'r':
            self.file = h5py.File(path, mode=mode, libver='latest', swmr=True)
            #检查读取文件的版本
            try:
                self.file.attrs["version"]
            except KeyError:
                raise ValueError(
                    "LUMISData can only read Lumis Data version = 0.2. if version = 0.1, please try h5Data to load it.")
            if  self.file.attrs["version"] != "0.2":
                raise ValueError(
                    "LUMISData can only read Lumis Data version = 0.2. if version = 0.1, please try h5Data to load it.")

            self.readMode = True

    def version(self):
        return self.file.attrs["version"]

    def showNote(self):
        return self.file.attrs["note"]

    def project(self):
        return self.file.attrs["project"]

    def createTime(self):
        return self.file.attrs["create time"]

    def deviceList(self):
        devList = set()
        for dataPath in self.file.keys():
            deviceName = self.file[dataPath].attrs["name"]
            devList.add(deviceName)
        return list(devList)

    def dataPathList(self, deviceName = None):
        if deviceName is None:
            return list(self.file.keys())
        else:
            result = []
            for dataPath in self.file.keys():
                name = self.file[dataPath].attrs["name"]
                if name == deviceName:
                    result.append(dataPath)
            return result

    def getDevData(self,path:str):
        return LUMISDevData(self.file[path],self)

    def newDevData(self, path,deviceName:str):
        dataGroup = self.file.create_group(path)
        data = dataGroup.create_dataset("data", shape=(5000,39),maxshape=(None, 39), dtype='uint16')
        index = dataGroup.create_dataset("index", shape=(1,), maxshape=(None,), dtype='int64')
        timeTag = dataGroup.create_dataset("timeTag", shape=(5000,), maxshape=(None,), dtype='uint64')
        device_status = dataGroup.create_dataset("device_status", shape=(17,), dtype='uint16')
        t = time.time()
        dataGroup.attrs["start time"] = t
        dataGroup.attrs["stop time"] = t
        index[0] = 0
        dataGroup.attrs["name"] = deviceName
        return LUMISDevData(dataGroup, self)

    # 获取读取模式
    def getReadMode(self) -> bool:
        return self.readMode

    def __del__(self):
        self.file.close()

# 一个设备的数据
class LUMISDevData():
    def __init__(self,dataGroup:h5py.Group, parent:LUMISData):
        self.parent = parent
        self.data = dataGroup['data']
        self.timeTag = dataGroup['timeTag']
        self.index = dataGroup['index']
        self.DevName = dataGroup.attrs["name"]
        self.statusInfo = dataGroup['device_status']
        self.dataGroup = dataGroup
        self.dataIndex = self.index[0] # 当前写到第几行
        self.setsIndex = self.index.shape[0] - 1  # 当前存在几次triggerID置零

    def setStartTime(self,t = None):
        if not self.parent.readMode:
            self.dataGroup.attrs["start time"] = time.time() if t is None else t

    def setStopTime(self, t = None):
        if not self.parent.readMode:
            self.dataGroup.attrs["stop time"] = time.time() if t is None else t

    def startTime(self):
        return self.dataGroup.attrs["start time"]

    def stopTime(self):
        return self.dataGroup.attrs["stop time"]

    def totalTime(self):
        return self.dataGroup.attrs["stop time"] - self.dataGroup.attrs["start time"]

    # 录入设备状态信息
    def putDeviceStatus(self, status: dict):
        '''
        "w": write device configuration state to h5 file
        "r": raise Exception
        :param status:dict:key:boardID;value:tuple(threshold, biasVoltage, triggerMode)
        :return:
        '''
        print(status)
        triggerMode = status[0][2]
        self.statusInfo[0] = triggerMode
        for i in range(8):
            t = status.get(i, (0, 0, 0))
            self.statusInfo[i + 1] = t[0]
            self.statusInfo[i + 9] = t[1]

    # 获取h5文件中存储的设备状态信息
    def getDeviceStatus(self) -> dict:
        '''
        :return: dict:key:boardID;value:tuple(threshold, bias voltage, trigger mode)
        '''
        status = {}
        triggerMode = self.statusInfo[0]
        for i in range(8):
            threshold = self.statusInfo[i + 1]
            biasVoltage = self.statusInfo[i + 9]
            if threshold == 0 and biasVoltage == 0:
                break
            else:
                status[i] = (threshold, biasVoltage, triggerMode)
        return status

    # ===============数据=================
    # 将数据添加到h5数据集中
    def addToDataSet(self, value: np.array, timeTag=None):
        '''
        "w": add data to h5 file
        "r": raise Exception
        :param value: data,type:np.array,dtype:'uint16',shape:(n,39)
                    column 0-38 will be pushed into group(data), column 39 will be pushed into group(timeTag)
        :param NewSets: if it set as True,h5 file will create a new data set to contain data
        :return:
        '''
        # 如果数据集的长度不够，则扩展5000行
        if self.dataIndex + value.shape[0] <= self.data.shape[0]:
            self.data.resize(self.data.shape[0] + 5000, axis=0)
            self.timeTag.resize(self.data.shape[0] + 5000, axis=0)
        # 数据存储
        self.data.write_direct(value, source_sel=np.s_[0:value.shape[0]],
                               dest_sel=np.s_[self.dataIndex:value.shape[0] + self.dataIndex])
        if timeTag is not None:
            self.timeTag.write_direct(timeTag, source_sel=np.s_[0:value.shape[0]],
                                      dest_sel=np.s_[self.dataIndex:value.shape[0] + self.dataIndex])
        self.dataIndex += value.shape[0]
        self.index[0] = self.dataIndex


        # 表示triggerID重置，添加重置处索引并添加分片时间

    # 读取h5文件中的数据
    def getData(self, index: int = -1, startIndex: int = 0, dtype='int64') -> pd.DataFrame:
        '''
        read data in h5 file
        :param index: When the index greater than or equal to 0, the corresponding set of data will be returned.
        when the index equal to -1,all the data will be returned.
        when the index equal to -2,all the data will be returned and the triggerID in returned data has been accumulated.
        :param startIndex: data will be returned from the startIndex
        :return:
        '''
        if index + 1 > self.index.shape[0] or index < -2:
            raise ValueError('index({}) out of range (-2-{})'.format(index, self.index.shape[0] - 1))
        if startIndex > self.index[0]:
            raise ValueError('startIndex({}) out of range (0-{})'.format(startIndex, self.index[0]))
        # ========特殊索引========
        if index == -1:
            set = self.data[startIndex:self.index[0]]
            timetage = self.timeTag[startIndex:self.index[0]].reshape((-1, 1))
            # 合并能量信息和时间信息-shape——>(-1,40)
            set = np.append(set, timetage, axis=1)
            # print("getData:{}".format(set))
            _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
            return _d
        elif index == -2:
            _d = pd.DataFrame(columns=_Index, dtype=dtype)
            for i in range(self.index.shape[0]):
                _s = self.getData(i, startIndex=startIndex)
                _s['triggerID'] = _s['triggerID'] + i * 65535
                _d = _d.append(_s, ignore_index=True)
            return _d
        # ========普通索引========
        if index == 0:  # 选择第一个数据集时
            if self.index.shape[0] == 1:
                stop = self.index[0]
            else:
                stop = self.index[1]
            if startIndex >= stop:
                _d = pd.DataFrame(columns=_Index, dtype=dtype)
            else:
                set = np.empty((stop - startIndex, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - startIndex,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
        elif index + 1 == self.index.shape[0]:  # 选择最后一个数据集时
            stop = self.index[0]
            start = self.index[index]
            if startIndex >= stop:
                _d = pd.DataFrame(columns=_Index, dtype=dtype)
            elif startIndex < start:
                set = np.empty((stop - start, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - start,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
            else:
                set = np.empty((stop - startIndex, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - startIndex,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
        else:  # 选择中间数据集时
            # 当判断到此时，index比self.index.shape[0]至少小2，比最大索引小1，index+1不会超出边界
            start = self.index[index]
            stop = self.index[index + 1]
            if startIndex >= stop:
                _d = pd.DataFrame(columns=_Index, dtype=dtype)
            elif startIndex < start:
                set = np.empty((stop - start, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - start,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[start:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
            else:
                set = np.empty((stop - startIndex, 39), dtype='uint16')
                self.data.read_direct(set, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetag = np.empty((stop - startIndex,), dtype='int64')
                self.timeTag.read_direct(timetag, source_sel=np.s_[startIndex:stop], dest_sel=np.s_[0:set.shape[0]])
                timetage = timetag.reshape((-1, 1))
                # 合并能量信息和时间信息-shape——>(-1,40)
                set = np.append(set, timetage, axis=1)
                _d = pd.DataFrame(set, columns=_Index, dtype=dtype)
        return _d

    def newSets(self):
        '''
        set reset triggerID in index
        '''
        self.setsIndex += 1
        self.index.resize(self.index.shape[0] + 1, axis=0)
        # 添加分片时间
        self.index[self.setsIndex] = self.dataIndex

    def refreshIndex(self,indexList:list):
        if self.index.shape[0] - 1 < len(indexList):
            lNum = len(indexList)
            for i in range(len(indexList)):
                if self.dataIndex < indexList[i]:
                    lNum = i
            self.index.resize(lNum+1, axis = 0)
            self.index[1:lNum+1] =  np.array(indexList[:lNum])

    def __del__(self):
        if self.parent.file:
            if not self.parent.readMode:
                print('h5 index:',self.dataIndex)
                self.data.resize(self.dataIndex, axis=0)







