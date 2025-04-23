import os,sys
#获取主板序列号
if sys.platform == "win32":
    respond = os.popen('wmic bios get serialnumber').read()
    respond = respond.strip().replace('\n', '').replace('\r', '').split(" ")
    serialNumber = respond[len(respond)-1]
elif sys.platform == "linux2" or sys.platform == "linux":
    respond = os.popen('dmidecode -t 2 | grep Serial').read()
    serialNumber = respond.strip().split()[-1].replace('/','')

#预置配置指令
clockSynch = b'\xff\x03' #0.时钟同步
reset = b'\xff\x02'     #0.重置从板
turnOnPower = b'\xff\x04' #1.打开从板电源
turnOffPower = b'\xff\x05'  #1.关闭从板电源


#服务器地址(使用时才会调用，在使用前更改即可)
Host,Port = "192.168.1.108",9999#"4jp6196986.wicp.vip", 11355 #"192.168.1.108",9999
projectDev = {}

#在构建slave时调用，作为缺失值
projectName = "Test"
deviceName = "TestDevice00"

#清空命令行打印结果
def clearTerminal():
    if sys.platform == "win32":
        os.system('cls')
    elif sys.platform == "linux2" or sys.platform == "linux":
        os.system('clear')




