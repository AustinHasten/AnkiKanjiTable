# AnkiKanjiTable
![image](https://github.com/AustinHasten/AnkiKanjiTable/assets/16011612/0a12f3d9-33c4-4f3f-a868-e127c16187c4)

Visualize your progress by seeing your kanji cards in a pretty table with their maturity indicated by their color.

Notes:
* You can click on a cell to open that kanji's details in Jisho.
* You can right click on a cell to get more options, like opening the card in the Anki Browser window, etc.
* If the field you select has more than one kanji in it, a tile will be created for each of those kanji. If the same kanji is found on multiple cards, the longest interval on those cards will determine the color of the card. i.e. if you have a card with "作家" with an interval of 1 day and a card with "国家" with an interval of 1 week, the tile for "家" will use the interval of 1 week to determine its color.
* When using Group By, any kanji that are in the selected list that you do not have cards for will appear with a black background and red foreground.
* The Filter setting uses the same search format as Anki's Browser window (https://docs.ankiweb.net/searching.html)
* The "Time Travel To" option shows what the table would have looked like at a specific point in time. If you set it to Jan 1 2020, the table should look like what it would have on that date. It can be fun to look back on your progress.
* The PNG Quality slider is a bit esoteric right now but just raise it if the PNG is not sharp enough. It controls each table cell's resolution in the resulting PNG and ranges from 25px\*25px to 200px*200px.
* The "Smooth" option just adds linear interpolation between the colors to smooth them out.

To be added:
* ~~Sort by JLPT level, RRTK/KKLC order, etc.~~
* The ability to select a start date and end date and create a gif showing the table over that span (mostly done).
* re: Time Travel To - account for local time zone and rollover setting (simple)

To be added maybe?:
* User-configurable themes
* ~~Allow regex for field name in case you have kanji fields with different names that you want in the same table~~

Not planned to be added:
* Export to HTML (don't see the utility)

Inspired by [Kanji Grid](https://ankiweb.net/shared/info/909972618) (See here for a color key)
