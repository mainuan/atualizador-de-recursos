"""Composição clássica aprovada, compartilhada pelo aplicativo e pela prévia."""
from pathlib import Path

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QIcon, QImageReader, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenu, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

ILLUSTRATION = Path(__file__).with_name('assets') / 'mainuan-novidades.png'


def text_label(text):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    policy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    policy.setHeightForWidth(True)
    label.setSizePolicy(policy)
    label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    return label


class Illustration(QWidget):
    def __init__(self, path=ILLUSTRATION, parent=None):
        super().__init__(parent)
        reader = QImageReader(str(path))
        image_format = bytes(reader.format()).lower()
        image = reader.read()
        if image.isNull() or image_format != b'png' or not image.hasAlphaChannel():
            raise ValueError('Forneça a ilustração do Mainuan em PNG com transparência.')
        self.pixmap = QPixmap.fromImage(image)
        self.setAccessibleName('Beija-flor-de-fronte-violeta diante de um notebook, com a mensagem Novidade!')
        self.setMinimumWidth(88)
        self.setMaximumWidth(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self):
        return QSize(230, 288)

    def image_rect(self):
        size = self.pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        return QRectF((self.width() - size.width()) / 2, 0,
                      size.width(), size.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.image_rect(), self.pixmap, QRectF(self.pixmap.rect()))


class StatusLabel(QLabel):
    """Mensagens operacionais em texto simples, sem ocupar espaço quando vazias."""
    def __init__(self):
        super().__init__()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        policy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.hide()

    def setText(self, value):
        super().setText(value)
        self.setVisible(bool(value))


class ClassicContent(QWidget):
    def __init__(self, message='', programs=(), illustration=ILLUSTRATION):
        super().__init__()
        self.setMinimumSize(380, 280)
        self.column = column = QVBoxLayout(self)
        column.setContentsMargins(20, 12, 20, 20)
        column.setSpacing(8)
        top = QHBoxLayout()
        top.addStretch()
        self.options = QToolButton()
        self.options.setIcon(QIcon.fromTheme('application-menu'))
        self.options.setToolTip('Mais opções')
        self.options.setAccessibleName('Mais opções')
        self.options.setAutoRaise(True)
        self.options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu = menu = QMenu(self.options)
        self.options.setMenu(menu)
        top.addWidget(self.options)
        column.addLayout(top)
        self.body = body = QHBoxLayout()
        body.setSpacing(20)
        self.illustration = Illustration(illustration)
        body.addWidget(self.illustration, 2)
        self.right = QWidget()
        self.right_layout = right = QVBoxLayout(self.right)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(12)
        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(50)
        content = QWidget()
        self.scroll.setAutoFillBackground(False)
        self.scroll.viewport().setAutoFillBackground(False)
        content.setAutoFillBackground(False)
        self.copy_layout = copy = QVBoxLayout(content)
        copy.setContentsMargins(0, 4, 4, 4)
        copy.setSpacing(10)
        self.message = text_label(message)
        self.base_point_size = self.message.font().pointSizeF()
        font = self.message.font()
        font.setPointSizeF(font.pointSizeF() + 2)
        font.setBold(True)
        self.message.setFont(font)
        copy.addWidget(self.message)
        self.status = StatusLabel()
        copy.addWidget(self.status)
        self.program_labels = []
        copy.addStretch()
        self.set_programs(programs)
        self.scroll.setWidget(content)
        right.addWidget(self.scroll, 1)
        self.progress = QProgressBar()
        self.progress.hide()
        right.addWidget(self.progress)
        actions = QVBoxLayout()
        actions.setSpacing(8)
        self.know = QPushButton('Conhecer novidades')
        self.know.setIcon(QIcon.fromTheme('internet-web-browser'))
        font = self.know.font()
        font.setBold(True)
        self.know.setFont(font)
        self.know.setDefault(True)
        self.know.setAccessibleDescription('Ação principal: abrir a página oficial no navegador.')
        self.install = QPushButton('Instalar novidades')
        self.install.setIcon(QIcon.fromTheme('system-software-install'))
        self.install.setAutoDefault(False)
        self.install.setAccessibleDescription('Prepara a operação e pede confirmação antes de instalar.')
        self.later = QPushButton('Agora não')
        self.later.setFlat(True)
        self.later.setAutoDefault(False)
        self.later.setAccessibleDescription('Adia a notificação por 24 horas, preservando o acesso manual.')
        self.buttons = (self.know, self.install, self.later)
        width = max(button.sizeHint().width() for button in self.buttons) + 16
        height = max(button.sizeHint().height() for button in self.buttons)
        for button in self.buttons:
            button.setFixedSize(width, height)
            actions.addWidget(button, 0, Qt.AlignmentFlag.AlignRight)
        right.addLayout(actions)
        body.addWidget(self.right, 3)
        column.addLayout(body, 1)
        self.know.setFocus()

    def set_programs(self, names):
        for item in self.program_labels:
            item.hide()
            self.copy_layout.removeWidget(item)
            item.deleteLater()
        self.program_labels.clear()
        for index, name in enumerate(names):
            item = text_label('•  ' + name)
            self.program_labels.append(item)
            self.copy_layout.insertWidget(index + 2, item)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.height() < 360
        self.column.setContentsMargins(*((12, 8, 12, 12) if compact else (20, 12, 20, 20)))
        self.body.setSpacing(12 if compact else 20)
        self.right_layout.setSpacing(8 if compact else 12)
        self.copy_layout.setSpacing(4 if compact else 10)
        font = self.message.font()
        font.setPointSizeF(self.base_point_size + (0 if compact else 2))
        self.message.setFont(font)
