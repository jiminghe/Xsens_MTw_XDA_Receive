"""
UI definition for MainWindow
Converted from mainwindow.ui
"""

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(824, 348)
        MainWindow.setMinimumSize(QtCore.QSize(824, 348))
        MainWindow.setMaximumSize(QtCore.QSize(824, 348))
        
        self.centralWidget = QtWidgets.QWidget(MainWindow)
        self.centralWidget.setObjectName("centralWidget")
        
        # Station Properties Group Box
        self.stationPropertiesGroupBox = QtWidgets.QGroupBox(self.centralWidget)
        self.stationPropertiesGroupBox.setGeometry(QtCore.QRect(10, 10, 151, 331))
        self.stationPropertiesGroupBox.setTitle("Wireless master properties:")
        
        self.stationIdCaptionLabel = QtWidgets.QLabel(self.stationPropertiesGroupBox)
        self.stationIdCaptionLabel.setGeometry(QtCore.QRect(10, 20, 46, 13))
        self.stationIdCaptionLabel.setText("ID:")
        
        self.stationIdLabel = QtWidgets.QLabel(self.stationPropertiesGroupBox)
        self.stationIdLabel.setGeometry(QtCore.QRect(30, 20, 61, 16))
        self.stationIdLabel.setText("-")
        
        self.channelCaptionLabel = QtWidgets.QLabel(self.stationPropertiesGroupBox)
        self.channelCaptionLabel.setGeometry(QtCore.QRect(10, 50, 46, 13))
        self.channelCaptionLabel.setText("Channel:")
        self.channelCaptionLabel.setEnabled(False)
        
        self.channelComboBox = QtWidgets.QComboBox(self.stationPropertiesGroupBox)
        self.channelComboBox.setGeometry(QtCore.QRect(90, 41, 51, 31))
        self.channelComboBox.setEnabled(False)
        for i in range(11, 26):
            self.channelComboBox.addItem(str(i))
        
        self.enableButton = QtWidgets.QPushButton(self.stationPropertiesGroupBox)
        self.enableButton.setGeometry(QtCore.QRect(10, 80, 131, 31))
        self.enableButton.setText("Enable")
        self.enableButton.setEnabled(False)
        
        self.updateRateCaptionLabel = QtWidgets.QLabel(self.stationPropertiesGroupBox)
        self.updateRateCaptionLabel.setGeometry(QtCore.QRect(10, 120, 61, 20))
        self.updateRateCaptionLabel.setText("Update rate:")
        self.updateRateCaptionLabel.setEnabled(False)
        
        self.allowedUpdateRatesComboBox = QtWidgets.QComboBox(self.stationPropertiesGroupBox)
        self.allowedUpdateRatesComboBox.setGeometry(QtCore.QRect(80, 120, 61, 22))
        self.allowedUpdateRatesComboBox.setEnabled(False)
        
        self.startMeasurementButton = QtWidgets.QPushButton(self.stationPropertiesGroupBox)
        self.startMeasurementButton.setGeometry(QtCore.QRect(10, 150, 131, 31))
        self.startMeasurementButton.setText("Start Measurement")
        self.startMeasurementButton.setEnabled(False)
        
        self.resetHeadingButton = QtWidgets.QPushButton(self.stationPropertiesGroupBox)
        self.resetHeadingButton.setGeometry(QtCore.QRect(10, 185, 131, 31)) 
        self.resetHeadingButton.setText("Reset Heading")
        self.resetHeadingButton.setEnabled(False)
        
        self.recordingButton = QtWidgets.QPushButton(self.stationPropertiesGroupBox)
        self.recordingButton.setGeometry(QtCore.QRect(10, 220, 131, 31))  # Moved down to make room
        self.recordingButton.setText("Start recording")
        self.recordingButton.setEnabled(False)
        
        self.flushingCaptionLabel = QtWidgets.QLabel(self.stationPropertiesGroupBox)
        self.flushingCaptionLabel.setGeometry(QtCore.QRect(10, 260, 46, 20))  # Moved down
        self.flushingCaptionLabel.setText("Flushing:")
        self.flushingCaptionLabel.setEnabled(False)
        
        self.flushingProgressBar = QtWidgets.QProgressBar(self.stationPropertiesGroupBox)
        self.flushingProgressBar.setGeometry(QtCore.QRect(60, 260, 81, 23))  # Moved down
        self.flushingProgressBar.setValue(0)
        self.flushingProgressBar.setEnabled(False)
        
        # Docked MTw List Group Box
        self.dockedMtwListGroupBox = QtWidgets.QGroupBox(self.centralWidget)
        self.dockedMtwListGroupBox.setGeometry(QtCore.QRect(170, 10, 151, 141))
        self.dockedMtwListGroupBox.setTitle("Docked MTw list (0):")
        
        self.dockedMtwList = QtWidgets.QListWidget(self.dockedMtwListGroupBox)
        self.dockedMtwList.setGeometry(QtCore.QRect(10, 20, 131, 111))
        self.dockedMtwList.setSortingEnabled(True)
        
        # Connected MTw List Group Box
        self.connectedMtwListGroupBox = QtWidgets.QGroupBox(self.centralWidget)
        self.connectedMtwListGroupBox.setGeometry(QtCore.QRect(170, 170, 151, 171))
        self.connectedMtwListGroupBox.setTitle("Connected MTw list (0):")
        
        self.connectedMtwList = QtWidgets.QListWidget(self.connectedMtwListGroupBox)
        self.connectedMtwList.setGeometry(QtCore.QRect(10, 20, 131, 111))
        self.connectedMtwList.setSortingEnabled(True)
        
        self.pitchToSelectCheckBox = QtWidgets.QCheckBox(self.connectedMtwListGroupBox)
        self.pitchToSelectCheckBox.setGeometry(QtCore.QRect(10, 140, 101, 20))
        self.pitchToSelectCheckBox.setText("Pitch to select")
        
        # Logging Group Box
        self.loggingGroupBox = QtWidgets.QGroupBox(self.centralWidget)
        self.loggingGroupBox.setGeometry(QtCore.QRect(330, 10, 341, 141))
        self.loggingGroupBox.setTitle("What's going on:")
        
        self.logWindow = QtWidgets.QTextBrowser(self.loggingGroupBox)
        self.logWindow.setGeometry(QtCore.QRect(10, 20, 321, 101))
        
        self.clearLogPushButton = QtWidgets.QPushButton(self.loggingGroupBox)
        self.clearLogPushButton.setGeometry(QtCore.QRect(10, 125, 321, 10))
        self.clearLogPushButton.setText("")
        
        # MTw Properties Group Box
        self.mtwPropertiesGroupBox = QtWidgets.QGroupBox(self.centralWidget)
        self.mtwPropertiesGroupBox.setGeometry(QtCore.QRect(330, 170, 161, 171))
        self.mtwPropertiesGroupBox.setTitle("Selected MTw properties:")
        
        self.batteryLevelCaptionLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.batteryLevelCaptionLabel.setGeometry(QtCore.QRect(20, 30, 71, 16))
        self.batteryLevelCaptionLabel.setText("Battery level:")
        
        self.batteryLevelLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.batteryLevelLabel.setGeometry(QtCore.QRect(100, 30, 50, 16))
        self.batteryLevelLabel.setText("-")
        self.batteryLevelLabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        self.rssiCaptionLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.rssiCaptionLabel.setGeometry(QtCore.QRect(20, 54, 46, 16))
        self.rssiCaptionLabel.setText("RSSI:")
        
        self.rssiLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.rssiLabel.setGeometry(QtCore.QRect(100, 54, 50, 13))
        self.rssiLabel.setText("-")
        self.rssiLabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        self.effUpdateRateCaptionLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.effUpdateRateCaptionLabel.setGeometry(QtCore.QRect(20, 78, 91, 16))
        self.effUpdateRateCaptionLabel.setText("Eff. update rate:")
        
        self.effUpdateRateLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.effUpdateRateLabel.setGeometry(QtCore.QRect(100, 78, 50, 16))
        self.effUpdateRateLabel.setText("-")
        self.effUpdateRateLabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        self.rollCaptionLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.rollCaptionLabel.setGeometry(QtCore.QRect(20, 102, 46, 16))
        self.rollCaptionLabel.setText("Roll:")
        
        self.rollLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.rollLabel.setGeometry(QtCore.QRect(79, 102, 71, 20))
        self.rollLabel.setText("-")
        self.rollLabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        self.pitchCaptionLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.pitchCaptionLabel.setGeometry(QtCore.QRect(20, 126, 46, 16))
        self.pitchCaptionLabel.setText("Pitch:")
        
        self.pitchLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.pitchLabel.setGeometry(QtCore.QRect(79, 126, 71, 20))
        self.pitchLabel.setText("-")
        self.pitchLabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        self.yawCaptionLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.yawCaptionLabel.setGeometry(QtCore.QRect(20, 150, 46, 16))
        self.yawCaptionLabel.setText("Yaw:")
        
        self.yawLabel = QtWidgets.QLabel(self.mtwPropertiesGroupBox)
        self.yawLabel.setGeometry(QtCore.QRect(79, 150, 71, 20))
        self.yawLabel.setText("-")
        self.yawLabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        # State Diagram Group Box
        self.stateMachineImageGroupBox = QtWidgets.QGroupBox(self.centralWidget)
        self.stateMachineImageGroupBox.setGeometry(QtCore.QRect(500, 170, 311, 171))
        self.stateMachineImageGroupBox.setTitle("State diagram:")
        
        self.stateDiagramLabel = QtWidgets.QLabel(self.stateMachineImageGroupBox)
        self.stateDiagramLabel.setGeometry(QtCore.QRect(10, 20, 291, 141))
        self.stateDiagramLabel.setText("<State diagram>")
        self.stateDiagramLabel.setAlignment(QtCore.Qt.AlignCenter)
        
        # Logo Label
        self.logoLabel = QtWidgets.QLabel(self.centralWidget)
        self.logoLabel.setGeometry(QtCore.QRect(680, 20, 131, 131))
        self.logoLabel.setText("")
        self.logoLabel.setScaledContents(True)
        
        MainWindow.setCentralWidget(self.centralWidget)
        
        QtCore.QMetaObject.connectSlotsByName(MainWindow)