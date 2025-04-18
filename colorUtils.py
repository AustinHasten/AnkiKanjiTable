from aqt.qt import QColor

themes = {
    'Classic': list(map(QColor, [
        '#E62E2E', '#E68A2E', '#E6E62E', '#8AE62E', '#2EE62E', '#2EE68A', '#2EE6E6'
    ])),
    'Red': list(map(QColor, [
        '#8C7773', '#996E66', '#A66559', '#B35C4D', '#BF5340', '#CC4A33', '#D94126', '#E63819', '#F22F0D', '#FF2600'
    ])),
    'Purple': list(map(QColor, [
        '#978FA3', '#9685AD', '#947AB8', '#9270C2', '#9066CC', '#8F5CD6', '#8D52E0', '#8B47EB', '#8A3EF4', '#8833FF'
    ])),
    'Dracula': list(map(QColor, [
        '#ff5555', '#ffb86c', '#f1fa8c', '#50fa7b', '#8be9fd', '#ff79c6', '#bd93f9'
    ]))
}


class ThemeManager():
    selectedTheme: str = None
    smooth: bool = False
    strongIvl: int = 0

    def getColor(self, pct: float) -> QColor:
        return getColor(self.selectedTheme, pct / self.strongIvl, self.smooth)


def invertColor(c: QColor) -> QColor:
    return QColor(255 - c.red(), 255 - c.green(), 255 - c.blue())


def interpolateColors(start: QColor, end: QColor, ratio: int) -> QColor:
    r = int(ratio * start.red() + (1 - ratio) * end.red())
    g = int(ratio * start.green() + (1 - ratio) * end.green())
    b = int(ratio * start.blue() + (1 - ratio) * end.blue())
    return QColor(r, g, b)


def getColor(theme: str, pct: float, smooth: bool=False) -> QColor:
    bands = themes[theme]
    startF = (len(bands) - 1) * pct
    start = min(int(startF), len(bands) - 1)
    if smooth:
        end = min(start + 1, len(bands) - 1)
        return interpolateColors(bands[end], bands[start], startF - start)
    else:
        return bands[start]
