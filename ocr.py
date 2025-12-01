import io  # <--- Helper for memory buffer
import sys

import mss
import pyperclip
import pytesseract
from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets


class SnippingTool(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.begin = QtCore.QPoint()
        self.end = QtCore.QPoint()
        self.is_selecting = False

        # --- SCREENSHOT CAPTURE ---
        with mss.mss() as sct:
            # Monitor 0 is the "All in one" virtual monitor
            monitor = sct.monitors[0]
            sct_img = sct.grab(monitor)

            # 1. Create the PIL Image (We keep this for OCR later)
            self.pil_img = Image.frombytes(
                "RGB", sct_img.size, sct_img.bgra, "raw", "BGRX"
            )

            # 2. THE FIX: Save image to a memory buffer as PNG
            # This bypasses raw byte alignment/skew issues entirely.
            buffer = io.BytesIO()
            self.pil_img.save(buffer, format="PNG")
            qdata = buffer.getvalue()

            # 3. Load QPixmap from the PNG data
            self.screen_pixmap = QtGui.QPixmap()
            self.screen_pixmap.loadFromData(qdata, "PNG")

            # Store offsets (in case of multi-monitor setups with negative coords)
            self.offset_x = monitor["left"]
            self.offset_y = monitor["top"]

        # --- WINDOW SETUP ---
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Tool
        )

        # Force the window to be exactly the size and position of the screenshot
        self.setGeometry(
            self.offset_x,
            self.offset_y,
            self.screen_pixmap.width(),
            self.screen_pixmap.height(),
        )

        self.setCursor(QtGui.QCursor(QtCore.Qt.CrossCursor))
        self.show()

    def paintEvent(self, event):
        qp = QtGui.QPainter(self)

        # 1. Draw the clear screenshot
        qp.drawPixmap(0, 0, self.screen_pixmap)

        # 2. Calculate the Dark Overlay Path
        # Start with a path covering the whole screen
        path = QtGui.QPainterPath()
        path.addRect(QtCore.QRectF(self.rect()))

        # 3. Punch a hole for the selection
        if not self.begin.isNull() and not self.end.isNull():
            x1 = min(self.begin.x(), self.end.x())
            y1 = min(self.begin.y(), self.end.y())
            w = abs(self.begin.x() - self.end.x())
            h = abs(self.begin.y() - self.end.y())

            selection_path = QtGui.QPainterPath()
            selection_path.addRect(x1, y1, w, h)
            path = path.subtracted(selection_path)

            # Draw Red Border
            qp.setPen(QtGui.QPen(QtGui.QColor("red"), 2))
            qp.setBrush(QtCore.Qt.NoBrush)
            qp.drawRect(x1, y1, w, h)

        # 4. Fill the dark path
        # This draws the "Grayed out" look over everything EXCEPT your selection
        qp.setPen(QtCore.Qt.NoPen)
        qp.setBrush(QtGui.QColor(0, 0, 0, 100))
        qp.drawPath(path)

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = self.begin
        self.is_selecting = True
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        self.end = event.pos()
        self.is_selecting = False
        self.close()
        self.process_ocr()

    def process_ocr(self):
        x1 = min(self.begin.x(), self.end.x())
        y1 = min(self.begin.y(), self.end.y())
        x2 = max(self.begin.x(), self.end.x())
        y2 = max(self.begin.y(), self.end.y())

        width = x2 - x1
        height = y2 - y1

        if width < 10 or height < 10:
            print("Selection too small.")
            QtWidgets.QApplication.quit()
            return

        try:
            # Crop the PIL image
            cropped_img = self.pil_img.crop((x1, y1, x2, y2))

            # Optional: Convert to grayscale for better OCR accuracy
            # cropped_img = cropped_img.convert("L")

            # OCR
            text = pytesseract.image_to_string(cropped_img)
            clean_text = text.strip()

            if clean_text:
                pyperclip.copy(clean_text)
                print("\n✅ OCR SUCCESS:")
                print("----------------------------")
                print(clean_text)
                print("----------------------------")
            else:
                print("⚠️  OCR finished, but no text found.")

        except Exception as e:
            print(f"Error: {e}")

        QtWidgets.QApplication.quit()


if __name__ == "__main__":
    # High DPI support
    if hasattr(QtCore.Qt, "AA_EnableHighDpiScaling"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, "AA_UseHighDpiPixmaps"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    window = SnippingTool()
    sys.exit(app.exec_())
