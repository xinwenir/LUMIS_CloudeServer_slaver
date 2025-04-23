# # from dataLayer.baseCore import h5Data
# # data = h5Data("data/tmpData2_0510_1h35min.h5")
# # print(data.getData(-2))
# # print(data.startTime())
# # print(data.stopTime())
# from devSlaver.slaver import slaver
# MySlaver = slaver()
# print("\033[34m server link: {}\033[0m".format(
#     ("\033[32m" if MySlaver.linkStatus.is_set() else "\033[31m") + str(MySlaver.linkStatus.is_set())))
# if MySlaver.linkStatus.is_set():
#     print("\033[34m final link time:\033[0m {}; \033[34mlast connect:{}\033[0m".format(
#         MySlaver.finalConnectTime,
#         ("\033[32m" if MySlaver.finalConnect.is_set() else "\033[31m") + str(MySlaver.finalConnect.is_set())))
# print("\033[34m measuring: {}\033[0m".format(
#     ("\033[32m" if MySlaver.measureStatus.is_set() else "\033[31m") + str(MySlaver.measureStatus.is_set())))
# checkModeList = ["\033[32m routine data","\033[33m baseline data","\033[36m all data"]
# print("\033[34m measure mode:{}\033[0m".format(checkModeList[MySlaver.decodeTool.getCheckMode()-1]))
# print("\033[34m configure file: \033[0m{}".format(MySlaver.configurePath))
# print("\033[34m data file: \033[0m{}".format(MySlaver.h5Path if MySlaver.h5Path is not None else "default path"))

print("load binary data -----", end='')
with open("data/2023_0215_2050(1).dat","br") as file:
    data = file.read()
print("succeed")
# tail = 0
# for i in range(10):
#     print("\n==========================={}=========================".format(i))
#     head = data.index(b'\xfa\x5a', tail)
#     tail = data.index(b'\xfe\xee\xfe\xee', head)
#     idx = 0
#     for i in range(head,tail+60):
#         print(int.to_bytes(data[i],1,byteorder="big",signed=False).hex(),end="\t")
#         if idx == 16:
#             print('')
#             idx = 0
#         else:
#             idx += 1

print(-1 & 3)
from dataLayer.baseCore import h5Data
from dataLayer.connectionTools import Lumis_Decode,dataDecode
import  time
from threading import Thread
dataFile = h5Data("./data/testData.h5","w",1)
dTool = Lumis_Decode()
dTool.setDetectorType(1)
dTool.enableDataBackup(False)
buff = data
total = len(data)
print("start decode")

thread = Thread(target=dataDecode,args=(dataFile, dTool))
thread.start()
t = time.time()
while(True):
    if(time.time() - t > 5):
        print("\rsplit: {} / {} ----- {:.2f}%".format(len(buff), total, ( 1 - len(buff) / total) * 100), end='')
        t = time.time()
        dataFile.flush()
    if(len(buff) > 2000):
        buff = dTool.loadBinaryData(buff[:2000]) + buff[2000:]
    else:
        dTool.loadBinaryData(buff)
        dTool.putStopOrder()





