from multiprocessing import Queue, Event, SimpleQueue
import time

_binaryBuff = SimpleQueue()


def loadBinaryData(source: bytes) -> bytes:
    '''
    将二进制数据根据SSP2E包切分后放入缓存队列中
    #对于大井眼数据，需要额外寻找是否包含姿态信息
    :param source: raw binary data
    :return: remained data
    '''
    tail = 0
    try:
        head = source.index(b'\xfa\x5a', tail)
        print("head:", head)
        tail = source.index(b'\xfe\xee\xfe\xee',head)
        print("tail:", tail)
    except:
        return source[tail+12:]
    if len(source) < tail + 12:
        return source[head:]
    buff = source[head:tail+12]
    print(buff)
    _binaryBuff.put(buff)



if __name__ == '__main__':
    tmpB = b'\xfa\x5a\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\x30\x00\xfe\xee\xfe\xee\xaa\xaa\xaa\xaa\00\00\00\00\00\00\00\00\00\00\00\00\00'
    while True:
        loadBinaryData(tmpB)
        TEX = _binaryBuff.get()
        print(TEX)
        time.sleep(5)

       