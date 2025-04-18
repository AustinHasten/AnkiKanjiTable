import math
import webbrowser
from typing import Callable, Generator

from aqt import dialogs, mw
from aqt.qt import (
    QAbstractItemView,
    QAction,
    QBrush,
    QColor,
    QDateTime,
    QFileDialog,
    QGuiApplication,
    QImage,
    QMenu,
    QPoint,
    QSize,
    QStandardPaths,
    QStyle,
    Qt,
    QTableWidget,
    QTableWidgetItem,
)

from .colorUtils import ThemeManager, invertColor
from .data import LevelSystem
from .utils import queries


# TODO Find a better spot for this
def browserSearch(searchText: str) -> None:
    browser = dialogs.open("Browser", mw)
    browser.form.searchEdit.lineEdit().setText(searchText)
    browser.onSearchActivated()


class MyQTableWidgetItem(QTableWidgetItem):
    def setColors(self, fg: QColor = None, bg: QColor = None) -> None:
        if fg is None and bg is None:
            raise Exception("Must provide either fg or bg")
        if fg is None:
            fg = QBrush(invertColor(bg))
        elif bg is None:
            bg = QBrush(invertColor(fg))
        else:
            fg = QBrush(fg)
            bg = QBrush(bg)
        self.setForeground(fg)
        self.setBackground(bg)

    def updateColors(self, *args, **kwargs) -> None:
        pass

    def clicked(self) -> None:
        pass


class KanjiCell(MyQTableWidgetItem):
    seenFGColor: QColor = QColor("#000000")
    unseenFGColor: QColor = QColor("#000000")
    unseenBGColor: QColor = QColor("#FFFFFF")
    missingBGColor: QColor = QColor("#000000")
    missingFGColor: QColor = QColor("#E62E2E")

    def __init__(self, text: str, data: dict = {}, *args, **kwargs) -> None:
        super().__init__(text, *args, **kwargs)
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.data = data

    def updateColors(self, themeManager: ThemeManager) -> None:
        if not self.data["cid"]:
            self.setColors(self.missingFGColor, self.missingBGColor)
        # ivl should be None/0 if unseen, nonzero if seen
        elif self.data["ivl"]:
            bgColor = themeManager.getColor(self.data["ivl"])
            self.setColors(self.seenFGColor, bgColor)
        else:
            self.setColors(self.unseenFGColor, self.unseenBGColor)

    def copy(self):
        c = KanjiCell(self.text(), self.data)
        c.setColors(self.foreground().color(), self.background().color())
        return c

    def clicked(self) -> None:
        webbrowser.open(f"https://jisho.org/search/{self.text()} %23kanji")

    def mostMatureClicked(self) -> None:
        browserSearch(f'cid:{self.data["cid"]}')

    def allMatchingClicked(self) -> None:
        browserSearch(f'cid:{",".join(self.data["allcids"])}')

    def addClicked(self) -> None:
        QGuiApplication.clipboard().setText(self.text())
        addDialog = dialogs.open("AddCards", mw)


class KanjiTable(QTableWidget):
    """It is what it sounds like"""

    defaultCSS: str = """
        QTableWidget {
            gridline-color: #2D2D2D;
        }
    """

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

    def cellClicked(self, cell: MyQTableWidgetItem) -> None:
        """Call the cell's clicked method, whatever that may be"""
        cell.clicked()

    def setFontSize(self, newSize: int) -> None:
        """Set the table's font size and resize all rows/cols to fit that new size size"""
        f = self.font()
        f.setPointSize(newSize)
        self.setFont(f)
        self.resizeCellsToFitContents()

    def resizeCellsToFitContents(self) -> None:
        """Resize all rows/cols to squarely fit one character at the current font size"""
        tileWidth = self.font().pointSize() * 2
        for c in range(self.columnCount()):
            self.setColumnWidth(c, tileWidth)
        for r in range(self.rowCount()):
            self.setRowHeight(r, tileWidth)

    def howManyColsWillFit(self) -> int:
        """At the current font size/tile size, how many tiles will fit in the width of the table"""
        tileWidth = self.font().pointSize() * 2
        containerWidth = self.width()
        if (tileWidth * self.rowCount()) > self.height():
            scrollBarWidth = self.style().pixelMetric(
                QStyle.PixelMetric.PM_ScrollBarExtent
            )
            containerWidth -= scrollBarWidth
        return math.floor(containerWidth / tileWidth)

    def sizeToShowAll(self) -> QSize:
        """The size that the table would have to be to show all tiles with no scrolling"""
        newWidth = self.horizontalHeader().sectionSize(0) * self.columnCount()
        newHeight = self.verticalHeader().sectionSize(0) * self.rowCount()
        return QSize(newWidth, newHeight)

    def prepareForScreenshot(self) -> QSize:
        """Hide the scrollbars, resize the table to show all tiles while holding onto the current size to restore it later"""
        self.hideScrollBars()
        oldSize = self.size()
        self.resize(self.sizeToShowAll())
        return oldSize

    def cleanupAfterScreenshot(self, oldSize: QSize) -> None:
        """Restore the table's previous size and show the scrollbars"""
        self.resize(oldSize)
        self.showScrollBars()

    def screenshot(self, cellResolution: int = 100) -> None:
        """Save a screenshot of the entire table"""
        oldSize = self.prepareForScreenshot()
        fileName = QFileDialog.getSaveFileName(
            self,
            "Save Page",
            QStandardPaths.standardLocations(
                QStandardPaths.StandardLocation.DesktopLocation
            )[0],
            "Portable Network Graphics (*.png)",
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

        image.save(fileName, b"PNG")

        self.cleanup(oldSize)

    def hideScrollBars(self) -> None:
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def showScrollBars(self) -> None:
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def allCells(self) -> Generator[KanjiCell, None, None]:
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                cell = self.item(r, c)
                if cell:
                    yield cell

    def updateAllColors(self, themeManager: ThemeManager) -> None:
        for cell in self.allCells():
            cell.updateColors(themeManager)

    def showContextMenu(self, point: QPoint) -> None:
        cell = self.itemAt(point)
        if not isinstance(cell, KanjiCell):
            return

        menu = QMenu()

        actions = []

        if cell.data["ivl"] is not None:
            a = QAction(f'Most Mature Card ({cell.data["ivl"]}d)')
            a.triggered.connect(cell.mostMatureClicked)
            actions.append(a)

            a = QAction(f'All Matching Cards ({len(cell.data["allcids"])})')
            a.triggered.connect(cell.allMatchingClicked)
            actions.append(a)
        else:
            a = QAction("Copy to clipboard and open Add Card dialog")
            a.triggered.connect(cell.addClicked)
            actions.append(a)

        for action in actions:
            menu.addAction(action)

        menu.exec(self.mapToGlobal(point))

    def appendItem(self, cell: MyQTableWidgetItem) -> None:
        if isinstance(cell, LevelCell):
            # Merge unused cells to get rid of extra grid lines
            if self.currentColumnIdx < self.columnCount():
                self.setSpan(
                    self.currentRowIdx,
                    self.currentColumnIdx,
                    1,
                    (self.columnCount() - self.currentColumnIdx),
                )

            # LevelCells are intended to take up an entire row so if we are not at the start of a row, go to the next one
            if self.currentColumnIdx != 0:
                self.currentRowIdx += 1
                self.currentColumnIdx = 0

            # Add rows as needed
            if self.currentRowIdx >= self.rowCount():
                self.insertRow(self.rowCount())

            self.setSpan(
                self.currentRowIdx, self.currentColumnIdx, 1, self.columnCount()
            )
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

    def appendItems(self, cells: list[MyQTableWidgetItem]) -> None:
        for cell in cells:
            self.appendItem(cell)

    def clear(self, *args, **kwargs) -> None:
        super().clear(*args, **kwargs)

        # Remove all rows and columns to get rid of any spans that have been set
        self.setRowCount(0)
        self.setColumnCount(0)

        self.currentRowIdx = 0
        self.currentColumnIdx = 0


class LevelCell(MyQTableWidgetItem):
    fgColor: QColor = QColor("#FFFFFF")
    bgColor: QColor = QColor("#2D2D2D")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setColors(self.fgColor, self.bgColor)

    def copy(self):
        return LevelCell(self.text())


class KanjiData:
    _defaults = {
        "ivl": None,
        "cid": None,
        "levelIndex": 0,
    }

    def __init__(self, kanji: str, data={}) -> None:
        self.kanji = kanji
        self.data = self._defaults | data
        if "allcids" not in self.data:
            self.data["allcids"] = set()
            if self.data["cid"]:
                self.data["allcids"].add(str(self.data["cid"]))
        # If ivl is < 0, it's in seconds rather than days -
        # we'll round that to 1 day for convenience
        if self.data["ivl"] is not None and self.data["ivl"] < 0:
            self.data["ivl"] = 1

    @classmethod
    def getTimeTravelIvl(cls, cid: str, timeTravelDateTime: QDateTime) -> int:
        qry = queries["LatestReviewForCardOnDate"].format(
            cid=cid, date=timeTravelDateTime.timestamp()
        )
        ivl = mw.col.db.first(qry)[1]
        # Card had not been seen yet at timeTravelDateTime
        if ivl is None:
            return 0
        return ivl

    @classmethod
    def fromCard(
        cls, kanji: str, card, timeTravelDatetime: QDateTime = None
    ) -> KanjiCell:
        ivl = card.ivl
        if timeTravelDatetime:
            ivl = cls.getTimeTravelIvl(card.id, timeTravelDatetime)
        # If ivl is < 0, it's in seconds rather than days -
        # we'll round that to 1 day for convenience
        if ivl < 0:
            ivl = 1

        return cls(kanji, {"ivl": ivl, "cid": card.id})

    def kanjiCell(self) -> KanjiCell:
        return KanjiCell(self.kanji, self.data)

    def keepMostMature(self, other: KanjiCell) -> None:
        self.data["allcids"].update(other.data["allcids"])
        if self < other:
            self.data["ivl"] = other.data["ivl"]
            self.data["cid"] = other.data["cid"]

    def __gt__(self, other):
        if isinstance(other, KanjiData):
            if self.data["ivl"] is None and other.data["ivl"] is not None:
                return False
            return self.data["ivl"] < other.data["ivl"]

        raise NotImplementedError

    def __lt__(self, other):
        if isinstance(other, KanjiData):
            if self.data["ivl"] is None and other.data["ivl"] is not None:
                return True
            return self.data["ivl"] < other.data["ivl"]


class KanjiDataDict(dict):
    def __setitem__(self, kanjiChar: str, kanjiData: KanjiData) -> None:
        if kanjiChar not in self:
            dict.__setitem__(self, kanjiChar, kanjiData)
        else:
            self[kanjiChar].keepMostMature(kanjiData)

    def updateFromCard(
        self, card, kanjiChars: list[str], timeTravelDatetime: QDateTime
    ) -> None:
        for kanjiChar in kanjiChars:
            self[kanjiChar] = KanjiData.fromCard(kanjiChar, card, timeTravelDatetime)

    def toKanjiCells(self, sortFunc: Callable) -> list[KanjiCell]:
        return [
            kanjiData.kanjiCell() for kanjiData in sorted(self.values(), key=sortFunc)
        ]

    def splitIntoLevels(self, levelSystem: LevelSystem):
        """
        Take KanjiDataDict and return {
            levelName: KanjiDataDict,
            ...
        }
        """
        r = {}
        for levelName, levelList in levelSystem.levels.items():
            r[levelName] = KanjiDataDict()
            for index, kanjiChar in enumerate(levelList):
                r[levelName][kanjiChar] = KanjiData(kanjiChar, {"levelIndex": index})
        r[f"Not in {levelSystem.name}"] = KanjiDataDict()
        for kanjiData in self.values():
            foundLevel, foundIdx = levelSystem.findCharacter(kanjiData.kanji)
            if foundLevel:
                r[foundLevel][kanjiData.kanji].keepMostMature(kanjiData)
            else:
                r[f"Not in {levelSystem.name}"][kanjiData.kanji] = kanjiData
        return r
