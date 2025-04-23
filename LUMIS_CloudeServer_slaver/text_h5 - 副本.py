from dataLayer.baseCore import h5Data
import time


# data = h5Data("./data/testData.h5", "r")
# d = data.getData(0)
# p = data.getPosture()
# print(p)
# data.close()
# print("\n\n\n===========================")
from math import log
from dataLayer.connectionTools import PostureDecode
with open("binaryFile","br") as file:
    data = file.read()
tail = 0
for i in range(100):
    head = data.index(b'\xfa\x5a', tail)
    tail = data.index(b'\xfe\xee\xfe\xee', head)
    nHead = data.index(b'\xfa\x5a', tail)
    idx = 0
    boardID = int(log(int.from_bytes(data[tail+11:tail+12],byteorder="big",signed=False),2))
    print("\n===========================[{},length:{}]=========================".format(boardID,tail-head))
    print("\n--------------data part--------------")
    for i in range(head,tail+4):
        print(int.to_bytes(data[i],1,byteorder="big",signed=False).hex(),end="\t")
        if idx == 16:
            print('')
            idx = 0
        else:
            idx += 1

    print("\n------------status part-------------")
    idx = 0
    for i in range(tail + 4, tail + 12):
        print(int.to_bytes(data[i], 1, byteorder="big", signed=False).hex(), end="\t")
        if idx == 16:
            print('')
            idx = 0
        else:
            idx += 1

    if data[tail+12 + 14:tail+12+16] == b'\xaa\x55':
        print("\n---------posture part-----------")
        idx = 0
        for i in range(tail + 12, tail + 12+25):
            print(int.to_bytes(data[i], 1, byteorder="big", signed=False).hex(), end="\t")
            if idx == 16:
                print('')
                idx = 0
            else:
                idx += 1

        print("陀螺仪x方向角速度:{},<{}>".format(PostureDecode.gyroAngularVelocity(data[tail+12+8:tail+12+10]),data[tail+12+8:tail+12+10].hex()))



