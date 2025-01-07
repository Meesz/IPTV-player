import sys
from PyQt6.QtWidgets import QApplication
from views.main_window import MainWindow
from controllers.player_controller import PlayerController

def main():
    app = QApplication(sys.argv)
    
    # Create main window and controller
    main_window = MainWindow()
    controller = PlayerController(main_window)
    
    # Show the main window
    main_window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 