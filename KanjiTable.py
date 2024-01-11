import math
import webbrowser

from aqt import dialogs, mw
from aqt.qt import (
    QAbstractItemView,
    QAction,
    QBrush,
    QColor,
    QFileDialog,
    QGuiApplication,
    QImage,
    QMenu,
    QSize,
    QStandardPaths,
    QStyle,
    Qt,
    QTableWidget,
    QTableWidgetItem
)

from .colorUtils import invertColor
from .utils import queries


# TODO Find a better spot for this
def browserSearch(searchText):
    browser = dialogs.open("Browser", mw)
    browser.form.searchEdit.lineEdit().setText(searchText)
    browser.onSearchActivated()


class KanjiTable(QTableWidget):
    defaultCSS = '''
        QTableWidget {
            gridline-color: #2D2D2D;
        }
    '''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.itemClicked.connect(self.cellClicked)

        self.currentRowIdx = 0
        self.currentColumnIdx = 0
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self.setStyleSheet(self.defaultCSS)

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

    def showContextMenu(self, point):
        cell = self.itemAt(point)
        if not isinstance(cell, KanjiCell):
            return

        menu = QMenu()

        actions = []

        a = QAction(f'Level Index {cell.data["levelIndex"]}')
        actions.append(a)

        if cell.data['ivl'] is not None:
            a = QAction(f'Most Mature Card ({cell.data["ivl"]}d)')
            a.triggered.connect(cell.mostMatureClicked)
            actions.append(a)

            a = QAction(f'All Matching Cards ({len(cell.data["allcids"])})')
            a.triggered.connect(cell.allMatchingClicked)
            actions.append(a)
        else:
            a = QAction('Copy to clipboard and open Add Card dialog')
            a.triggered.connect(cell.addClicked)
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


class MyQTableWidgetItem(QTableWidgetItem):
    def setColors(self, fg=None, bg=None):
        if fg is None and bg is None:
            raise Exception('Must provide either fg or bg')
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

    def mostMatureClicked(self, cid):
        browserSearch(f'cid:{self.data["cid"]}')

    def allMatchingClicked(self, cids):
        browserSearch(f'cid:{",".join(self.data["allcids"])}')

    def addClicked(self, kanji):
        QGuiApplication.clipboard().setText(self.text())
        addDialog = dialogs.open('AddCards', mw)


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

    def keepMostMature(self, other):
        if self < other:
            other.data['allcids'].update(self.data['allcids'])
            other.data['levelIndex'] = self.data['levelIndex']
            self.data = other.data

    def __gt__(self, other):
        if isinstance(other, KanjiData):
            if self.data['ivl'] is None and other.data['ivl'] is not None:
                return False
            return self.data['ivl'] < other.data['ivl']

        raise NotImplementedError

    def __lt__(self, other):
        if isinstance(other, KanjiData):
            if self.data['ivl'] is None and other.data['ivl'] is not None:
                return True
            return self.data['ivl'] < other.data['ivl']

        raise NotImplementedError


class KanjiDataDict(dict):
    def __setitem__(self, kanjiChar, kanjiData):
        if kanjiChar not in self:
            dict.__setitem__(self, kanjiChar, kanjiData)
        else:
            self[kanjiChar].keepMostMature(kanjiData)

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
                r[foundLevel][kanjiData.kanji].keepMostMature(kanjiData)
            else:
                r[f'Not in {levelSystem.name}'][kanjiData.kanji] = kanjiData
        return r
