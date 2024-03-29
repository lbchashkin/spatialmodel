# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SpatialModel
                                 A QGIS plugin
 This plugin creates a spatial model
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-04-14
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Leonid Chashkin / HSE
        email                : lbchashkin@edu.hse.ru
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import math
import os
import os.path
from zipfile import ZipFile

import requests
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QFileDialog
from qgis.core import QgsStyle, QgsPalettedRasterRenderer, QgsHillshadeRenderer, QgsBrightnessContrastFilter, \
    QgsRasterContourRenderer, QgsLineSymbol, QgsCoordinateReferenceSystem, QgsCoordinateTransform

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .spatial_model_dialog import SpatialModelDialog


class SpatialModel:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'SpatialModel_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Spatial Model')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        self.dlg = None

    @staticmethod
    def get_srtm_data(y_max, y_min, x_min, x_max, login, password, folder):
        session = requests.Session()
        session.auth = (login, password)  # ауентификация

        filenames = []  # назания загруженных файлов
        lat_tx = ""  # код широты
        lon_tx = ""  # код долготы
        for lat in range(y_min, y_max):  # цикл по широте
            for lon in range(x_min, x_max):  # цикл по долготе
                if 10 > lon >= 0:  # 1 знак Е
                    lon_tx = "E00%s" % lon
                elif 10 <= lon < 100:  # 2 знака E
                    lon_tx = "E0%s" % lon
                elif lon >= 100:  # 3 знака E
                    lon_tx = "E%s" % lon
                elif -10 < lon < 0:  # 1 знак W
                    lon_tx = "W00%s" % abs(lon)
                elif -10 >= lon > -100:  # 2 знака W
                    lon_tx = "W0%s" % abs(lon)
                elif lon <= -100:  # 3 знака W
                    lon_tx = "W%s" % abs(lon)

                if 10 > lat >= 0:  # 1 знак N
                    lat_tx = "N0%s" % lat
                elif 10 <= lat < 100:  # 2 знака N
                    lat_tx = "N%s" % lat
                elif -10 < lat < 0:  # 1 знак S
                    lat_tx = "S0%s" % abs(lat)
                elif -10 >= lat > -100:  # 2 знака S
                    lat_tx = "S%s" % abs(lat)

                url = "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/%s%s.SRTMGL1.hgt.zip" % (
                    lat_tx, lon_tx)
                r1 = session.request('get', url)
                response = session.get(r1.url, auth=(login, password))  # загрузка архива

                if response.status_code == 200:
                    zip_name = os.path.join(folder, f"{lat}_{lon}.zip")
                    with open(zip_name, "wb") as f:  # временное сохранение архива
                        f.write(response.content)

                    with ZipFile(zip_name, 'r') as myzip:
                        myzip.extractall()  # разархивация

                    os.remove(zip_name)  # удаление архива
                    filenames.append(os.path.abspath(f"{lat_tx}{lon_tx}.hgt"))
                else:
                    print("Error downloading SRTM data.")
                    return []

        return filenames

    def visualizing(self, filenames):
        for filename in filenames:  # цикл по всем лоям

            # слой цветового градиента
            layer = self.iface.addRasterLayer(filename, "colour")

            style = QgsStyle().defaultStyle()
            ramp = style.colorRamp("RdYlGn")  # палитра
            palette = QgsPalettedRasterRenderer.classDataFromRaster(layer.dataProvider(), 1, ramp)
            palette_raster = QgsPalettedRasterRenderer(layer.dataProvider(), 1, palette)
            layer.setRenderer(palette_raster)
            layer.triggerRepaint()  # перерисовка слоя

            # слой теневого рельефа
            layer = self.iface.addRasterLayer(filename, "hillshade")

            layer.setRenderer(QgsHillshadeRenderer(layer.dataProvider(), 1, 45, 315))
            layer.triggerRepaint()  # перерисовка слоя

            # Яркость
            contrastFilter = QgsBrightnessContrastFilter()
            contrastFilter.setBrightness(100)
            layer.pipe().set(contrastFilter)
            layer.triggerRepaint()  # перерисовка слоя

            # Смешивание
            layer.setBlendMode(13)
            layer.triggerRepaint()  # перерисовка слоя

            # слой изолиний
            layer = self.iface.addRasterLayer(filename, "isolines")
            isolines = QgsRasterContourRenderer(layer.dataProvider())
            isolines.setContourInterval(500)  # размер щага
            symbol = QgsLineSymbol()
            symbol.setColor(QColor("black"))  # цвет линий
            isolines.setContourIndexSymbol(symbol)
            isolines.setContourSymbol(symbol)
            layer.setRenderer(isolines)
            layer.triggerRepaint()  # перерисовка слоя

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('SpatialModel', message)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToWebMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/spatial_model/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Создать цифровую модель'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginWebMenu(
                self.tr(u'&Spatial Model'),
                action)
            self.iface.removeToolBarIcon(action)

    def get_folder(self):
        """Get folder name"""
        folder_name = QFileDialog.getExistingDirectory()
        self.dlg.fileLine.setText(folder_name)

    def get_location(self):
        """Get current map location"""
        new_system = QgsCoordinateReferenceSystem("EPSG:4326")
        current_system = self.iface.mapCanvas().mapSettings().destinationCrs()
        transformer = QgsCoordinateTransform()
        transformer.setSourceCrs(current_system)
        transformer.setDestinationCrs(new_system)

        coordinates = transformer.transform(self.iface.mapCanvas().extent())

        self.dlg.west.setValue(math.floor(coordinates.xMinimum()))
        self.dlg.east.setValue(math.ceil(coordinates.xMaximum()))
        self.dlg.south.setValue(math.floor(coordinates.yMinimum()))
        self.dlg.north.setValue(math.ceil(coordinates.yMaximum()))

    def get_input(self):
        """Get input data"""
        login = self.dlg.login.text()
        password = self.dlg.password.text()
        N = self.dlg.north.value()
        S = self.dlg.south.value()
        W = self.dlg.west.value()
        E = self.dlg.east.value()
        folder = self.dlg.fileLine.text()
        return [(login, password), (N, S, W, E), folder]

    @staticmethod
    def is_data_valid(auth, coordinates, folder):
        """Is data valid"""
        if (auth[0] == "") or (auth[1] == ""):
            return 1
        if not os.path.isdir(folder):
            return 2
        n, s, w, e = coordinates
        if ((n < -56) and (s < -56)) or (n > 59) or ((s < -56) and (n != 0)):
            return 3
        if (n <= s) or (e <= w):
            return 4
        return 0

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so                 that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            self.dlg = SpatialModelDialog()
        self.dlg.pushButton.clicked.connect(self.get_location)
        self.dlg.fileButton.clicked.connect(self.get_folder)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            auth, coordinates, folder = self.get_input()

            ok = self.is_data_valid(auth, coordinates, folder)

            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Ошибка")
            msg.setWindowTitle("Ошибка")

            if ok != 0:
                message = ""
                if ok == 1:
                    message = "Поля логин и пароль пустые. Заполните их и повторите попытку."
                elif ok == 2:
                    message = "Неверный путь к папке. Папки не существует. Введите корректный путь и повторите попытку."
                elif ok == 3:
                    message = "Рассматриваемая область полностью или частично не входит в область данных SRTM." \
                              " Выберите другую область и повторите попытку."
                elif ok == 3:
                    message = "Неверно заполнены координаты. Максимальная широта и долгота должны быть"\
                              " больше минимальных." \
                              " Введите корректные координаты и повторите попытку."
                msg.setInformativeText(message)
                msg.exec_()
            else:
                N, S, W, E = coordinates
                filenames = self.get_srtm_data(N, S, W, E, auth[0], auth[1], folder)
                if len(filenames) == 0:
                    msg.setInformativeText(
                        "При загрузке данных о рельефе из проекта SRTM произошла ошибка."
                        "Проверьте введённые данные и повторите попытку.")
                    msg.exec_()
                else:
                    self.visualizing(filenames)
