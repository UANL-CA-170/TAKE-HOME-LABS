#!/usr/bin/env python

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import datetime
import os
import sys
from threading import Thread
import serial
import time
import collections
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import struct
import copy
import pandas as pd

# To clean screen
def clear(): 
    if os.name == "posix":
        os.system("clear")
    elif os.name in ("ce", "nt", "dos"):
        os.system("cls")

# To store data in config.ini
def loadconfig():
    folder = os.getcwd()
    ruta_config = folder + "/config/config.ini"
    isFile = os.path.isfile(ruta_config)
    if isFile:
        print('Reading serial port configuration from file:' + ruta_config)
        df = pd.read_csv(ruta_config, sep=':', header=None)
        data = df.get(1)
        Port = data.get(0).strip().strip("'\"")
        Baudrate = int(data.get(1))
        Samples = int(data.get(2))
        Sampling = int(data.get(3))
        Min_amp = int(data.get(4))
        Max_amp = int(data.get(5))
    else:
        print('The configuration of the serial port can not be found.')
        print('Please introduce serial port configuration.')
        if sys.platform in ("linux", "linux2"):
            Port = input("Name of the port, for example '/dev/ttyACM0' -> ")
        elif sys.platform == "darwin":
            Port = input("Name of the port, for example '/dev/tty.usb' -> ")
        elif sys.platform == "win32":
            Port = input("Name of the port, for example COM5 -> ")
        else:
            raise Exception("Error, the OS can not be determined.")
        Baudrate = int(input("Baudrate? -> "))
        Samples = int(input("Samples per plot in the x-axis? -> "))
        Sampling = int(input("Sampling time in mseg -> "))
        Min_amp = int(input("Minimum value of the y-axis -> "))
        Max_amp = int(input("Maximum value for the y-axis -> "))
        i = 0
        while i < 3:
            RecData = int(input("Do you want to save config for next connections (1 - Si / 0 - No) -> "))
            if RecData == 1:
                print("The file config.ini has now the config, it was stored in the folder config/")
                time.sleep(3)
                try:
                    os.stat(os.getcwd() + '/config')
                except:
                    os.mkdir(os.getcwd() + '/config')
                    print('Creating directory /config...')
                    time.sleep(3)
                data_new = {'0': ['Port', 'Baudrate', 'Samples', 'Sampling_ms', 'Min_Value_Plot', 'Max_Value_Plot'],
                            '1': [Port, Baudrate, Samples, Sampling, Min_amp, Max_amp]}
                df = pd.DataFrame(data=data_new)
                print('Saving data in config.ini...')
                df.to_csv(ruta_config, sep=':', index=False, header=False)
                time.sleep(3)
                print('Config data has been stored in config/config.ini.')
                time.sleep(3)
                break
            elif RecData == 0:
                print("Config data can not be stored in config.ini file")
                time.sleep(3)
                break
            else:
                i += 1
                if i < 3:
                    print('Type 1 / 0 only, please type again ')
                else:
                    sys.exit("Error, type 1/0 only.")
    time.sleep(3)
    return Port, Baudrate, Samples, Sampling, Min_amp, Max_amp

# Serial port
class serialPlot:
    def __init__(self, serialPort='/dev/ttyACM0', serialBaud=9600, plotLength=100, dataNumBytes=2, numPlots=1):
        self.port = serialPort
        self.baud = serialBaud
        self.plotMaxLength = plotLength
        self.dataNumBytes = dataNumBytes
        self.numPlots = numPlots
        self.rawData = bytearray(numPlots * dataNumBytes)
        self.dataType = None
        if dataNumBytes == 2:
            self.dataType = 'h'
        elif dataNumBytes == 4:
            self.dataType = 'f'
        self.data = [collections.deque([0] * plotLength, maxlen=plotLength) for _ in range(numPlots)]
        self.isRun = True
        self.isReceiving = False
        self.thread = None
        self.plotTimer = 0
        self.previousTimer = 0
        self.csvData = []

        print('Reaching ' + str(serialPort) + ' a ' + str(serialBaud) + ' BAUD.')
        try:
            self.serialConnection = serial.Serial(serialPort, serialBaud, timeout=4)
            print(f'✅ Connected with {serialPort} at {serialBaud} BAUD.')
        except serial.SerialException as e:
            print(f"❌ Connection failed with {serialPort} at {serialBaud} BAUD.\nError: {e}")
            self.serialConnection = None

    def readSerialStart(self):
        if self.serialConnection is None:
            print("Serial connection not established. Cannot start reading.")
            return
        if self.thread is None:
            self.thread = Thread(target=self.backgroundThread)
            self.thread.start()
            while not self.isReceiving:
                time.sleep(0.1)

    def close(self, RecData):
        self.isRun = False
        self.thread.join()
        self.serialConnection.close()
        print('Disconnecting...')
        time.sleep(3)
        if RecData == 1:
            print('Storing monitor data in file csv...')
            time.sleep(3)
            folder = os.getcwd()
            folder_datos = folder + "/datos"
            try:
                os.stat(folder_datos)
            except:
                os.mkdir(folder_datos)
                print('Creating directory /datos...:' + folder_datos)
                time.sleep(3)
            x = datetime.datetime.now()
            fecha_hora = x.isoformat()
            fecha_hora = fecha_hora.replace(':', '', 2).replace('.', '', 2).replace('-', '', 2)[2:15]
            df = pd.DataFrame(self.csvData, columns=['Time in sec', 'Reference', 'Output', 'Control'])
            df.to_csv(folder_datos + '/datos-' + fecha_hora + ".csv")
            print('Data monitor has been saved in file ' + folder_datos + '/datos-' + fecha_hora + ".csv")
            time.sleep(3)
        print('Closing...')
        time.sleep(3)

    def backgroundThread(self):
        if self.serialConnection is None:
            print("Serial connection not established. Exiting background thread.")
            return
        time.sleep(1.0)
        self.serialConnection.reset_input_buffer()
        while self.isRun:
            self.serialConnection.readinto(self.rawData)
            self.isReceiving = True

    def getSerialData(self, frame, lines, lineValueText, lineLabel, timeText, RecData):
        currentTimer = time.perf_counter() if sys.version[0] != '2' else time.clock()
        self.plotTimer = int((currentTimer - self.previousTimer) * 1000)
        self.previousTimer = currentTimer
        timeText.set_text('Sampling time = ' + str(self.plotTimer) + 'ms')
        privateData = copy.deepcopy(self.rawData[:])
        for i in range(self.numPlots):
            data = privateData[(i*self.dataNumBytes):(self.dataNumBytes + i*self.dataNumBytes)]
            value, = struct.unpack(self.dataType, data)
            self.data[i].append(value)
            lines[i].set_data(range(self.plotMaxLength), self.data[i])
            lineValueText[i].set_text('[' + lineLabel[i] + '] = ' + str(value))
        if RecData == 1:
            self.csvData.append([currentTimer, self.data[0][-1], self.data[1][-1], self.data[2][-1]])

def main():
    clear()
    print("--------------------------------------------------------------")
    print("|                                                            |")
    print("| Serial port monitor.                                       |")
    print("| v1.01, November 13, 2022.                                  |")
    print("| Departamento de Electronica y Automatizacion, FIME-UANL.   |")
    print("|                                                            |")
    print("--------------------------------------------------------------")
    print("Please introduce the following parameters:" )
    i = 0
    while i < 3:
        RecData = int(input("Do you want to store data (1 - yes / 0 - no) -> "))
        if RecData == 1:
            print("Data will be stored.")
            break
        elif RecData == 0:
            print("Data will not be stored.")
            break
        else:
            i += 1
            if i < 3:
                print('Please type only 1 / 0, please type again ')
            else:
                sys.exit("Error, please type 1 / 0 only.")

    # Port config
    portName, baudRate, maxPlotLength, pltInterval, ymin, ymax = loadconfig()

    # Monitor
    dataNumBytes = 4
    numPlots = 3
    xmin = 0
    xmax = maxPlotLength

    s = serialPlot(portName, baudRate, maxPlotLength, dataNumBytes, numPlots)
    s.readSerialStart()

    print("Connected, please close the figure to end the session...")

    fig = plt.figure(figsize=(10, 10))
    ax = plt.axes(xlim=(xmin, xmax),
                  ylim=(float(ymin - (ymax - ymin) / 10), float(ymax + (ymax - ymin) / 10)))
    ax.set_title('Serial port monitor')
    ax.set_xlabel("Sampling time " + str(pltInterval) + " mseg.")
    ax.set_ylabel("Magnitude")
    lineLabel = ['Reference', 'Output', 'Control']
    style = ['r', 'k-', 'b:']
    timeText = ax.text(0.63, 0.95, '', transform=ax.transAxes)
    lines = []
    lineValueText = []
    for i in range(numPlots):
        lines.append(ax.plot([], [], style[i], label=lineLabel[i])[0])
        lineValueText.append(ax.text(0.63, 0.90 - i*0.05, '', transform=ax.transAxes))
    anim = animation.FuncAnimation(fig, s.getSerialData,
                                   fargs=(lines, lineValueText, lineLabel, timeText, RecData),
                                   interval=pltInterval)
    plt.legend(loc="upper left")
    plt.grid()
    plt.show()

    s.close(RecData)


if __name__ == '__main__':
    main()
