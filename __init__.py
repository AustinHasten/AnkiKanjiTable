# NOTES
# The interval on the most recent review is not always equal to the interval on the card.
# Any rescheduling (i.e. via FSRS Helper) can change the interval on the card without changing the interval in the revlog.
# Just something to keep in mind. Time travel is still accurate to the time you travel to -
#   on the day of the revlog, that WAS the interval after the review. So this is almost desirous?
#
# The time it takes to save the png is 70 times larger than the steps leading up to it so don't waste time trying to optimize that much
# ex. 0.3s vs 24.3s
# NOTE the way I save pngs has changed so see if this has changed ^^^
#
# Any user-input times need to be converted to utc with datetime.astimezone(localTZ) because DB is in utc
#
# Foreground colors are currently ignored, we just invert the background. Change that?

# TODO
#   Grid lines are different color at very bottom??
#   Table totally borks if you switch from dark/light mode and vice versa
#   Add more stuff to context menu?
#   Make sure times are being converted to the correct time zones
#   Make stuff into enums like which size option is selected and junk
# GIF
#   Add linux support
#   Clear tmpDir between gif runs to prevent old pictures from getting in the gif
#   resize instead of fail if table is too big for gif

# TODO?
#   Use generate button instead of repopulating all the time?
#   Generate themes from a start and end color
# GIF
#   Skip days where no reviews were done
#   Add configurable info to overlay besides just date. New cards done, reviews done, time taken, etc.
#   Hold last frame for multiple frames
#   Find a way to move createGIF to table class

# import os
import re
import fnmatch
# import datetime
import math
# import subprocess
import webbrowser
import unicodedata

from aqt import mw, gui_hooks, dialogs
from aqt.qt import Qt, qconnect, QColor, QBrush, QTableWidgetItem, QTableWidget, QAbstractItemView, QFileDialog, QStandardPaths, QStyle, QSize, QWidget, QHBoxLayout, QSplitter, QVBoxLayout, QComboBox, QScrollArea, QSpinBox, QButtonGroup, QRadioButton, QDateTime, QDateTimeEdit, QPushButton, QCheckBox, QSlider, QAction, QImage, QLineEdit, QTimer, pyqtSignal, QMenu, QGuiApplication
# QPixMap, QDate, QSizePolicy, QDateEdit, QLabel, QPainter, QPainterPath, QFontDatabase, QDialog
# from aqt.utils import showCritical
# from anki import utils as ankiUtils

from .utils import queries, MyGroupBox  # dateRange, maxDatetime, minDatetime
from .colorUtils import themes, getColor, invertColor
from .data import levelSystems

import sys

# exe = os.path.join(os.path.dirname(__file__), 'ffmpeg.exe')
# localTZ = datetime.datetime.utcnow().astimezone().tzinfo  # https://stackoverflow.com/a/39079819

cjk_re = re.compile("CJK (UNIFIED|COMPATIBILITY) IDEOGRAPH")


def isKanji(unichar):
    return bool(cjk_re.match(unicodedata.name(unichar, "")))


def browserSearch(searchText):
    browser = dialogs.open("Browser", mw)
    browser.form.searchEdit.lineEdit().setText(searchText)
    browser.onSearchActivated()


class MyQTableWidget(QTableWidget):
    defaultCSS = '''
        QTableWidget {
            gridline-color: #2D2D2D;
        }
    '''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.currentRowIdx = 0
        self.currentColumnIdx = 0
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self.setStyleSheet(self.defaultCSS)

    def mostMatureClicked(self, cid):
        browserSearch(f'cid:{cid}')

    def allMatchingClicked(self, cids):
        browserSearch(f'cid:{",".join(cids)}')

    def addClicked(self, kanji):
        QGuiApplication.clipboard().setText(kanji)
        addDialog = dialogs.open('AddCards', mw)

    def showContextMenu(self, point):
        cell = self.itemAt(point)
        if not isinstance(cell, KanjiCell):
            return

        menu = QMenu()

        actions = []

        if cell.data['ivl'] is not None:
            a = QAction(f'Most Mature Card ({cell.data["ivl"]}d)')
            a.triggered.connect(lambda _: self.mostMatureClicked(cell.data['cid']))
            actions.append(a)

            a = QAction(f'All Matching Cards ({len(cell.data["allcids"])})')
            a.triggered.connect(lambda _: self.allMatchingClicked(cell.data["allcids"]))
            actions.append(a)
        else:
            a = QAction('Copy to clipboard and open Add Card dialog')
            a.triggered.connect(lambda _: self.addClicked(cell.text()))
            actions.append(a)

        for action in actions:
            menu.addAction(action)

        menu.exec(self.mapToGlobal(point))

    def appendItem(self, cell):
        if isinstance(cell, LevelCell):
            # Merge unused cells to get rid of extra grid lines
            if self.currentColumnIdx < self.columnCount():
                self.setSpan(self.currentRowIdx, self.currentColumnIdx, 1, (self.columnCount() - self.currentColumnIdx))

            # LevelCells are intended to take up an entire row so if we are not at the start of a row, go to the next one
            if self.currentColumnIdx != 0:
                self.currentRowIdx += 1
                self.currentColumnIdx = 0

            # Add rows as needed
            if self.currentRowIdx >= self.rowCount():
                self.insertRow(self.rowCount())

            self.setSpan(self.currentRowIdx, self.currentColumnIdx, 1, self.columnCount())
            self.setItem(self.currentRowIdx, self.currentColumnIdx, cell)
            self.currentRowIdx += 1

            return

        if isinstance(cell, KanjiCell):
            # Rollover to the next row
            if self.currentColumnIdx >= self.columnCount():
                self.currentRowIdx += 1
                self.currentColumnIdx = 0

            # Add rows as needed
            if self.currentRowIdx >= self.rowCount():
                self.insertRow(self.rowCount())

            self.setItem(self.currentRowIdx, self.currentColumnIdx, cell)
            self.currentColumnIdx += 1

            return

        return NotImplementedError

    def appendItems(self, cells):
        for cell in cells:
            self.appendItem(cell)

    def clear(self, *args, **kwargs):
        super().clear(*args, **kwargs)

        # Remove all rows and columns to get rid of any spans that have been set
        self.setRowCount(0)
        self.setColumnCount(0)

        self.currentRowIdx = 0
        self.currentColumnIdx = 0


class MyQLineEdit(QLineEdit):
    ''' QLineEdit that emits a valueChanged signal if the value is changed between focusIn and focusOut '''
    valueChanged = pyqtSignal()

    def focusInEvent(self, event):
        self.previousText = self.text()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        if self.previousText and self.previousText != self.text():
            self.valueChanged.emit()
        super().focusOutEvent(event)


class MyQTableWidgetItem(QTableWidgetItem):
    def setColors(self, fg=None, bg=None):
        if fg is None and bg is None:
            return
        if fg is None:
            fg = QBrush(invertColor(bg))
        elif bg is None:
            bg = QBrush(invertColor(fg))
        else:
            fg = QBrush(fg)
            bg = QBrush(bg)
        self.setForeground(fg)
        self.setBackground(bg)

    def updateColors(self, *args, **kwargs):
        pass

    def clicked(self):
        pass


class LevelCell(MyQTableWidgetItem):
    fgColor = QColor('#FFFFFF')
    bgColor = QColor('#2D2D2D')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setColors(self.fgColor, self.bgColor)

    def copy(self):
        return LevelCell(self.text())


class KanjiCell(MyQTableWidgetItem):
    seenFGColor = QColor('#000000')
    unseenFGColor = QColor('#000000')
    unseenBGColor = QColor('#FFFFFF')
    missingBGColor = QColor('#000000')
    missingFGColor = QColor('#E62E2E')

    def __init__(self, text, data={}, *args, **kwargs):
        super().__init__(text, *args, **kwargs)
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.data = data

    def updateColors(self, themeManager):
        if not self.data['cid']:
            self.setColors(self.missingFGColor, self.missingBGColor)
        # ivl should be None/0 if unseen, nonzero if seen
        elif self.data['ivl']:
            bgColor = themeManager.getColor(self.data['ivl'])
            self.setColors(self.seenFGColor, bgColor)
        else:
            self.setColors(self.unseenFGColor, self.unseenBGColor)

    def copy(self):
        c = KanjiCell(self.text(), self.data)
        c.setColors(self.foreground().color(), self.background().color())
        return c

    def clicked(self):
        webbrowser.open(f'https://jisho.org/search/{self.text()} %23kanji')

    def __eq__(self, other):
        if isinstance(other, str):
            return self.text() == other
        if isinstance(other, KanjiCell):
            return self.text() == other.character

        raise NotImplementedError

    def __gt__(self, other):
        # if isinstance(other, int):
        #     return self.sortOrder > other
        if isinstance(other, KanjiCell):
            return self.sortOrder > other.sortOrder

        raise NotImplementedError

    def __ge__(self, other):
        # if isinstance(other, int):
        #     return self.sortOrder >= other
        if isinstance(other, KanjiCell):
            return self.sortOrder >= other.sortOrder

        raise NotImplementedError

    def __lt__(self, other):
        # if isinstance(other, int):
        #     return self.sortOrder < other
        if isinstance(other, KanjiCell):
            return self.sortOrder < other.sortOrder

        raise NotImplementedError

    def __le__(self, other):
        # if isinstance(other, int):
        #     return self.sortOrder <= other
        if isinstance(other, KanjiCell):
            return self.sortOrder <= other.sortOrder

        raise NotImplementedError


class KanjiTable(MyQTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.itemClicked.connect(self.cellClicked)

    def cellClicked(self, cell):
        cell.clicked()

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

    def howManyColsWillFit(self):
        tileWidth = self.font().pointSize() * 2
        containerWidth = self.width()
        if (tileWidth * self.rowCount()) > self.height():
            scrollBarWidth = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
            containerWidth -= scrollBarWidth
        return math.floor(containerWidth / tileWidth)

    def sizeToShowAll(self):
        newWidth = self.horizontalHeader().sectionSize(0) * self.columnCount()
        newHeight = self.verticalHeader().sectionSize(0) * self.rowCount()
        return QSize(newWidth, newHeight)

    def setup(self):
        self.hideScrollBars()
        oldSize = self.size()
        self.resize(self.sizeToShowAll())
        return oldSize

    def cleanup(self, oldSize):
        self.resize(oldSize)
        self.showScrollBars()

    def screenshot(self, cellResolution=100):
        oldSize = self.setup()
        fileName = QFileDialog.getSaveFileName(
            self,
            'Save Page',
            QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DesktopLocation)[0],
            'Portable Network Graphics (*.png)'
        )[0]

        actualWidth = self.width()
        actualHeight = self.height()
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
                if cell:
                    yield cell

    def updateAllColors(self, themeManager):
        for cell in self.allItems():
            cell.updateColors(themeManager)


class ThemeManager():
    selectedTheme = None
    smooth = False
    strongIvl = 0

    def getColor(self, pct):
        return getColor(self.selectedTheme, pct / self.strongIvl, self.smooth)


class KanjiData:
    defaults = {
        'ivl': None,
        'cid': None,
        'levelIndex': 0,
    }

    def __init__(self, kanji, data={}):
        self.kanji = kanji
        self.data = self.defaults | data
        if 'allcids' not in self.data:
            self.data['allcids'] = set()
            if self.data['cid']:
                self.data['allcids'].add(str(self.data['cid']))
        # If ivl is < 0, it's in seconds rather than days -
        # we'll round that to 1 day for convenience
        if self.data['ivl'] is not None and self.data['ivl'] < 0:
            self.data['ivl'] = 1

    @classmethod
    def getTimeTravelIvl(cls, cid, timeTravelDateTime):
        qry = queries['LatestReviewForCardOnDate'].format(cid=cid, date=timeTravelDateTime.timestamp())
        ivl = mw.col.db.first(qry)[1]
        # Card had not been seen yet at timeTravelDateTime
        if ivl is None:
            return 0
        return ivl

    @classmethod
    def fromCard(cls, kanji, card, timeTravelDatetime=None):
        ivl = card.ivl
        if timeTravelDatetime:
            ivl = cls.getTimeTravelIvl(card.id, timeTravelDatetime)
        # If ivl is < 0, it's in seconds rather than days -
        # we'll round that to 1 day for convenience
        if ivl < 0:
            ivl = 1

        return cls(kanji, {'ivl': ivl, 'cid': card.id})

    def kanjiCell(self):
        return KanjiCell(self.kanji, self.data)

    def __gt__(self, other):
        # if isinstance(other, int):
        #     return self.data.get('ivl', 0) > other
        if isinstance(other, KanjiData):
            if self.data['ivl'] is None and other.data['ivl'] is not None:
                return False
            return self.data['ivl'] < other.data['ivl']

        raise NotImplementedError

    def __lt__(self, other):
        # if isinstance(other, int):
        #     return self.data.get('ivl', 0) < other
        if isinstance(other, KanjiData):
            if self.data['ivl'] is None and other.data['ivl'] is not None:
                return True
            return self.data['ivl'] < other.data['ivl']

        raise NotImplementedError


class KanjiDataDict(dict):
    def __setitem__(self, kanjiChar, kanjiData):
        if kanjiChar not in self:
            dict.__setitem__(self, kanjiChar, kanjiData)
        # One KanjiData is less than the other if it has a shorter ivl
        # TODO Move this all to like an update() function on KanjiData?
        elif self[kanjiChar] < kanjiData:
            kanjiData.data['allcids'].update(self[kanjiChar].data['allcids'])
            dict.__setitem__(self, kanjiChar, kanjiData)

    def updateFromCard(self, card, kanjiChars, timeTravelDatetime):
        for kanjiChar in kanjiChars:
            self[kanjiChar] = KanjiData.fromCard(kanjiChar, card, timeTravelDatetime)

    def toKanjiCells(self, sortFunc):
        return [kanjiData.kanjiCell() for kanjiData in sorted(self.values(), key=sortFunc)]

    def splitIntoLevels(self, levelSystem):
        '''
        Take KanjiDataDict and return
        {
            levelName: KanjiDataDict {
                kanjiChar: KanjiData
            },
            ...
        }
        '''
        r = {}
        for levelName, levelList in levelSystem.levels.items():
            r[levelName] = KanjiDataDict()
            for index, kanjiChar in enumerate(levelList):
                r[levelName][kanjiChar] = KanjiData(kanjiChar, {'levelIndex': index})
        r[f'Not in {levelSystem.name}'] = KanjiDataDict()
        for kanjiData in self.values():
            foundLevel, foundIdx = levelSystem.findCharacter(kanjiData.kanji)
            if foundLevel:
                r[foundLevel][kanjiData.kanji] = kanjiData
            else:
                r[f'Not in {levelSystem.name}'][kanjiData.kanji] = kanjiData
        return r


class MyApp(QWidget):
    themeManager = ThemeManager()

    def getMatchingKanjiFromNote(self, note):
        fieldNamePattern = self.fieldNamePatternInput.text()
        matchingFields = [f for f in note.keys() if fnmatch.fnmatch(f, fieldNamePattern)]
        for matchingField in matchingFields:
            for char in note[matchingField]:
                if isKanji(char):
                    yield char

    def getMatchingCards(self):
        for cid in mw.col.find_cards(self.filterInput.text()):
            yield mw.col.get_card(cid)

    def getKanjiCells(self, timeTravelDatetime=None):
        kanjiDatas = KanjiDataDict()

        for card in self.getMatchingCards():
            kanjiChars = self.getMatchingKanjiFromNote(card.note())
            kanjiDatas.updateFromCard(card, kanjiChars, timeTravelDatetime)

        # TODO Make these functions be associated data of the combobox options
        if self.sortCombo.currentText() == 'Interval':
            def sortFunc(kanjiData):
                if kanjiData.data['ivl'] is None:
                    return sys.maxsize
                else:
                    return -kanjiData.data['ivl']
        elif self.sortCombo.currentText() == 'Index':
            sortFunc = lambda _: _.data.get('levelIndex', 0)

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

    def buildGUI(self):
        self.mainLayout = QHBoxLayout(self)

        self.splitter = QSplitter()

        self.leftContainer = QWidget()
        self.leftLayout = QVBoxLayout(self.leftContainer)

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
        self.specifyColumnsRadio = QRadioButton('Specify Columns')
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
        self.timeTravelGroupBox = MyGroupBox('Time Travel To')
        self.timeTravelGroupBox.layout.addWidget(self.timeTravelInput)
        self.timeTravelGroupBox.setCheckable(True)
        self.timeTravelGroupBox.setChecked(False)

        self.groupByGroupBox = MyGroupBox('Group By')
        self.groupByGroupBox.setCheckable(True)
        self.groupByComboBox = QComboBox()
        self.groupByComboBox.addItems(levelSystems.keys())
        self.groupByGroupBox.layout.addWidget(self.groupByComboBox)

        self.sortGroupBox = MyGroupBox('Sort')
        self.sortCombo = QComboBox()
        self.sortCombo.addItems(['Index', 'Interval'])
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
        self.fontSizeGroupBox.layout.addWidget(self.fontSizeSlider)

        self.table.horizontalHeader().setMinimumSectionSize(self.fontSizeSlider.minimum())
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
    def themeSelectionChanged(self, *args, **kwargs):
        self.themeManager.selectedTheme = self.themeCombo.currentText()
        self.table.updateAllColors(self.themeManager)

    # TODO use paramter instead of value()?
    def strongIntervalChanged(self, *args, **kwargs):
        self.themeManager.strongIvl = self.strongIntervalSpin.value()
        self.table.updateAllColors(self.themeManager)

    def smoothChanged(self, *args, **kwargs):
        self.themeManager.smooth = self.themeSmoothCheck.isChecked()
        self.table.updateAllColors(self.themeManager)

    def sizeChanged(self, *args, **kwargs):
        if self.specifyColumnsRadio.isChecked():
            self.specifyColumnsSpin.setEnabled(True)
        else:
            self.specifyColumnsSpin.setEnabled(False)
        copies = [c.copy() for c in self.table.allItems()]
        self.table.clear()
        self.setTableColumns(len(copies))
        self.table.appendItems(copies)
        self.table.resizeCellsToFitContents()

    def somethingChanged(self, *args, **kwargs):
        self.populateTable()

    def takeScreenshot(self):
        self.table.screenshot(self.qualitySlider.value())

    def fontSizeSliderMoved(self, newSize):
        self.table.setFontSize(newSize)
        self.sizeChanged()

    def populateTable(self, timeTravelDatetime=None):
        self.table.clear()

        if not timeTravelDatetime and self.timeTravelGroupBox.isChecked():
            timeTravelDatetime = self.timeTravelInput.dateTime().toPyDateTime()

        cells = self.getKanjiCells(timeTravelDatetime)
        if not cells:
            self.table.setColumnCount(0)
            self.table.setRowCount(0)
            self.savePNGBtn.setEnabled(False)
            self.setWindowTitle('Kanji Table (0)')
            return
        self.savePNGBtn.setEnabled(True)

        self.setWindowTitle(f'Kanji Table ({len([c for c in cells if isinstance(c, KanjiCell)])})')
        self.setTableColumns(len(cells))
        self.table.appendItems(cells)
        self.table.resizeCellsToFitContents()
        self.table.updateAllColors(self.themeManager)

    def setTableColumns(self, cellCount):
        if self.fitToWidthRadio.isChecked():
            cols = self.table.howManyColsWillFit()
        elif self.specifyColumnsRadio.isChecked():
            cols = self.specifyColumnsSpin.value()
        self.table.setColumnCount(cols)

    def showEvent(self, event):
        ''' QWidget.size() has unexpected values until everything is shown so wait until after showing then populate '''
        self.buildGUI()
        super().showEvent(event)
        # Qt weirdness means we have to do this with a QTimer instead of calling it directly
        # https://stackoverflow.com/a/56852841/3261260
        QTimer.singleShot(0, self.populateTable)

    '''
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
