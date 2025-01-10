from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor

class LoadingSpinner(QWidget):
    """
    A widget that displays a loading spinner animation.
    
    Attributes:
        size (int): The size of the spinner.
        num_dots (int): The number of dots in the spinner.
        color (QColor): The color of the dots.
        rotation (float): The current rotation angle of the spinner.
        timer (QTimer): The timer controlling the animation.
    """
    def __init__(self, parent=None, size=64, num_dots=8, color=QColor(255, 255, 255)):
        """
        Initializes the LoadingSpinner with the given parameters.
        
        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            size (int, optional): The size of the spinner. Defaults to 64.
            num_dots (int, optional): The number of dots in the spinner. Defaults to 8.
            color (QColor, optional): The color of the dots. Defaults to white.
        """
        super().__init__(parent)
        
        # Set size
        self.setFixedSize(size, size)
        self.size = size
        
        # Spinner properties
        self.num_dots = num_dots
        self.color = color
        self.rotation = 0
        
        # Animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        
        # Make background transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    
    def start(self):
        """Starts the spinner animation."""
        self.show()
        self.timer.start(50)  # 20 FPS
    
    def stop(self):
        """Stops the spinner animation."""
        self.timer.stop()
        self.hide()
    
    def rotate(self):
        """Updates the rotation angle and repaints the spinner."""
        self.rotation += 360 / self.num_dots
        self.update()
    
    def paintEvent(self, event):
        """
        Handles the paint event to draw the spinner.
        
        Args:
            event (QPaintEvent): The paint event.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate sizes
        center = self.size / 2
        dot_size = self.size / 10
        radius = (self.size - dot_size) / 3
        
        # Draw dots
        for i in range(self.num_dots):
            # Calculate opacity based on position
            opacity = (i + 1) / self.num_dots
            
            # Set color with opacity
            color = QColor(self.color)
            color.setAlphaF(opacity)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            
            # Calculate position
            angle = (360 / self.num_dots * i + self.rotation) * 3.14159 / 180
            x = center + radius * -1 * (angle - 3.14159)
            y = center + radius * (angle + 3.14159 / 2)
            
            # Draw dot
            rect = QRectF(x - dot_size/2, y - dot_size/2, dot_size, dot_size)
            painter.drawEllipse(rect) 