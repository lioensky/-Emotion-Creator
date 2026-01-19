import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QFileDialog, QLabel, QSpinBox, QScrollArea, 
                             QLineEdit, QGridLayout, QMessageBox, QFrame)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QCursor
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QPoint
from PIL import Image

class ImageLabel(QLabel):
    grid_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.rows = 4
        self.cols = 4
        self.pixmap_orig = None
        self.row_offsets = [] # Normalized offsets (0.0 to 1.0)
        self.col_offsets = []
        self.dragging_line = None # ('row', index) or ('col', index)
        self.setMouseTracking(True)

    def set_image(self, pixmap):
        self.pixmap_orig = pixmap
        self.reset_offsets()
        self.update_display()

    def reset_offsets(self):
        self.row_offsets = [i / self.rows for i in range(self.rows + 1)]
        self.col_offsets = [j / self.cols for j in range(self.cols + 1)]

    def update_grid_count(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.reset_offsets()
        self.update_display()

    def update_display(self):
        if self.pixmap_orig:
            temp_pixmap = self.pixmap_orig.copy()
            painter = QPainter(temp_pixmap)
            pen = QPen(QColor(255, 0, 0, 150))
            pen.setWidth(max(2, temp_pixmap.width() // 300))
            painter.setPen(pen)

            w = temp_pixmap.width()
            h = temp_pixmap.height()

            for y_offset in self.row_offsets[1:-1]:
                y = int(h * y_offset)
                painter.drawLine(0, y, w, y)
            
            for x_offset in self.col_offsets[1:-1]:
                x = int(w * x_offset)
                painter.drawLine(x, 0, x, h)
            
            painter.end()
            self.setPixmap(temp_pixmap)

    def mousePressEvent(self, event):
        if not self.pixmap_orig: return
        pos = event.position()
        # Convert widget pos to pixmap pos
        pix_rect = self.pixmapRect()
        if not pix_rect.contains(pos.toPoint()): return

        rel_x = (pos.x() - pix_rect.left()) / pix_rect.width()
        rel_y = (pos.y() - pix_rect.top()) / pix_rect.height()

        threshold = 0.02
        # Check cols
        for i, x_off in enumerate(self.col_offsets[1:-1]):
            if abs(rel_x - x_off) < threshold:
                self.dragging_line = ('col', i + 1)
                return
        # Check rows
        for i, y_off in enumerate(self.row_offsets[1:-1]):
            if abs(rel_y - y_off) < threshold:
                self.dragging_line = ('row', i + 1)
                return

    def mouseMoveEvent(self, event):
        pix_rect = self.pixmapRect()
        pos = event.position()
        
        if self.dragging_line:
            rel_x = max(0.0, min(1.0, (pos.x() - pix_rect.left()) / pix_rect.width()))
            rel_y = max(0.0, min(1.0, (pos.y() - pix_rect.top()) / pix_rect.height()))

            if self.dragging_line[0] == 'col':
                idx = self.dragging_line[1]
                # Keep order
                if self.col_offsets[idx-1] < rel_x < self.col_offsets[idx+1]:
                    self.col_offsets[idx] = rel_x
            else:
                idx = self.dragging_line[1]
                if self.row_offsets[idx-1] < rel_y < self.row_offsets[idx+1]:
                    self.row_offsets[idx] = rel_y
            
            self.update_display()
        else:
            # Change cursor if hovering over line
            if not pix_rect.contains(pos.toPoint()):
                self.setCursor(Qt.CursorShape.ArrowCursor)
                return
            
            rel_x = (pos.x() - pix_rect.left()) / pix_rect.width()
            rel_y = (pos.y() - pix_rect.top()) / pix_rect.height()
            threshold = 0.02
            
            on_col = any(abs(rel_x - x_off) < threshold for x_off in self.col_offsets[1:-1])
            on_row = any(abs(rel_y - y_off) < threshold for y_off in self.row_offsets[1:-1])
            
            if on_col: self.setCursor(Qt.CursorShape.SplitHCursor)
            elif on_row: self.setCursor(Qt.CursorShape.SplitVCursor)
            else: self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self.dragging_line = None

    def pixmapRect(self):
        if not self.pixmap(): return QRect()
        return self.itemRect(self.pixmap())

    def itemRect(self, item):
        # Calculate the actual rect of the pixmap inside the label (considering Alignment)
        res = QRect(0, 0, item.width(), item.height())
        label_w = self.width()
        label_h = self.height()
        
        # Simplified for Center alignment
        res.moveLeft((label_w - item.width()) // 2)
        res.moveTop((label_h - item.height()) // 2)
        return res

class EmotionCreator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("表情包批量切割创建器 (支持拖动分割线)")
        self.resize(1200, 800)

        self.image_path = None
        self.rows = 4
        self.cols = 4
        self.name_inputs = []

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left side: Image Preview
        left_layout = QVBoxLayout()
        self.scroll_area = QScrollArea()
        self.image_label = ImageLabel()
        self.image_label.setText("请导入图片\n(导入后可拖动红色分割线)")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)
        left_layout.addWidget(self.scroll_area)
        
        main_layout.addLayout(left_layout, 3)

        # Right side: Controls
        right_panel = QFrame()
        right_panel.setFixedWidth(350)
        right_layout = QVBoxLayout(right_panel)
        
        # Import Button
        self.btn_import = QPushButton("导入图片")
        self.btn_import.setFixedHeight(40)
        self.btn_import.clicked.connect(self.import_image)
        right_layout.addWidget(self.btn_import)

        # Grid Controls
        grid_ctrl_layout = QHBoxLayout()
        grid_ctrl_layout.addWidget(QLabel("行数:"))
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(1, 20)
        self.spin_rows.setValue(self.rows)
        self.spin_rows.valueChanged.connect(self.on_grid_count_changed)
        grid_ctrl_layout.addWidget(self.spin_rows)

        grid_ctrl_layout.addWidget(QLabel("列数:"))
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 20)
        self.spin_cols.setValue(self.cols)
        self.spin_cols.valueChanged.connect(self.on_grid_count_changed)
        grid_ctrl_layout.addWidget(self.spin_cols)
        right_layout.addLayout(grid_ctrl_layout)

        # Naming Area
        right_layout.addWidget(QLabel("切片命名 (按顺序):"))
        self.name_scroll = QScrollArea()
        self.name_container = QWidget()
        self.name_grid = QGridLayout(self.name_container)
        self.name_scroll.setWidget(self.name_container)
        self.name_scroll.setWidgetResizable(True)
        right_layout.addWidget(self.name_scroll)

        # Export Button
        self.btn_export = QPushButton("一键批量导出")
        self.btn_export.setFixedHeight(40)
        self.btn_export.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_export.clicked.connect(self.export_images)
        right_layout.addWidget(self.btn_export)

        main_layout.addWidget(right_panel)
        self.update_name_inputs()

    def import_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            self.image_path = file_path
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.critical(self, "错误", "无法加载图片")
                return
            self.image_label.set_image(pixmap)
            self.on_grid_count_changed()

    def on_grid_count_changed(self):
        self.rows = self.spin_rows.value()
        self.cols = self.spin_cols.value()
        self.image_label.update_grid_count(self.rows, self.cols)
        self.update_name_inputs()

    def update_name_inputs(self):
        old_names = [edit.text() for edit in self.name_inputs]
        for i in reversed(range(self.name_grid.count())): 
            w = self.name_grid.itemAt(i).widget()
            if w: w.setParent(None)
        self.name_inputs = []

        for r in range(self.rows):
            for c in range(self.cols):
                idx = r * self.cols + c
                edit = QLineEdit()
                if idx < len(old_names): edit.setText(old_names[idx])
                edit.setPlaceholderText(f"切片 {idx+1} 文件名")
                self.name_grid.addWidget(QLabel(f"{r+1}-{c+1}:"), idx, 0)
                self.name_grid.addWidget(edit, idx, 1)
                self.name_inputs.append(edit)

    def export_images(self):
        if not self.image_path:
            QMessageBox.warning(self, "警告", "请先导入图片")
            return

        export_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not export_dir: return

        try:
            img = Image.open(self.image_path)
            width, height = img.size
            
            row_px = [int(h * height) for h in self.image_label.row_offsets]
            col_px = [int(w * width) for w in self.image_label.col_offsets]

            for r in range(self.rows):
                for c in range(self.cols):
                    idx = r * self.cols + c
                    name = self.name_inputs[idx].text().strip()
                    if not name: name = f"slice_{r+1}_{c+1}"
                    
                    left, top = col_px[c], row_px[r]
                    right, bottom = col_px[c+1], row_px[r+1]

                    crop = img.crop((left, top, right, bottom))
                    _, ext = os.path.splitext(self.image_path)
                    save_path = os.path.join(export_dir, f"{name}{ext}")
                    
                    if ext.lower() in ['.jpg', '.jpeg'] and crop.mode == 'RGBA':
                        background = Image.new("RGB", crop.size, (255, 255, 255))
                        background.paste(crop, mask=crop.split()[3])
                        background.save(save_path, "JPEG", quality=95)
                    else:
                        crop.save(save_path)

            QMessageBox.information(self, "成功", f"已成功导出 {self.rows * self.cols} 张图片")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EmotionCreator()
    window.show()
    sys.exit(app.exec())