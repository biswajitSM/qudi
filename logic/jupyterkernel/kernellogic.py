# -*- coding: utf-8 -*-
"""
IPython compatible kernel launcher module

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
from logic.generic_logic import GenericLogic
from qtpy import QtCore
import pyqtgraph as pg
import numpy as np
import time

from .qzmqkernel import QZMQKernel
from core.util.network import netobtain
import logging
#-----------------------------------------------------------------------------
# The Qudi logic module
#-----------------------------------------------------------------------------

class QudiKernelLogic(GenericLogic):
    """ Logic module providing a Jupyer-compatible kernel connected via ZMQ."""
    _modclass = 'QudiKernelLogic'
    _modtype = 'logic'
    _out = {'kernel': 'QudiKernelLogic'}

    sigStartKernel = QtCore.Signal(str)
    sigStopKernel = QtCore.Signal(int)
    def __init__(self, **kwargs):
        """ Create logic object
          @param dict kwargs: additional parameters as a dict
        """
        super().__init__(**kwargs)
        self.kernellist = dict()
        self.modules = set()

    def on_activate(self, e):
        """ Prepare logic module for work.

          @param object e: Fysom state change notification
        """
        logging.basicConfig(
            format='%(asctime)s %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %I:%M:%S %p',
            level=logging.DEBUG)

        self.kernellist = dict()
        self.modules = set()
        self._manager.sigModulesChanged.connect(self.updateModuleList)
        self.sigStartKernel.connect(self.updateModuleList, QtCore.Qt.QueuedConnection)

    def on_deactivate(self, e):
        """ Deactivate module.

          @param object e: Fysom state change notification
        """
        while len(self.kernellist) > 0:
            self.stopKernel(tuple(self.kernellist.keys())[0])
            QtCore.QCoreApplication.processEvents()
            time.sleep(0.05)

    def startKernel(self, config, external=None):
        """Start a qudi inprocess jupyter kernel.
          @param dict config: connection information for kernel
          @param callable external: function to call on exit of kernel

          @return str: uuid of the started kernel
        """
        realconfig = netobtain(config)
        self.log.info('Start {0}'.format(realconfig))
        mythread = self.getModuleThread()
        kernel = QZMQKernel(realconfig)
        kernel.moveToThread(mythread)
        kernel.user_global_ns.update({
            'pg': pg,
            'np': np,
            'config': self._manager.tree['defined'],
            'manager': self._manager
            })
        kernel.sigShutdownFinished.connect(self.cleanupKernel)
        self.log.info('Kernel is {0}'.format(kernel.engine_id))
        QtCore.QMetaObject.invokeMethod(kernel, 'connect_kernel')
        self.kernellist[kernel.engine_id] = kernel
        self.log.info('Finished starting Kernel {0}'.format(kernel.engine_id))
        self.sigStartKernel.emit(kernel.engine_id)
        return kernel.engine_id

    def stopKernel(self, kernelid):
        """Tell kernel to close all sockets and stop hearteat thread.
          @param str kernelid: uuid of kernel to be stopped
        """
        realkernelid = netobtain(kernelid)
        self.log.info('Stopping {0}'.format(realkernelid))
        kernel = self.kernellist[realkernelid]
        QtCore.QMetaObject.invokeMethod(kernel, 'shutdown')

    def cleanupKernel(self, kernelid, external=None):
        """Remove kernel reference and tell rpyc client for that kernel to exit.

          @param str kernelid: uuid of kernel reference to remove
          @param callable external: reference to rpyc client exit function
        """
        self.log.info('Cleanup kernel {0}'.format(kernelid))
        del self.kernellist[kernelid]
        if external is not None:
            try:
                external.exit()
            except:
                self.log.warning('External qudikernel starter did not exit')

    def updateModuleList(self):
        """Remove non-existing modules from namespace,
            add new modules to namespace, update reloaded modules
        """
        currentModules = set()
        newNamespace = dict()
        for base in ['hardware', 'logic', 'gui']:
            for module in self._manager.tree['loaded'][base]:
                currentModules.add(module)
                newNamespace[module] = self._manager.tree['loaded'][base][module]
        discard = self.modules - currentModules
        for kernel in self.kernellist:
            self.kernellist[kernel].user_global_ns.update(newNamespace)
        for module in discard:
            for kernel in self.kernellist:
                self.kernellist[kernel].user_global_ns.pop(module, None)
        self.modules = currentModules
