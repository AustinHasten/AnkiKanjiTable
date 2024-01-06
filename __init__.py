# NOTES
# The interval on the most recent review is not always equal to the interval on the card.
# Any rescheduling (i.e. via FSRS Helper) can change the interval on the card without changing the interval in the revlog.
# Just something to keep in mind. Time travel is still accurate to the time you travel to -
#   on the day of the revlog, that WAS the interval after the review. So this is almost desirous?
#
# The time it takes to save the png is 70 times larger than the steps leading up to it so don't waste time trying to optimize that much
# ex. 0.3s vs 24.3s
#
# Any user-input times need to be converted to utc with datetime.astimezone(localTZ) because DB is in utc

# TODO
#   Make sure times are being converted to the correct time zones
#   Make stuff into enums like which size option is selected and junk
#   TEST THIS ON NOTES THAT HAVE MULTIPLE CARD TYPES
# PNG
# GIF
#   Add linux support
#   Clear tmpDir between gif runs to prevent old pictures from getting in the gif
#   resize instead of fail if table is too big for gif

# TODO?
#   Generate themes from a start and end color
#   Allow regex for field name in case people have their kanji fields name differently in different note types
# GIF
#   Skip days where no reviews were done
#   Add configurable info to overlay besides just date. New cards done, reviews done, time taken, etc.
#   Hold last frame for multiple frames
#   Find a way to move createGIF to table class

import os
import re
import fnmatch
import datetime
import math
import subprocess
import webbrowser
import unicodedata

from aqt import mw, gui_hooks
from aqt.qt import Qt, qconnect, QColor, QBrush, QTableWidgetItem, QTableWidget, QAbstractItemView, QFileDialog, QStandardPaths, QStyle, QSize, QWidget, QHBoxLayout, QSplitter, QVBoxLayout, QSizePolicy, QComboBox, QScrollArea, QSpinBox, QButtonGroup, QRadioButton, QDateTime, QDateTimeEdit, QDate, QDateEdit, QPushButton, QCheckBox, QSlider, QLabel, QAction, QPainter, QPainterPath, QFontDatabase, QDialog, QPixmap, QImage, QLineEdit, QTimer, pyqtSignal
# from aqt.utils import showCritical
from anki import utils as ankiUtils

from .utils import queries, MyGroupBox, dateRange, maxDatetime, minDatetime
from .colorUtils import themes, getColor, invertColor

# exe = os.path.join(os.path.dirname(__file__), 'ffmpeg.exe')
# localTZ = datetime.datetime.utcnow().astimezone().tzinfo  # https://stackoverflow.com/a/39079819

seenFGColor = QColor('#000000')
unseenFGColor = QColor('#000000')
unseenBGColor = QColor('#FFFFFF')


class MyQLineEdit(QLineEdit):
    focusLost = pyqtSignal()

    def focusOutEvent(self, event):
        self.focusLost.emit()
        super().focusOutEvent(event)

# class GIFDialog(QDialog):
#     def manualStartDateToggled(self, isChecked):
#         self.startDateInput.setEnabled(isChecked)
#
#     def manualEndDateToggled(self, isChecked):
#         self.endDateInput.setEnabled(isChecked)
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.layout = QVBoxLayout(self)
#
#         self.startDateGroupBox = MyGroupBox('Start Date')
#         self.startDateEarliestRadio = QRadioButton('Earliest Review')
#         self.startDateManualRadio = QRadioButton('Manual')
#         self.startDateButtonGroup = QButtonGroup()
#         self.startDateButtonGroup.addButton(self.startDateEarliestRadio)
#         self.startDateButtonGroup.addButton(self.startDateManualRadio)
#         self.startDateInput = QDateEdit()
#         self.startDateInput.setEnabled(False)  # Enabled if Manual start date is selected
#         self.startDateInput.setCalendarPopup(True)
#         self.startDateInput.setDate(QDate.currentDate().addDays(-30))
#         self.startDateGroupBox.layout.addWidget(self.startDateEarliestRadio)
#         self.startDateGroupBox.layout.addWidget(self.startDateManualRadio)
#         self.startDateGroupBox.layout.addWidget(self.startDateInput)
#         self.layout.addWidget(self.startDateGroupBox)
#
#         self.endDateGroupBox = MyGroupBox('End Date')
#         self.endDateTodayRadio = QRadioButton('Today')
#         self.endDateLatestRadio = QRadioButton('Latest Review')
#         self.endDateManualRadio = QRadioButton('Manual')
#         self.endDateButtonGroup = QButtonGroup()
#         self.endDateButtonGroup.addButton(self.endDateTodayRadio)
#         self.endDateButtonGroup.addButton(self.endDateLatestRadio)
#         self.endDateButtonGroup.addButton(self.endDateManualRadio)
#         self.endDateInput = QDateEdit()
#         self.endDateInput.setEnabled(False)  # Enabled if Manual end date is selected
#         self.endDateInput.setCalendarPopup(True)
#         self.endDateInput.setDate(QDate.currentDate())
#         self.endDateGroupBox.layout.addWidget(self.endDateTodayRadio)
#         self.endDateGroupBox.layout.addWidget(self.endDateLatestRadio)
#         self.endDateGroupBox.layout.addWidget(self.endDateManualRadio)
#         self.endDateGroupBox.layout.addWidget(self.endDateInput)
#         self.layout.addWidget(self.endDateGroupBox)
#
#         self.saveGIFBtn = QPushButton('Save')
#         self.layout.addWidget(self.saveGIFBtn)
#
#         # Connect signals to slots
#         self.saveGIFBtn.clicked.connect(self.createGIF)
#         self.startDateManualRadio.toggled.connect(self.manualStartDateToggled)
#         self.endDateManualRadio.toggled.connect(self.manualEndDateToggled)
#
#         # Finishing touches
#         self.startDateEarliestRadio.click()
#         self.endDateLatestRadio.click()
#
#         self.exec()
#

# def openGIFDialog():
#     GIFDialog()


class KanjiCell(QTableWidgetItem):
    def __init__(self, idx, value, ivl, *args, **kwargs):
        super().__init__(value, *args, **kwargs)
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.idx = idx
        self.value = value
        self.ivl = ivl

    # @classmethod
    # def fromCard(cls, value, card):  # timeTravelDatetime=None, *args, **kwargs):
    #     idx = card.id  # Index within the list of kanji. Right now it's just the cid.
    #     if len(value) > 1:
    #         value = value[0]
    #     ivl = card.ivl
    #     # if timeTravelDateTime:
    #     #     qry = queries['LatestReviewForCardOnDate'].format(cid=card.id, date=timeTravelDatetime.timestamp())
    #     #     ivl = mw.col.db.first(qry)[1]
    #     #     if ivl is None:
    #     #         ivl = 0
    #     #     else:
    #     #         # If ivl is < 1, it's in seconds rather than days - we'll round that to 1 day for convenience
    #     #         ivl = max(ivl, 1)
    #     return cls(idx, value, ivl)

    @classmethod
    def copy(cls, cell):
        c = cls(cell.idx, cell.value, cell.ivl)
        c.setColors(cell.foreground().color(), cell.background().color())
        return c

    def setColors(self, fg, bg):
        self.setForeground(QBrush(invertColor(bg)))
        self.setBackground(QBrush(bg))

    def openLink(self):
        webbrowser.open(f'https://jisho.org/search/{self.value} %23kanji')


class KanjiTable(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.itemClicked.connect(self.cellClicked)

    def cellClicked(self, cell):
        cell.openLink()

    def setFontSize(self, newSize):
        f = self.font()
        f.setPointSize(newSize)
        self.setFont(f)
        self.resizeCellsToFitContents()

    def resizeCellsToFitContents(self):
        tileWidth = self.font().pointSize() * 2
        for c in range(self.columnCount()):
            self.setColumnWidth(c, tileWidth)
        for r in range(self.rowCount()):
            self.setRowHeight(r, tileWidth)

    def updateColumnCount(self, newColumnCount):
        if newColumnCount == self.columnCount():
            return
        cells = [KanjiCell.copy(c) for c in self.allItems()]
        newRowCount = math.ceil(len(cells) / newColumnCount)
        self.clear()
        self.setColumnCount(newColumnCount)
        self.setRowCount(newRowCount)
        self.resizeCellsToFitContents()
        for idx, cell in enumerate(cells):
            self.setItem(int(idx / newColumnCount), idx % newColumnCount, cell)

    def updateRowCount(self, newRowCount):
        if newRowCount == self.rowCount():
            return
        cells = [KanjiCell.copy(c) for c in self.allItems()]
        newColumnCount = math.ceil(len(cells) / newRowCount)
        self.clear()
        self.setColumnCount(newColumnCount)
        self.setRowCount(newRowCount)
        self.resizeCellsToFitContents()
        for idx, cell in enumerate(cells):
            self.setItem(int(idx / newColumnCount), idx % newColumnCount, cell)

    def setup(self):
        self.hideScrollBars()
        oldSize = self.size()
        self.resize(self.sizeToShowAll())
        return oldSize

    def screenshot(self, cellResolution=100):
        oldSize = self.setup()
        fileName = QFileDialog.getSaveFileName(
            self,
            'Save Page',
            QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DesktopLocation)[0],
            'Portable Network Graphics (*.png)'
        )[0]

        actualWidth = self.horizontalHeader().sectionSize(0) * self.columnCount()
        actualHeight = self.verticalHeader().sectionSize(0) * self.rowCount()
        desiredWidth = self.columnCount() * cellResolution
        desiredHeight = self.rowCount() * cellResolution

        canvasWidth = max(actualWidth, desiredWidth)
        canvasHeight = max(actualHeight, desiredHeight)

        image1 = QImage(canvasWidth, canvasHeight, QImage.Format.Format_RGB32)
        image1.setDevicePixelRatio(desiredWidth / actualWidth)
        self.render(image1)
        image = image1.scaled(desiredWidth, desiredHeight)

        image.save(fileName, b'PNG')

        self.cleanup(oldSize)

    def cleanup(self, oldSize):
        self.resize(oldSize)
        self.showScrollBars()

    def colsToFit(self):
        tileWidth = self.font().pointSize() * 2
        containerWidth = self.width()
        if (tileWidth * self.rowCount()) > self.height():
            scrollBarWidth = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
            containerWidth -= scrollBarWidth
        return math.floor(containerWidth / tileWidth)

    def rowsToFit(self):
        tileHeight = self.font().pointSize() * 2
        containerHeight = self.height()
        if (tileHeight * self.columnCount()) > self.width():
            scrollBarHeight = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
            containerHeight -= scrollBarHeight
        return math.floor(containerHeight / tileHeight)

    def sizeToShowAll(self):
        newWidth = self.horizontalHeader().sectionSize(0) * self.columnCount()
        newHeight = self.verticalHeader().sectionSize(0) * self.rowCount()
        return QSize(newWidth, newHeight)

    def hideScrollBars(self):
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def showScrollBars(self):
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def allItems(self):
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                cell = self.item(r, c)
                if cell:  # Could be none if we're on the last row and have more columns to go but have run out of items
                    yield cell


cjk_re = re.compile("CJK (UNIFIED|COMPATIBILITY) IDEOGRAPH")


def isKanji(unichar):
    return bool(cjk_re.match(unicodedata.name(unichar, "")))


class MyApp(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buildGUI()

    def getTimeTravelIvl(self, cid, timeTravelDateTime):
        qry = queries['LatestReviewForCardOnDate'].format(cid=cid, date=timeTravelDateTime.timestamp())
        ivl = mw.col.db.first(qry)[1]
        # Card had not been seen yet at timeTravelDateTime
        if ivl is None:
            return 0
        # If ivl is < 1, it's in seconds rather than days - we'll round that to 1 day for convenience
        return max(ivl, 1)

    def getKanjiCells(self, timeTravelDatetime=None):
        cids = mw.col.find_cards(self.filterInput.text())
        fieldNamePattern = self.fieldNamePatternInput.text()

        d = {}
        for cid in cids:
            card = mw.col.get_card(cid)
            ivl = card.ivl
            if timeTravelDatetime:
                ivl = self.getTimeTravelIvl(card.id, timeTravelDatetime)
            note = card.note()
            matchingFields = [f for f in note.keys() if fnmatch.fnmatch(f, fieldNamePattern)]
            kanji = [char for matchingField in matchingFields for char in note[matchingField] if isKanji(char)]
            for k in kanji:
                if k not in d or ivl > d[k]['ivl']:
                    d[k] = {
                        'ivl': ivl,
                        'id': card.id
                    }
        return [KanjiCell(idx=v['id'], value=k, ivl=v['ivl']) for k, v in d.items()]

    def buildGUI(self):
        self.mainLayout = QHBoxLayout(self)

        self.splitter = QSplitter()

        self.leftContainer = QWidget()
        self.leftLayout = QVBoxLayout(self.leftContainer)
        self.leftLayoutTopLayout = QHBoxLayout()

        self.settingsGroupBox = MyGroupBox('Settings')
        self.middleScroll = QScrollArea()
        self.middleScroll.setWidgetResizable(True)
        self.middleScroll.setWidget(self.settingsGroupBox)

        self.fieldNameGroupBox = MyGroupBox('Field Name')
        self.fieldNamePatternInput = MyQLineEdit('*Kanji*')
        self.fieldNameGroupBox.layout.addWidget(self.fieldNamePatternInput)

        self.filterGroupBox = MyGroupBox('Filter')
        self.filterInput = MyQLineEdit('deck:*')
        self.filterGroupBox.layout.addWidget(self.filterInput)

        self.strongIntervalSpin = QSpinBox()
        self.strongIntervalSpin.setRange(1, 65536)
        self.strongIntervalSpin.setValue(21)
        self.strongIntervalGroupBox = MyGroupBox('Card interval considered strong')
        self.strongIntervalGroupBox.layout.addWidget(self.strongIntervalSpin)

        self.sizeGroupBox = MyGroupBox('Size')
        self.sizeButtonGroup = QButtonGroup()
        self.fitToWidthRadio = QRadioButton('Fit to Width')
        self.fitToHeightRadio = QRadioButton('Fit to Height')
        self.specifyColumnsRadio = QRadioButton('Specify Columns')
        self.specifyRowsRadio = QRadioButton('Specify Rows')
        self.sizeButtonGroup.addButton(self.fitToWidthRadio)
        self.sizeButtonGroup.addButton(self.fitToHeightRadio)
        self.sizeButtonGroup.addButton(self.specifyColumnsRadio)
        self.sizeButtonGroup.addButton(self.specifyRowsRadio)

        self.specifyColumnsSpin = QSpinBox()
        self.specifyColumnsSpin.setRange(1, 100)
        self.specifyColumnsSpin.setValue(10)

        self.specifyRowsSpin = QSpinBox()
        self.specifyRowsSpin.setRange(1, 100)
        self.specifyRowsSpin.setValue(10)

        self.sizeGroupBox.layout.addWidget(self.fitToWidthRadio)
        self.sizeGroupBox.layout.addWidget(self.fitToHeightRadio)
        self.sizeGroupBox.layout.addWidget(self.specifyColumnsRadio)
        self.sizeGroupBox.layout.addWidget(self.specifyColumnsSpin)
        self.sizeGroupBox.layout.addWidget(self.specifyRowsRadio)
        self.sizeGroupBox.layout.addWidget(self.specifyRowsSpin)

        self.timeTravelInput = QDateTimeEdit()
        self.timeTravelInput.setCalendarPopup(True)
        self.timeTravelInput.setDateTime(QDateTime.currentDateTime())
        self.timeTravelGroupBox = MyGroupBox('Time Travel To')
        self.timeTravelGroupBox.layout.addWidget(self.timeTravelInput)
        self.timeTravelGroupBox.setCheckable(True)
        self.timeTravelGroupBox.setChecked(False)

        self.sortCombo = QComboBox()
        self.sortCombo.addItems(['Index', 'Interval'])
        self.sortGroupBox = MyGroupBox('Sort')
        self.sortGroupBox.layout.addWidget(self.sortCombo)

        self.themeCombo = QComboBox()
        self.themeCombo.addItems(themes.keys())
        self.themeSmoothCheck = QCheckBox('Smooth')
        self.themeGroupBox = MyGroupBox('Theme')
        self.themeGroupBox.layout.addWidget(self.themeCombo)
        self.themeGroupBox.layout.addWidget(self.themeSmoothCheck)

        self.qualityGroupBox = MyGroupBox('PNG Quality')
        self.qualitySlider = QSlider()
        self.qualitySlider.setOrientation(Qt.Orientation.Horizontal)
        self.qualitySlider.setMinimum(25)
        self.qualitySlider.setMaximum(200)
        self.qualitySlider.setValue(100)
        self.qualityGroupBox.layout.addWidget(self.qualitySlider)

        self.leftLayoutBottomLayout = QHBoxLayout()
        self.generateBtn = QPushButton("Generate")

        self.savePNGBtn = QPushButton('Save PNG')
        # self.openGIFBtn = QPushButton('Create GIF')

        # Table stuff
        self.tableContainer = QWidget()
        self.tableLayout = QVBoxLayout(self.tableContainer)
        self.table = KanjiTable()
        self.tableLayout.addWidget(self.table)

        self.fontSizeGroupBox = MyGroupBox('Table Font Size')
        self.fontSizeSlider = QSlider()
        self.fontSizeSlider.setOrientation(Qt.Orientation.Horizontal)
        self.fontSizeSlider.setMinimum(5)
        self.fontSizeSlider.setMaximum(50)
        self.fontSizeSlider.setValue(12)
        self.fontSizeSliderMoved(12)
        self.fontSizeGroupBox.layout.addWidget(self.fontSizeSlider)

        self.table.horizontalHeader().setMinimumSectionSize(self.fontSizeSlider.minimum())
        self.table.verticalHeader().setMinimumSectionSize(self.fontSizeSlider.minimum())

        # Connect signals to slots
        # self.deckCombo.currentTextChanged.connect(self.deckChanged)
        self.sizeButtonGroup.buttonClicked.connect(self.sizeOptionChanged)
        self.sortCombo.currentIndexChanged.connect(self.sortChanged)
        self.themeCombo.currentIndexChanged.connect(self.themeChanged)
        self.themeSmoothCheck.stateChanged.connect(self.smoothToggled)
        self.strongIntervalSpin.textChanged.connect(self.strongIntervalChanged)
        self.timeTravelGroupBox.toggled.connect(self.timeTravelToggled)
        self.timeTravelInput.dateTimeChanged.connect(self.timeTravelDateChanged)
        self.fieldNamePatternInput.returnPressed.connect(self.fieldNamePatternChanged)
        self.fieldNamePatternInput.focusLost.connect(self.fieldNamePatternChanged)
        self.filterInput.returnPressed.connect(self.filterChanged)
        self.filterInput.focusLost.connect(self.filterChanged)

        self.savePNGBtn.clicked.connect(self.takeScreenshot)
        self.generateBtn.clicked.connect(self.populateTable)
        # self.openGIFBtn.clicked.connect(openGIFDialog)
        self.fontSizeSlider.valueChanged.connect(self.fontSizeSliderMoved)

        # Add stuff to leftLayoutTopLayout
        # self.leftLayoutTopLayout.addWidget(QLabel("Deck: "))
        # self.leftLayoutTopLayout.addWidget(self.deckCombo)

        # Add stuff to leftLayoutMiddleLayout
        # self.settingsGroupBox.layout.addWidget(self.patternGroupBox)
        self.settingsGroupBox.layout.addWidget(self.fieldNameGroupBox)
        self.settingsGroupBox.layout.addWidget(self.filterGroupBox)
        self.settingsGroupBox.layout.addWidget(self.strongIntervalGroupBox)
        self.settingsGroupBox.layout.addWidget(self.sizeGroupBox)
        self.settingsGroupBox.layout.addWidget(self.sortGroupBox)
        self.settingsGroupBox.layout.addWidget(self.timeTravelGroupBox)
        self.settingsGroupBox.layout.addWidget(self.themeGroupBox)
        self.settingsGroupBox.layout.addWidget(self.fontSizeGroupBox)
        self.settingsGroupBox.layout.addWidget(self.qualityGroupBox)

        # Add stuff to leftLayoutBottomLayout
        # self.leftLayoutBottomLayout.addWidget(self.generateBtn)
        self.leftLayoutBottomLayout.addWidget(self.savePNGBtn)
        # self.leftLayoutBottomLayout.addWidget(self.openGIFBtn)

        # Add stuff to leftLayout
        # self.leftLayout.addLayout(self.leftLayoutTopLayout)
        self.leftLayout.addWidget(self.middleScroll)
        self.leftLayout.addLayout(self.leftLayoutBottomLayout)

        # Add stuff to main layout
        self.splitter.addWidget(self.leftContainer)
        self.splitter.addWidget(self.tableContainer)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.mainLayout.addWidget(self.splitter)

        # Finishing touches
        self.fitToWidthRadio.click()

        self.populateTable()

    def filterChanged(self):
        self.populateTable()

    def fieldNamePatternChanged(self):
        self.populateTable()

    def takeScreenshot(self):
        self.table.screenshot(self.qualitySlider.value())

    def timeTravelDateChanged(self):
        self.populateTable()

    def timeTravelToggled(self):
        self.populateTable()

    def strongIntervalChanged(self):
        self.populateTable()

    def fieldNameChanged(self):
        self.populateTable()

    def smoothToggled(self):
        self.populateTable()

    def sortChanged(self, idx):
        self.populateTable()

    def sizeOptionChanged(self, button):
        self.populateTable()

    # TODO Just update colors instead of repopulating the whole table?
    def themeChanged(self, idx):
        self.populateTable()

    def fontSizeSliderMoved(self, newSize):
        self.table.setFontSize(newSize)
        if self.fitToWidthRadio.isChecked():
            self.table.updateColumnCount(self.table.colsToFit())
        elif self.fitToHeightRadio.isChecked():
            self.table.updateRowCount(self.table.rowsToFit())

    def populateTable(self, timeTravelDatetime=None):
        self.table.clear()

        if not timeTravelDatetime and self.timeTravelGroupBox.isChecked():
            timeTravelDatetime = self.timeTravelInput.dateTime().toPyDateTime()

        cells = self.getKanjiCells(timeTravelDatetime)
        self.setWindowTitle(f'Kanji Table ({len(cells)})')
        if self.sortCombo.currentText() == 'Index':
            cells = sorted(cells, key=lambda _: _.idx)
        elif self.sortCombo.currentText() == 'Interval':
            cells = sorted(cells, key=lambda _: _.ivl, reverse=True)
        if not cells:
            self.table.setColumnCount(0)
            self.table.setRowCount(0)
            self.savePNGBtn.setEnabled(False)
            return
        self.savePNGBtn.setEnabled(True)

        # Set number of columns and rows
        if self.fitToWidthRadio.isChecked():
            cols = self.table.colsToFit()
            rows = math.ceil(len(cells) / cols)
        elif self.fitToHeightRadio.isChecked():
            rows = self.table.rowsToFit()
            cols = math.ceil(len(cells) / rows)
        elif self.specifyColumnsRadio.isChecked():
            cols = self.specifyColumnsSpin.value()
            rows = math.ceil(len(cells) / cols)
        elif self.specifyRowsRadio.isChecked():
            rows = self.specifyRowsSpin.value()
            cols = math.ceil(len(cells) / rows)
        else:
            return
        self.table.setColumnCount(cols)
        self.table.setRowCount(rows)

        strongIvl = self.strongIntervalSpin.value()
        selectedTheme = self.themeCombo.currentText()
        smooth = self.themeSmoothCheck.isChecked()

        for idx, cell in enumerate(cells):
            if bool(cell.ivl):  # ivl should be None/0 if unseen, nonzero if seen
                bgColor = getColor(selectedTheme, cell.ivl / strongIvl, smooth)
                cell.setColors(seenFGColor, bgColor)
            else:
                cell.setColors(unseenFGColor, unseenBGColor)
            self.table.setItem(int(idx / cols), idx % cols, cell)

        self.table.resizeCellsToFitContents()


    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.populateTable)


    '''
    def getStartDate(self):
        startDateOption = self.startDateButtonGroup.checkedButton().text()
        if startDateOption == 'Manual':
            return self.startDateInput.dateTime().toPyDateTime()
        elif startDateOption == 'Earliest Review':
            did = mw.col.decks.by_name(self.deckCombo.currentText())['id']
            result = mw.col.db.first(queries['EarliestReviewForDeck'].format(did=did))
            if len(result) < 1:
                return maxDatetime
            else:
                return datetime.datetime.fromtimestamp(result[0])

    def getEndDate(self):
        endDateOption = self.endDateButtonGroup.checkedButton().text()
        if endDateOption == 'Manual':
            return self.endDateInput.dateTime().toPyDateTime()
        elif endDateOption == 'Latest Review':
            did = mw.col.decks.by_name(self.deckCombo.currentText())['id']
            result = mw.col.db.first(queries['LatestReviewForDeck'].format(did=did))
            if len(result) < 1:
                return minDatetime
            else:
                return datetime.datetime.fromtimestamp(result[0])
        elif endDateOption == 'Today':
            return datetime.combine(QDate.currentDate().toPyDate(), datetime.min.time())

    def createGIF(self, startDate=None, endDate=None):
        self.populateTable(timeTravelDatetime=minDatetime)  # Make sure we start with a populated table
        newSize = self.table.sizeToShowAll()
        if newSize.width() > 65535 or newSize.height() > 65535:
            showCritical('At least one dimension of table is too large for gif. Increase number of columns and/or decrease font size.')
            return
        # Setup
        mw.progress.start(immediate=True)
        oldSize = self.table.setup()
        # selectedTheme = self.themeCombo.currentText()
        # strongIvl = self.strongIntervalSpin.value()
        tmpDir = ankiUtils.tmpdir()
        rollover = mw.col.get_preferences().scheduling.rollover

        painter = QPainter()
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fontSize = (self.table.width() * 0.75) / 10  # 3/4 of table width / len('YYYY-MM-DD')
        font.setPixelSize(int(fontSize))

        def paintDateOnPixmap(pxMap, date):
            painter.begin(pxMap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.setFont(font)
            brect = painter.boundingRect(0, 0, self.table.width(), self.table.height(), Qt.AlignmentFlag.AlignCenter, adjustedDt.strftime('%Y-%m-%d'))
            path = QPainterPath()
            path.addRoundedRect(brect.toRectF(), 10, 10)
            painter.setPen(QColor(63, 63, 63, 182))
            painter.drawPath(path)
            painter.fillPath(path, QColor(63, 63, 63, 182))
            painter.setPen(QColor('#ffffff'))
            painter.drawText(0, 0, self.table.width(), self.table.height(), Qt.AlignmentFlag.AlignCenter, adjustedDt.strftime('%Y-%m-%d'))
            painter.end()

        startDate = self.getStartDate()
        endDate = self.getEndDate()
        for idx, dt in enumerate(dateRange(startDate, endDate)):
            adjustedDt = dt + datetime.timedelta(days=1, hours=rollover)
            self.populateTable(timeTravelDatetime=adjustedDt)
            mw.app.processEvents()
            fileName = os.path.join(tmpDir, f'KanjiTable_{idx}.png')
            pxMap = self.table.grab()
            paintDateOnPixmap(pxMap, adjustedDt)
            pxMap.save(fileName, b'PNG')

        fp_in = os.path.join(tmpDir, 'KanjiTable_%d.png')
        fp_out = os.path.join(tmpDir, 'image.gif')
        p = subprocess.Popen([
            exe, '-y',  # Overwrite without asking
            '-framerate', '2',  # Low framerate to make the gif slower
            '-loglevel', 'error',  # Shhh
            '-i', fp_in,  # Input file
            fp_out  # Output file
        ], startupinfo=startupinfo)
        while p.poll() is None:
            mw.app.processEvents()

        # Cleanup
        self.table.cleanup(oldSize)
        self.populateTable()  # Reset table
        mw.progress.finish()
    '''


def showConfig():
    mw.kanjiGridWidget.showMaximized()


def setup():
    mw.kanjiGridWidget = widget = MyApp()
    action = QAction('Kanji Table', mw)
    qconnect(action.triggered, showConfig)
    mw.form.menuTools.addAction(action)


# # Prevent mpv window from showing on Windows machines.
# if ankiUtils.isWin:
#     startupinfo = subprocess.STARTUPINFO()
#     startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
# else:
#     startupinfo = None
gui_hooks.profile_did_open.append(setup)
