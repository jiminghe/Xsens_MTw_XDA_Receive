"""
Main entry point for Xsens Awinda application
"""

import sys
import logging

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
    # Configuration
    desired_update_rate = 60  # Available: 40, 60, 80, 100, 120 Hz
    desired_radio_channel = 11  # Available: 11-25
    
    try:
        # Create and run main window
        main_window = MainWindow(
            desired_update_rate=desired_update_rate,
            desired_radio_channel=desired_radio_channel
        )
        
        main_window.run()
        
        logging.info("Successful exit.")
        print("Press [ENTER] to continue.")
        input()
        
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()