from typing import Callable, Optional
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)


class ActionDelegate(QStyledItemDelegate):
    """Delegate rendering the 3-dot (⋮) menu button and managing action triggers."""

    action_triggered = Signal(str, int)  # action_name, row_index

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()

        # Draw cell background
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            bg_color = index.data(Qt.BackgroundRole)
            if bg_color:
                painter.fillRect(option.rect, bg_color)

        # Draw 3-dot button rectangle
        btn_width = 28
        btn_height = 24
        x = option.rect.x() + (option.rect.width() - btn_width) // 2
        y = option.rect.y() + (option.rect.height() - btn_height) // 2
        btn_rect = QRect(x, y, btn_width, btn_height)

        # Hover state
        if option.state & QStyle.State_MouseOver:
            painter.setBrush(QColor("#E2E8F0"))
            painter.setPen(QColor("#CBD5E1"))
            painter.drawRoundedRect(btn_rect, 4, 4)

        # Draw dots text "⋮"
        font = QFont("Segoe UI", 13, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#1E293B") if not (option.state & QStyle.State_Selected) else option.palette.highlightedText().color())
        painter.drawText(btn_rect, Qt.AlignCenter, "⋮")

        painter.restore()

    def editorEvent(self, event, model, option, index):
        # Handle single left-click to open actions menu
        if event.type() == event.Type.MouseButtonRelease and event.button() == Qt.LeftButton:
            self.show_menu(index.row(), option.rect)
            return True
        return super().editorEvent(event, model, option, index)

    def show_menu(self, row: int, rect: QRect):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                padding: 4px;
                border-radius: 6px;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 20px 6px 24px;
                border-radius: 4px;
                color: #1E293B;
            }
            QMenu::item:selected {
                background-color: #EFF6FF;
                color: #1D4ED8;
            }
            QMenu::separator {
                height: 1px;
                background: #F1F5F9;
                margin: 4px 8px;
            }
        """)

        atr_action = menu.addAction("📋  ATR Management")
        menu.addSeparator()
        edit_action = menu.addAction("✏️  Edit Representation")
        update_action = menu.addAction("🔄  Quick Update")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️  Delete Representation")

        action = menu.exec(QCursor.pos())

        if action == atr_action:
            self.action_triggered.emit("atr", row)
        elif action == edit_action:
            self.action_triggered.emit("edit", row)
        elif action == update_action:
            self.action_triggered.emit("update", row)
        elif action == delete_action:
            self.action_triggered.emit("delete", row)
