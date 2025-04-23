from dataLayer.baseCore import h5Data
import time


data = h5Data("./tmpData9.h5", "r")
d = data.getData(0)
print("timeTag:",d.timeTag)
import matplotlib.pyplot as plt
plt.plot(d.timeTag)
plt.show()

detectorType = data.getDetectorType()

if detectorType == 1:
    print("zaizai")
    p = data.getPosture()
    if not p == 0:
        print("data:",p)
else:
    print("zaizai")
data.close()
print("\n\n\n===========================")
