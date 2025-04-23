'''
包含一些通用的参数
'''
# -----------数据索引-----------
_Index = []
# 0-35
for i in range(36):
    _Index.append('chn_{:2>d}'.format(i))
_Index.append('temperature')    # 36
_Index.append('triggerID')      # 37
_Index.append('boardID')        # 38
_Index.append("timeTag")        # 39

# -----------指示数据大小的枚举-------
from enum import Enum
class sizeUnit_binary(Enum):
    B = 1
    KB = 1024
    MB = 1024 * 1024

# ---------共享数据地址---------
_address = ("tcp://4jp6196986.wicp.vip", 38154)

# ---------版本信息------------
__version__ = "1.0.1"


