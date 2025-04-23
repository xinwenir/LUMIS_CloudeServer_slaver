import os,sys
with open("./requirement.txt") as file:
    l = file.readline().strip()
    while l:
        print(l)
        if sys.platform == "win32":
            os.system("pip install {}".format(l))
        elif sys.platform == "linux2" or sys.platform == "linux":
            os.system("pip3 install {}".format(l))
        l = file.readline().strip()