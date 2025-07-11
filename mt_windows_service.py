import sys

import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import time
import logging

logging.basicConfig(filename='c:\\Temp\\mt-repair-service.log', level=logging.INFO,
                    format='[MTRepairService] %(levelname)-7.7s %(message)s')

class MTService:

    def __init__(self):
        self.running = False

    def stop(self):
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            time.sleep(10)  # Important work
            servicemanager.LogInfoMsg("Service running...")

class MTServiceFramework(win32serviceutil.ServiceFramework):

    _svc_name_ = "MobileTouchRepairService"
    _svc_display_name_ = "Community Ambulance Mobile Touch Repair Service"

    def SvcStop(self):
        """Stop the service"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.service_impl.stop()
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        """Start the service; does not return until stopped"""
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        self.service_impl = MTService()
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        # Run the service
        self.service_impl.run()


def init():
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(MTServiceFramework)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(MTServiceFramework)


if __name__ == '__main__':
    init()