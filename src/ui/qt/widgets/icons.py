"""
Vector Icon Painter Module
Renders crisp, resolution-independent vector icons for PySide6 components using QPainter and QPainterPath.
Eliminates all text/emoji fallback icon characters across the application.
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QPen, QBrush, QColor, QIcon, QPixmap

class VectorIconPainter:
    """Draws geometric vector paths for application icons."""
    
    @staticmethod
    def draw(painter: QPainter, name: str, rect: QRectF, color: QColor, pen_width: float = 1.8):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        pen = QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        cx, cy = rect.center().x(), rect.center().y()
        
        if name == "home" or name == "dashboard":
            path = QPainterPath()
            path.moveTo(x + w * 0.18, y + h * 0.48)
            path.lineTo(x + w * 0.5, y + h * 0.18)
            path.lineTo(x + w * 0.82, y + h * 0.48)
            path.lineTo(x + w * 0.82, y + h * 0.82)
            path.lineTo(x + w * 0.58, y + h * 0.82)
            path.lineTo(x + w * 0.58, y + h * 0.58)
            path.lineTo(x + w * 0.42, y + h * 0.58)
            path.lineTo(x + w * 0.42, y + h * 0.82)
            path.lineTo(x + w * 0.18, y + h * 0.82)
            path.closeSubpath()
            painter.drawPath(path)
            
        elif name == "play":
            path = QPainterPath()
            path.moveTo(x + w * 0.28, y + h * 0.18)
            path.lineTo(x + w * 0.82, y + h * 0.5)
            path.lineTo(x + w * 0.28, y + h * 0.82)
            path.closeSubpath()
            painter.setBrush(QBrush(color))
            painter.drawPath(path)
            
        elif name == "champions":
            path1 = QPainterPath()
            path1.moveTo(x + w * 0.2, y + h * 0.2)
            path1.lineTo(x + w * 0.8, y + h * 0.8)
            path2 = QPainterPath()
            path2.moveTo(x + w * 0.8, y + h * 0.2)
            path2.lineTo(x + w * 0.2, y + h * 0.8)
            painter.drawPath(path1)
            painter.drawPath(path2)
            painter.drawEllipse(QPointF(cx, cy), w * 0.15, h * 0.15)
            
        elif name == "friends":
            painter.drawEllipse(QPointF(cx - w * 0.12, cy - h * 0.18), w * 0.14, h * 0.14)
            path1 = QPainterPath()
            path1.moveTo(cx - w * 0.35, cy + h * 0.35)
            path1.cubicTo(cx - w * 0.35, cy + h * 0.05, cx + w * 0.1, cy + h * 0.05, cx + w * 0.1, cy + h * 0.35)
            painter.drawPath(path1)
            
            painter.drawEllipse(QPointF(cx + w * 0.2, cy - h * 0.12), w * 0.11, h * 0.11)
            path2 = QPainterPath()
            path2.moveTo(cx, cy + h * 0.35)
            path2.cubicTo(cx, cy + h * 0.12, cx + w * 0.4, cy + h * 0.12, cx + w * 0.4, cy + h * 0.35)
            painter.drawPath(path2)
            
        elif name == "coach":
            path = QPainterPath()
            path.moveTo(cx, y + h * 0.15)
            path.lineTo(cx + w * 0.1, cy - h * 0.1)
            path.lineTo(x + w * 0.85, cy)
            path.lineTo(cx + w * 0.1, cy + h * 0.1)
            path.lineTo(cx, y + h * 0.85)
            path.lineTo(cx - w * 0.1, cy + h * 0.1)
            path.lineTo(x + w * 0.15, cy)
            path.lineTo(cx - w * 0.1, cy - h * 0.1)
            path.closeSubpath()
            painter.drawPath(path)
            
        elif name == "settings" or name == "gear":
            painter.drawEllipse(QPointF(cx, cy), w * 0.2, h * 0.2)
            for i in range(8):
                angle = i * 45
                painter.save()
                painter.translate(cx, cy)
                painter.rotate(angle)
                painter.drawLine(0, -int(h * 0.24), 0, -int(h * 0.4))
                painter.restore()
                
        elif name == "power":
            path = QPainterPath()
            path.addArc(QRectF(x + w * 0.18, y + h * 0.18, w * 0.64, h * 0.64), 45 * 16, 270 * 16)
            painter.drawPath(path)
            painter.drawLine(QPointF(cx, y + h * 0.12), QPointF(cx, cy + h * 0.05))
            
        elif name == "chevron_left":
            path = QPainterPath()
            path.moveTo(x + w * 0.65, y + h * 0.2)
            path.lineTo(x + w * 0.3, cy)
            path.lineTo(x + w * 0.65, y + h * 0.8)
            painter.drawPath(path)
            
        elif name == "chevron_right":
            path = QPainterPath()
            path.moveTo(x + w * 0.35, y + h * 0.2)
            path.lineTo(x + w * 0.7, cy)
            path.lineTo(x + w * 0.35, y + h * 0.8)
            painter.drawPath(path)
            
        elif name == "close":
            painter.drawLine(QPointF(x + w * 0.25, y + h * 0.25), QPointF(x + w * 0.75, y + h * 0.75))
            painter.drawLine(QPointF(x + w * 0.75, y + h * 0.25), QPointF(x + w * 0.25, y + h * 0.75))
            
        elif name == "minimize":
            painter.drawLine(QPointF(x + w * 0.2, cy), QPointF(x + w * 0.8, cy))
            
        elif name == "dock":
            painter.drawRoundedRect(QRectF(x + w * 0.18, y + h * 0.18, w * 0.35, h * 0.35), 2, 2)
            painter.drawRoundedRect(QRectF(x + w * 0.45, y + h * 0.45, w * 0.35, h * 0.35), 2, 2)
            
        else:
            painter.drawEllipse(QPointF(cx, cy), w * 0.2, h * 0.2)
            
        painter.restore()


class RiotIconWidget(QWidget):
    """Reusable QWidget that paints a resolution-independent vector icon."""
    
    def __init__(self, name: str, size: int = 20, color: str = "#C8AA6E", parent=None):
        super().__init__(parent)
        self.icon_name = name
        self.icon_size = size
        self.icon_color = QColor(color)
        self.setFixedSize(size, size)
        
    def set_color(self, color: str):
        self.icon_color = QColor(color)
        self.update()

    def set_icon(self, name: str):
        self.icon_name = name
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = QRectF(0, 0, self.width(), self.height())
        VectorIconPainter.draw(painter, self.icon_name, rect, self.icon_color)


def get_icon_pixmap(name: str, size: int = 24, color: str = "#C8AA6E") -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    rect = QRectF(0, 0, size, size)
    VectorIconPainter.draw(painter, name, rect, QColor(color))
    painter.end()
    return pixmap


def get_icon(name: str, size: int = 24, color: str = "#C8AA6E") -> QIcon:
    return QIcon(get_icon_pixmap(name, size, color))
