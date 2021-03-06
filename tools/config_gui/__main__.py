# -*- coding: utf-8 -*-
"""
Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""
if __package__ is None:
    import __init__
    __package__ = 'config_gui'
else:
    import __init__

from qtpy import QtCore, QtGui, QtWidgets, uic

from pyflowgraph.graph_view import GraphView
from pyflowgraph.graph_view_widget import GraphViewWidget
from pyflowgraph.node import Node
from pyflowgraph.port import InputPort, OutputPort, IOPort

import sys
import os

sys.path.append(os.getcwd())
from gui.colordefs import QudiPalettePale as palette
import core.config
from menu import ModMenu
from collections import OrderedDict
import listmods
import logging
import argparse

class ConfigMainWindow(QtWidgets.QMainWindow):
    """ This class represents the Manager Window.
    """
    def __init__(self, loadfile=None):
        """ Create the Manager Window.
        """
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_config_window.ui')
        self.log = logging.getLogger(__name__)

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)

        self.mods = dict()
        self.globalsection = OrderedDict()
        self.currentFile = ''

        # init 
        self.setupUi()
        self.show()

        if loadfile is not None:
            self.loadConfigFile(loadfile)

    def setupUi(self):
        self.actionNew_configuration.triggered.connect(self.newConfigFile)
        self.actionSave_configuration.triggered.connect(self.saveConfigFile)
        self.actionSave_configuration_as.triggered.connect(self.saveConfigFileAs)
        self.actionOpen_configuration.triggered.connect(self.openConfigFile)
        self.actionDelete_selected_nodes.triggered.connect(self.graphView.deleteSelectedNodes)
        self.actionFrame_selected_nodes.triggered.connect(self.graphView.frameSelectedNodes)
        self.actionFrame_all_nodes.activated.connect(self.graphView.frameAllNodes)

        # add module menu
        self.findModules()
        self.mmroot = ModMenu(self.m)
        for mod in self.mmroot.modules:
            mod.sigAddModule.connect(self.addModule)
        self.actionAdd_Module.setMenu(self.mmroot)

        # node change signals
        self.graphView.nodeAdded.connect(self.nodeAdded)
        self.graphView.nodeRemoved.connect(self.nodeRemoved)
        self.graphView.nodeNameChanged.connect(self.nodeNameChanged)

    def findModules(self):
        modules = listmods.find_pyfiles(os.getcwd())
        m, i_s, ie, oe = listmods.check_qudi_modules(modules)
        self.m = m

        if len(oe) > 0 or len(ie) > 0:
            print('\n==========  ERRORS:  ===========', file=sys.stderr)
            for e in oe:
                print(e[0], file=sys.stderr)
                print(e[1], file=sys.stderr)

            for e in ie:
                print(e[0], file=sys.stderr)
                print(e[1], file=sys.stderr)
       #  print(self.m)

    def addModule(self, module, name=None, pos=(0,0)):
        if name is None:
            name = 'new_module'
        n = 1
        if self.graphView.hasNode(name):
            while self.graphView.hasNode('{}{}'.format(name, n)):
                n += 1
            name = '{}{}'.format(name, n)

        g = self.graphView
        node = Node(g, name)
        if module.path.startswith('hardware'):
            node.setColor(palette.c2)
        elif module.path.startswith('logic'):
            node.setColor(palette.c1)
        elif module.path.startswith('gui'):
            node.setColor(palette.c4)
        else:
            node.setColor(palette.c3)

        for conn in module.conn_in:
            node.addPort(InputPort(node, g, conn[0], palette.c3, conn[1]))

        for conn in module.conn_out:
            node.addPort(OutputPort(node, g, conn[0], palette.c3, conn[1]))

        node.setGraphPos(QtCore.QPointF(pos[0], pos[1]))

        self.mods[name] = {
            'node': node,
            'module': module,
            }
        g.addNode(node)

    def openConfigFile(self):
        defaultconfigpath = ''
        filename = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Load Configration',
            defaultconfigpath ,
            'Configuration files (*.cfg)')
        if len(filename) > 0:
            print('Open:', filename)
            self.loadConfigFile(filename)

    def loadConfigFile(self, filename):
        config = core.config.load(filename)
        self.configToNodes(config)
        self.currentFile = filename
        self.graphView.frameAllNodes()

    def newConfigFile(self):
        self.graphView.reset()
        self.configFileName = 'New configuration'
        self.updateWindowTitle(self.configFileName, extra='*')

    def saveConfigFile(self):
        if os.path.isfile(self.currentFile):
            config = self.nodesToConfig()
            core.config.save(self.currentFile, config)
        else:
             self.saveConfigFileAs()

    def saveConfigFileAs(self):
        defaultconfigpath = os.path.dirname(self.currentFile)
        filename = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Save Configration As',
            defaultconfigpath ,
            'Configuration files (*.cfg)')
        if len(filename) > 0:
            print('Save:', filename)
            config = self.nodesToConfig()
            core.config.save(filename, config)
            self.currentFile = filename

    def updateWindowTitle(self, filename, extra=''):
        self.setWindowTitle('{}{} - Qudi configuration editor'.format(filename, extra))
    
    def getModuleInfo(self):
        modules = listmods.find_pyfiles(os.getcwd())
        m, i_s, ie, oe = listmods.check_qudi_modules(modules)

    def configToNodes(self, config):
        pos = [0, 0]
        for b,m in config.items():
            if b not in ['hardware', 'logic', 'gui']:
                continue
            for k,v in m.items():
                mc = 'module.Class'
                #print(b, k, v)
                if mc in v and self.mmroot.hasModule(b + '.' + v[mc]):
                    mod = self.mmroot.getModule(b + '.' + v[mc])
                    self.addModule(mod, k, pos)
                pos[1] += 100
            pos[0] += 600
            pos[1] = 0

        for b,m in config.items():
            if b not in ['hardware', 'logic', 'gui']:
                continue
            for k,v in m.items():
                if 'connect' in v:
                    for conn_in, conn_out in v['connect'].items():
                        cl = conn_out.split('.')
                        src = '.'.join(cl[:-1])

                        if k not in self.mods:
                            self.log.error(
                                'Target module {} not present while connecting {}.{} to {}'
                                ''.format(k, conn_in, src, cl[-1]))
                            continue
                        if conn_in not in [c[0] for c in self.mods[k]['module'].conn_in]:
                            self.log.error(
                                'Target connector {} not present while connecting {}.{} to {}.{}'
                                ''.format(conn_in, src, cl[-1], k, conn_in))
                            continue
                        if src not in self.mods:
                            self.log.error(
                                'Source module {} not present while connecting {} to {}.{}'
                                ''.format(src, cl[-1], k, conn_in))
                            continue
                        if cl[-1] not in [c[0] for c in self.mods[src]['module'].conn_out]:
                            self.log.error(
                                'Source connector {} not present while connecting {}.{} to {}.{}'
                                ''.format(conn_in, src, cl[-1], k, conn_in))
                            continue

                        try:
                            self.graphView.connectPorts(self.mods[src]['node'], cl[-1], self.mods[k]['node'], conn_in)
                        except:
                            self.log.error(
                                'pyflowgraph failed while connecting {}.{} to {}.{}'
                                ''.format(src, cl[-1], k, conn_in))
                            
        self.globalsection = config['global']

    def nodesToConfig(self):
        """ Convert nodes into OrderedDict for saving.
        """
        config = OrderedDict()
        config['global'] = OrderedDict()
        config['hardware'] = OrderedDict()
        config['logic'] = OrderedDict()
        config['gui'] = OrderedDict()

        for key,value in self.globalsection.items():
            config['global'][key] = value

        for mname,mod in self.mods.items():
            entry = OrderedDict()
            path = mod['module'].path.split('.')

            if len(path) > 1 and path[0] in ('hardware', 'logic', 'gui'):
                config[path[0]][mname] = entry
                entry['module.Class'] = '.'.join(path[1:])

                portin = (mod['node'].getPort(x[0]) for x in mod['module'].conn_in)
                conndict = OrderedDict()
                for port in portin:
                    conns = port.inCircle().getConnections()
                    if len(conns) == 1:
                        c = tuple(conns)[0]
                        src = c.getSrcPort()
                        node = src.getNode()
                        conndict[port.getName()] = '{}.{}'.format(node.getName(), src.getName())
                if len(conndict) > 0:
                    entry['connect'] = conndict
            print(entry)

        return config

    def nodeAdded(self):
        pass

    def nodeRemoved(self):
        pass

    def nodeNameChanged(self):
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='config_gui')
    parser.add_argument('-c', '--config', default=None, help='configuration file')
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    mw = ConfigMainWindow(loadfile=args.config)
    app.exec_()

