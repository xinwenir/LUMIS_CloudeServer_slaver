## h5Data version = 0.2

LUMISData -- 兼容version 0.1 的数据

​	LUMISDevData -- 一个设备的数据



version = 0.2的h5文件格式

```
=========FORMAT OF H5 FILE version: 0.2========
root
 ├info(group)
 │ ├project(attribute)
 │ └version(attribute)
 └(device name)(group)
 	├start time(attribute)
 	├stop time(attribute)
    ├data(dataSet)
    │ └data
    ├timeTag(dataSet)
    │ └timeTag
    ├index(dataSet)
    │ └index
    └device_status(dataset)
      ├trigger mode
      ├board 0 threshold
      ├~~~~~~~
      ├board 7 threshold
      ├board 0 bias voltage
      ├~~~~~
      └board 7 bias voltage
```







## LUMIS project

存储一系列slaver，同时指向当前h5文件的数据，存在一个h5Data对象(version = 0.2)存储数据，不能存在同名slaver

## LUMIS slaver

### 功能：

1. 状态：
   - 设备信息：设备名，所属项目，序列号
2. 数据：
   - 数据对象（h5.dataset）
3. 心跳：
   1. 是否在采集
   2. 采集到的事件数

#### 指令方案：

##### 1.注册设备：

slaver端连接server时，server将根据slaver发送的信息在内存空间注册一个设备

###### slaver -- server

> {
>     "devType": 0, /连接的设备类型，0为设备端（slaver端），1为用户端（client端）
>     *"reconnect": bool,
>     /是否为重连，若无此key，则默认为False
>     "devInfo": {
>                 "name": str(name),
>
> ​                "project": str(project),
>
> ​                "serialNumber": str(project),
>
> ​				*"status_measure": bool
>
> ​                }
> ​    /设备信息
> ​    /调用函数getSlaver()将根据重连标识和设备信息返回LUMISslaver对象，若设备已经开始采集时，将会向设备请求数据
> ​    /=====若不为重连=====
> ​    /则根据设备信息在对应key下的list中创建一个新的LUMISslaver对象
> ​    /此时建立连接成功
> ​    /=====若为重连=====
> ​    /则根据设备信息寻找设备是否还在内存中，若在则返回内存中的对象，若不在则创建一个新的LUMISslaver对象
>
> ​    /建立连接成功
> }

###### server -- slaver 返回值

**若不为重连**

> {
>
> ​	"return":True
>
> }

**若为重连或设备已经在采集**

> {
>
> ​	"return":True,
>
> ​	"order": {
>
> ​					"askForData": int(lineIndex)	/返回当前已经接收到的event数据，将从slaver请求余下数据
>
> ​					}
>
> }

slaver --server

> {
>
> ​	"return":True,
>
> ​	"data": list 2D
>
> }

server -- slaver

> {
>
> ​	"return":True
>
> }

#### 2.心跳

slaver每隔1s就会向server发送一次心跳数据，用于以下用途：

- 确保双方保持连接
- 返回当前设备状态（是否在测量）
- 采集过程中返回数据
- server在发送对slaver的心跳返回值时，可能会返回操作指令，来指令slaver开启/结束采集

若长时间（30s~60s）未收到slaver的心跳数据，则认为slaver断开连接

slaver -- server

> {
>
> ​	"heartRate": True,
>
> ​	"status_measure": bool, /若status_measure为true则会存在data关键字
>
> ​	*"data": list 2D
>
> }

server -- slaver

> {
>
> ​	"return":True,
>
> ​	*"order":{ 
>
> ​					"measure":true/false
>
> ​					 }
>
> }

目前order只有开始/结束测量，配置文件为默认配置文件，存储在slaver设备上，成功开启后，slaver返回如下

> {
>
> ​	"return":True
>
> }

## LUMIS client：

#### 功能：

1. 获取当前项目在线的slaver
2. 获取指定slaver处理后的数据结果


## 20220418更新日志：

1. 在slaver中：数据在数据分片时自动分片保存副本
    * 由于在同线程时功能函数耗时过高，因此拉起一个新的线程去执行目标函数
2. 在server中:
    * 线程可以在数据库的命令库中搜索，然后获取用户的指令队列，并对目标设备发送指令

以上内容均需测试验证其功能性与稳定性


## 功能性需求：
网页服务，网页提交表单服务：基于`plotly`的前端后端一体服务

## 20220427更新日志：
1. 在slaver中修改了serialNumber的获取方式，转变为CPUID，无需手动更改
2. 由于修改了serialNumber，数据库中的serialNUmber需要改成varchar
