import datetime
from aqt.qt import QGroupBox, QHBoxLayout, QVBoxLayout, QWidget

# Too early and your system might throw an exception when trying to convert to unix epoch milliseconds so let's use Anki's initial release date
minDatetime = datetime.datetime(year=2006, month=10, day=5)
# Too late and your system might throw an exception when trying to convert to unix epoch milliseconds so we'll just use the year 2100
maxDatetime = datetime.datetime(year=2100, month=1, day=1)


def dateRange(startDate, endDate):
    duration = (endDate - startDate).days
    for d in range(duration + 1):
        yield startDate + datetime.timedelta(days=d)


class MyGroupBox(QGroupBox):
    ''' Smaller margins/padding and has a layout by default '''

    def __init__(self, label):
        super().__init__(label)
        self.containerWidget = QWidget()
        self.dummyLayout = QHBoxLayout(self)  # Could be anything, it just holds the single container widget
        self.dummyLayout.addWidget(self.containerWidget)
        self.dummyLayout.setContentsMargins(0, 0, 0, 0)

        self.layout = QVBoxLayout(self.containerWidget)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.setStyleSheet('padding:0px;')


queries = {
    'LatestReviewForCardOnDate': """
        SELECT
            max(id), ivl
        FROM
            revlog
        WHERE
            cid = {cid}
            AND (id / 1000) <= {date}
    """,
    'LatestReviewForDeck': """
        SELECT
            max(r.id)/1000
        FROM
            revlog r
            JOIN cards c on c.id = r.cid
        WHERE
            c.did = {did}
    """,
    'EarliestReviewForDeck': """
        SELECT
            min(r.id)/1000
        FROM
            revlog r
            JOIN cards c on c.id = r.cid
        WHERE
            c.did = {did}
    """,
}
