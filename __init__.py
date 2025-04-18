# NOTE
# The time it takes to save the png is 70 times larger than the steps leading up to it so don't waste time trying to optimize that much
# ex. 0.3s vs 24.3s
# NOTE the way I save pngs has changed so see if this has changed ^^^
#
# Any user-input times need to be converted to utc with datetime.astimezone(localTZ) because DB is in utc

# TODO
#   Grid lines are different color at very bottom??
#   Add more stuff to context menu?
#   Make sure times are being converted to the correct time zones
#   Make stuff into enums like which size option is selected and junk
# GIF
#   Add linux support
#   Clear tmpDir between gif runs to prevent old pictures from getting in the gif
#   resize instead of fail if table is too big for gif

# TODO?
#   Generate themes from a start and end color
# GIF
#   Skip days where no reviews were done
#   Add configurable info to overlay besides just date. New cards done, reviews done, time taken, etc.
#   Hold last frame for multiple frames
#   Find a way to move createGIF to table class

import fnmatch
import re
import sys
from typing import Generator

from aqt import gui_hooks, mw
from aqt.qt import (
    QAction,
    QButtonGroup,
    QCheckBox,
    QColor,
    QComboBox,
    QDateTime,
    QDateTimeEdit,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
    qconnect,
)

from .colorUtils import ThemeManager, getColor, themes
from .data import levelSystems
from .KanjiTable import KanjiCell, KanjiDataDict, KanjiTable, LevelCell
from .utils import MyGroupBox

# Imports for GIF --------
# import os
# import datetime
# import subprocess
# QPixMap, QDate, QSizePolicy, QDateEdit, QLabel, QPainter, QPainterPath, QFontDatabase, QDialog
# from aqt.utils import showCritical
# from anki import utils as ankiUtils
# from .utils import dateRange, maxDatetime, minDatetime
# Vars for GIF --------
# exe = os.path.join(os.path.dirname(__file__), 'ffmpeg.exe')
# localTZ = datetime.datetime.utcnow().astimezone().tzinfo  # https://stackoverflow.com/a/39079819

kanjiRegex = re.compile(r"[㐀-䶵一-鿋豈-頻]")


def isKanji(character: str) -> bool:
    return bool(kanjiRegex.match(character))
    # return any(
    #     [
    #         start <= ord(character) <= end
    #         for start, end in [
    #             (4352, 4607),
    #             (11904, 42191),
    #             (43072, 43135),
    #             (44032, 55215),
    #             (63744, 64255),
    #             (65072, 65103),
    #             (65381, 65500),
    #             (131072, 196607),
    #         ]
    #     ]
    # )


class MyQLineEdit(QLineEdit):
    """QLineEdit that emits a valueChanged signal if the value is changed between focusIn and focusOut"""

    valueChanged = pyqtSignal()

    def focusInEvent(self, event):
        self.previousText = self.text()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        if self.previousText and self.previousText != self.text():
            self.valueChanged.emit()
        super().focusOutEvent(event)


class MyApp(QWidget):
    themeManager: ThemeManager = ThemeManager()
    hasBeenBuilt: bool = False

    def getMatchingKanjiFromNote(self, note) -> Generator[str, None, None]:
        fieldNamePattern = self.fieldNamePatternInput.text()
        matchingFields = [
            f for f in note.keys() if fnmatch.fnmatch(f, fieldNamePattern)
        ]
        for matchingField in matchingFields:
            for char in note[matchingField]:
                if isKanji(char):
                    yield char

    def getMatchingCards(self):
        for cid in mw.col.find_cards(self.filterInput.text()):
            yield mw.col.get_card(cid)

    def getKanjiCells(self, timeTravelDatetime: QDateTime = None) -> list[KanjiCell]:
        kanjiDatas = KanjiDataDict()

        for card in self.getMatchingCards():
            kanjiChars = self.getMatchingKanjiFromNote(card.note())
            kanjiDatas.updateFromCard(card, kanjiChars, timeTravelDatetime)

        # TODO Make these functions be associated data of the combobox options
        # TODO Make these members of kanjidatadict?
        if self.sortCombo.currentText() == "Interval":

            def sortFunc(kanjiData):
                if kanjiData.data["ivl"] is None:
                    return sys.maxsize
                else:
                    return -kanjiData.data["ivl"]

        elif self.sortCombo.currentText() == "Index":
            sortFunc = lambda _: _.data.get("levelIndex", 0)

        if self.groupByGroupBox.isChecked():
            selectedLevelSystem = levelSystems[self.groupByComboBox.currentText()]
            levels = kanjiDatas.splitIntoLevels(selectedLevelSystem)
            r = []
            for levelName, kanjiDataDict in levels.items():
                r.append(LevelCell(levelName))
                r += kanjiDataDict.toKanjiCells(sortFunc)
            return r
        else:
            return kanjiDatas.toKanjiCells(sortFunc)

    def buildGUI(self) -> None:
        self.mainLayout = QHBoxLayout(self)

        self.splitter = QSplitter()

        self.leftContainer = QWidget()
        self.leftLayout = QVBoxLayout(self.leftContainer)

        self.settingsGroupBox = MyGroupBox("Settings")
        self.middleScroll = QScrollArea()
        self.middleScroll.setWidgetResizable(True)
        self.middleScroll.setWidget(self.settingsGroupBox)

        self.fieldNameGroupBox = MyGroupBox("Field Name")
        self.fieldNamePatternInput = MyQLineEdit("Japanese")
        self.fieldNameGroupBox.layout.addWidget(self.fieldNamePatternInput)

        self.filterGroupBox = MyGroupBox("Filter")
        self.filterInput = MyQLineEdit("deck:*")
        self.filterGroupBox.layout.addWidget(self.filterInput)

        self.strongIntervalSpin = QSpinBox()
        self.strongIntervalSpin.setRange(1, 65536)
        self.strongIntervalSpin.setValue(21)
        self.strongIntervalGroupBox = MyGroupBox("Card interval considered strong")
        self.strongIntervalGroupBox.layout.addWidget(self.strongIntervalSpin)

        self.sizeGroupBox = MyGroupBox("Size")
        self.sizeButtonGroup = QButtonGroup()
        self.fitToWidthRadio = QRadioButton("Fit to Width")
        self.specifyColumnsRadio = QRadioButton("Specify Columns")
        self.sizeButtonGroup.addButton(self.fitToWidthRadio)
        self.sizeButtonGroup.addButton(self.specifyColumnsRadio)

        self.specifyColumnsSpin = QSpinBox()
        self.specifyColumnsSpin.setRange(1, 100)
        self.specifyColumnsSpin.setValue(10)

        self.sizeGroupBox.layout.addWidget(self.fitToWidthRadio)
        self.sizeGroupBox.layout.addWidget(self.specifyColumnsRadio)
        self.sizeGroupBox.layout.addWidget(self.specifyColumnsSpin)

        self.timeTravelInput = QDateTimeEdit()
        self.timeTravelInput.setCalendarPopup(True)
        self.timeTravelInput.setDateTime(QDateTime.currentDateTime())
        self.timeTravelGroupBox = MyGroupBox("Time Travel To")
        self.timeTravelGroupBox.layout.addWidget(self.timeTravelInput)
        self.timeTravelGroupBox.setCheckable(True)
        self.timeTravelGroupBox.setChecked(False)

        self.groupByGroupBox = MyGroupBox("Group By")
        self.groupByGroupBox.setCheckable(True)
        self.groupByGroupBox.setChecked(False)

        self.groupByComboBox = QComboBox()
        self.groupByComboBox.addItems(levelSystems.keys())
        self.groupByGroupBox.layout.addWidget(self.groupByComboBox)

        self.sortGroupBox = MyGroupBox("Sort")
        self.sortCombo = QComboBox()
        self.sortCombo.addItems(["Index", "Interval"])
        self.sortGroupBox.layout.addWidget(self.sortCombo)

        self.themeCombo = QComboBox()
        self.themeCombo.addItems(themes.keys())
        self.themeSmoothCheck = QCheckBox("Smooth")
        self.themeGroupBox = MyGroupBox("Theme")
        self.themeGroupBox.layout.addWidget(self.themeCombo)
        self.themeGroupBox.layout.addWidget(self.themeSmoothCheck)

        self.qualityGroupBox = MyGroupBox("PNG Quality")
        self.qualitySlider = QSlider()
        self.qualitySlider.setOrientation(Qt.Orientation.Horizontal)
        self.qualitySlider.setMinimum(25)
        self.qualitySlider.setMaximum(200)
        self.qualitySlider.setValue(100)
        self.qualityGroupBox.layout.addWidget(self.qualitySlider)

        self.leftLayoutBottomLayout = QHBoxLayout()
        self.generateBtn = QPushButton("Generate")

        self.savePNGBtn = QPushButton("Save PNG")
        # self.openGIFBtn = QPushButton('Create GIF')

        # Table stuff
        self.tableContainer = QWidget()
        self.tableLayout = QVBoxLayout(self.tableContainer)
        self.table = KanjiTable()
        self.tableLayout.addWidget(self.table)

        self.fontSizeGroupBox = MyGroupBox("Table Font Size")
        self.fontSizeSlider = QSlider()
        self.fontSizeSlider.setOrientation(Qt.Orientation.Horizontal)
        self.fontSizeSlider.setMinimum(5)
        self.fontSizeSlider.setMaximum(50)
        self.fontSizeGroupBox.layout.addWidget(self.fontSizeSlider)

        self.table.horizontalHeader().setMinimumSectionSize(
            self.fontSizeSlider.minimum()
        )
        self.table.verticalHeader().setMinimumSectionSize(self.fontSizeSlider.minimum())

        # Connect signals to slots
        self.sizeButtonGroup.buttonClicked.connect(self.sizeChanged)
        self.sortCombo.currentIndexChanged.connect(self.somethingChanged)
        self.themeSmoothCheck.stateChanged.connect(self.somethingChanged)
        self.timeTravelGroupBox.toggled.connect(self.somethingChanged)
        self.timeTravelInput.dateTimeChanged.connect(self.somethingChanged)
        self.fieldNamePatternInput.returnPressed.connect(self.somethingChanged)
        self.fieldNamePatternInput.valueChanged.connect(self.somethingChanged)
        self.filterInput.returnPressed.connect(self.somethingChanged)
        self.filterInput.valueChanged.connect(self.somethingChanged)
        self.strongIntervalSpin.textChanged.connect(self.strongIntervalChanged)
        self.themeCombo.currentIndexChanged.connect(self.themeSelectionChanged)
        self.themeSmoothCheck.stateChanged.connect(self.smoothChanged)
        self.groupByComboBox.currentIndexChanged.connect(self.somethingChanged)
        self.specifyColumnsSpin.textChanged.connect(self.sizeChanged)
        self.groupByGroupBox.toggled.connect(self.somethingChanged)

        self.savePNGBtn.clicked.connect(self.takeScreenshot)
        self.generateBtn.clicked.connect(self.populateTable)
        # self.openGIFBtn.clicked.connect(openGIFDialog)
        self.fontSizeSlider.valueChanged.connect(self.fontSizeSliderMoved)

        # Add stuff to leftLayoutMiddleLayout
        self.settingsGroupBox.layout.addWidget(self.fieldNameGroupBox)
        self.settingsGroupBox.layout.addWidget(self.filterGroupBox)
        self.settingsGroupBox.layout.addWidget(self.strongIntervalGroupBox)
        self.settingsGroupBox.layout.addWidget(self.sizeGroupBox)
        self.settingsGroupBox.layout.addWidget(self.groupByGroupBox)
        self.settingsGroupBox.layout.addWidget(self.sortGroupBox)
        self.settingsGroupBox.layout.addWidget(self.timeTravelGroupBox)
        self.settingsGroupBox.layout.addWidget(self.themeGroupBox)
        self.settingsGroupBox.layout.addWidget(self.fontSizeGroupBox)
        self.settingsGroupBox.layout.addWidget(self.qualityGroupBox)

        # Add stuff to leftLayoutBottomLayout
        self.leftLayoutBottomLayout.addWidget(self.savePNGBtn)
        # self.leftLayoutBottomLayout.addWidget(self.openGIFBtn)

        # Add stuff to leftLayout
        self.leftLayout.addWidget(self.middleScroll)
        self.leftLayout.addLayout(self.leftLayoutBottomLayout)

        # Add stuff to main layout
        self.splitter.addWidget(self.leftContainer)
        self.splitter.addWidget(self.tableContainer)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.mainLayout.addWidget(self.splitter)

        # Finishing touches
        self.themeManager.selectedTheme = self.themeCombo.currentText()
        self.themeManager.smooth = self.themeSmoothCheck.isChecked()
        self.themeManager.strongIvl = self.strongIntervalSpin.value()
        self.fitToWidthRadio.click()
        self.fontSizeSliderMoved(12)
        self.fontSizeSlider.setValue(12)

    # TODO use paramter instead of currenttext()?
    def themeSelectionChanged(self, *args, **kwargs) -> None:
        self.themeManager.selectedTheme = self.themeCombo.currentText()
        self.table.updateAllColors(self.themeManager)

    # TODO use paramter instead of value()?
    def strongIntervalChanged(self, *args, **kwargs) -> None:
        self.themeManager.strongIvl = self.strongIntervalSpin.value()
        self.table.updateAllColors(self.themeManager)

    def smoothChanged(self, *args, **kwargs) -> None:
        self.themeManager.smooth = self.themeSmoothCheck.isChecked()
        self.table.updateAllColors(self.themeManager)

    def sizeChanged(self, *args, **kwargs) -> None:
        if self.specifyColumnsRadio.isChecked():
            self.specifyColumnsSpin.setEnabled(True)
        else:
            self.specifyColumnsSpin.setEnabled(False)
        copies = [c.copy() for c in self.table.allCells()]
        self.table.clear()
        self.setTableColumns(len(copies))
        self.table.appendItems(copies)
        self.table.resizeCellsToFitContents()

    def somethingChanged(self, *args, **kwargs) -> None:
        self.populateTable()

    def takeScreenshot(self) -> None:
        self.table.screenshot(self.qualitySlider.value())

    def fontSizeSliderMoved(self, newSize: int) -> None:
        self.table.setFontSize(newSize)
        self.sizeChanged()

    def populateTable(self, timeTravelDatetime: QDateTime = None) -> None:
        self.table.clear()

        if not timeTravelDatetime and self.timeTravelGroupBox.isChecked():
            timeTravelDatetime = self.timeTravelInput.dateTime().toPyDateTime()

        cells = self.getKanjiCells(timeTravelDatetime)
        if not cells:
            self.table.clear()
            self.savePNGBtn.setEnabled(False)
            self.setWindowTitle("Kanji Table (0)")
            return
        self.savePNGBtn.setEnabled(True)

        self.setWindowTitle(
            f"Kanji Table ({len([c for c in cells if isinstance(c, KanjiCell)])})"
        )
        self.setTableColumns(len(cells))
        self.table.appendItems(cells)
        self.table.resizeCellsToFitContents()
        self.table.updateAllColors(self.themeManager)

    def setTableColumns(self, cellCount: int) -> None:
        if self.fitToWidthRadio.isChecked():
            cols = self.table.howManyColsWillFit()
        elif self.specifyColumnsRadio.isChecked():
            cols = self.specifyColumnsSpin.value()
        self.table.setColumnCount(cols)

    def showEvent(self, event) -> None:
        """QWidget.size() has unexpected values until everything is shown so wait until after showing then populate"""
        if not self.hasBeenBuilt:
            self.buildGUI()
            # Qt weirdness means we have to do this with a QTimer instead of calling it directly
            # https://stackoverflow.com/a/56852841/3261260
            QTimer.singleShot(0, self.populateTable)
            self.hasBeenBuilt = True
        # IDK why but sometimes this is necessary (after closing the window then changing themes and stuff)
        self.table.resizeCellsToFitContents()
        super().showEvent(event)

    """
    class GIFDialog(QDialog):
        def manualStartDateToggled(self, isChecked):
            self.startDateInput.setEnabled(isChecked)

        def manualEndDateToggled(self, isChecked):
            self.endDateInput.setEnabled(isChecked)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.layout = QVBoxLayout(self)

            self.startDateGroupBox = MyGroupBox('Start Date')
            self.startDateEarliestRadio = QRadioButton('Earliest Review')
            self.startDateManualRadio = QRadioButton('Manual')
            self.startDateButtonGroup = QButtonGroup()
            self.startDateButtonGroup.addButton(self.startDateEarliestRadio)
            self.startDateButtonGroup.addButton(self.startDateManualRadio)
            self.startDateInput = QDateEdit()
            self.startDateInput.setEnabled(False)  # Enabled if Manual start date is selected
            self.startDateInput.setCalendarPopup(True)
            self.startDateInput.setDate(QDate.currentDate().addDays(-30))
            self.startDateGroupBox.layout.addWidget(self.startDateEarliestRadio)
            self.startDateGroupBox.layout.addWidget(self.startDateManualRadio)
            self.startDateGroupBox.layout.addWidget(self.startDateInput)
            self.layout.addWidget(self.startDateGroupBox)

            self.endDateGroupBox = MyGroupBox('End Date')
            self.endDateTodayRadio = QRadioButton('Today')
            self.endDateLatestRadio = QRadioButton('Latest Review')
            self.endDateManualRadio = QRadioButton('Manual')
            self.endDateButtonGroup = QButtonGroup()
            self.endDateButtonGroup.addButton(self.endDateTodayRadio)
            self.endDateButtonGroup.addButton(self.endDateLatestRadio)
            self.endDateButtonGroup.addButton(self.endDateManualRadio)
            self.endDateInput = QDateEdit()
            self.endDateInput.setEnabled(False)  # Enabled if Manual end date is selected
            self.endDateInput.setCalendarPopup(True)
            self.endDateInput.setDate(QDate.currentDate())
            self.endDateGroupBox.layout.addWidget(self.endDateTodayRadio)
            self.endDateGroupBox.layout.addWidget(self.endDateLatestRadio)
            self.endDateGroupBox.layout.addWidget(self.endDateManualRadio)
            self.endDateGroupBox.layout.addWidget(self.endDateInput)
            self.layout.addWidget(self.endDateGroupBox)

            self.saveGIFBtn = QPushButton('Save')
            self.layout.addWidget(self.saveGIFBtn)

            # Connect signals to slots
            self.saveGIFBtn.clicked.connect(self.createGIF)
            self.startDateManualRadio.toggled.connect(self.manualStartDateToggled)
            self.endDateManualRadio.toggled.connect(self.manualEndDateToggled)

            # Finishing touches
            self.startDateEarliestRadio.click()
            self.endDateLatestRadio.click()

            self.exec()


    def openGIFDialog():
        GIFDialog()


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
    """


def showConfig() -> None:
    mw.kanjiGridWidget.showMaximized()


def setup() -> None:
    mw.kanjiGridWidget = widget = MyApp()
    action = QAction("Kanji Table", mw)
    qconnect(action.triggered, showConfig)
    mw.form.menuTools.addAction(action)


# # Prevent mpv window from showing on Windows machines.
# if ankiUtils.isWin:
#     startupinfo = subprocess.STARTUPINFO()
#     startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
# else:
#     startupinfo = None
gui_hooks.profile_did_open.append(setup)
