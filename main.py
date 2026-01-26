"""
Main entry point for Xsens Awinda GUI application
"""

import sys
import logging

from PyQt5.QtWidgets import QApplication, QMessageBox

from mainwindow import MainWindow


# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('xsens_debug.log'),
        logging.StreamHandler()
    ]
)


def main():
    """Main function"""
    app = QApplication(sys.argv)
    
    try:
        window = MainWindow()
        window.show()
        
        return app.exec_()
    
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Fatal Error")
        msg.setInformativeText(str(e))
        msg.setWindowTitle("Error")
        msg.exec_()
        
        return 1


if __name__ == '__main__':
    sys.exit(main())