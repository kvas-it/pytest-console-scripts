import importlib


class MockEntryPoint:
    def __init__(self, exec_path):
        self.exec_path = exec_path
        self.module = None

    def load(self):
        self.module = importlib.import_module(self.exec_path)
        return self.module.run
