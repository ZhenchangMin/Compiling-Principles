"""Run the supplied Python 3.8 irsim bytecode without its GUI.

Usage: python3.8 run_official_irsim.py irsim.pyc generated/manifest.json results.json
Only Qt display/input plumbing and top-level GUI startup are replaced. The
original sanity_check, labelCheck, memory, call, and execute_code methods run.
"""
import dis
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys
import types


class Widget:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class CodeList(Widget):
    def __init__(self): self.lines = []
    def clear(self): self.lines.clear()
    def addItem(self, line): self.lines.append(line)
    def count(self): return len(self.lines)
    def item(self, index): return types.SimpleNamespace(text=lambda: self.lines[index])


class Console(Widget):
    def __init__(self): self.values = []
    def clear(self): self.values.clear()
    def append(self, value): self.values.append(int(value))


def load_engine(path):
    if sys.version_info[:2] != (3, 8):
        raise RuntimeError('The supplied irsim.pyc requires Python 3.8')
    class Signal:
        def __init__(self, *args): pass
    for name in ('PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
                 'ui_mainwindow', 'resources_rc'):
        module = types.ModuleType(name)
        module.__all__ = []
        sys.modules[name] = module
    sys.modules['PyQt5.QtCore'].__all__ = ['pyqtSignal']
    sys.modules['PyQt5.QtCore'].pyqtSignal = Signal
    sys.modules['PyQt5.QtWidgets'].__all__ = ['QMainWindow']
    sys.modules['PyQt5.QtWidgets'].QMainWindow = Widget
    sys.modules['ui_mainwindow'].Ui_MainWindow = type('Ui_MainWindow', (), {})
    loader = importlib.machinery.SourcelessFileLoader('official_irsim', str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    code = loader.get_code(loader.name)
    # Execute imports and the unmodified IRSim class definition, ending before
    # the unconditional QApplication startup. Method code objects are untouched.
    end = next(i.offset + 2 for i in dis.get_instructions(code)
               if i.opname == 'STORE_NAME' and i.argval == 'IRSim')
    code = code.replace(co_code=code.co_code[:end] +
                        bytes([dis.opmap['LOAD_CONST'], code.co_consts.index(None),
                               dis.opmap['RETURN_VALUE'], 0]))
    exec(code, module.__dict__)
    def critical(*args): raise RuntimeError(str(args[-1]))
    module.QMessageBox = types.SimpleNamespace(critical=critical)
    return module


def execute(module, path, inputs):
    machine = module.IRSim.__new__(module.IRSim)
    machine.codeList = CodeList()
    machine.watchTable = Widget()
    machine.console = Console()
    machine.updateStatus = lambda *args: None
    machine.initialize()
    data = iter(inputs)
    module.QInputDialog = types.SimpleNamespace(getInt=lambda *args: (next(data), True))
    machine.loadFile(str(path))
    if machine.filename is None: raise RuntimeError('Official simulator rejected the IR')
    machine.ip = machine.entranceIP
    while 0 <= machine.ip < len(machine.codes):
        if machine.instrCnt > 1000000: raise RuntimeError('Instruction limit exceeded')
        result = machine.execute_code(machine.codes[machine.ip])
        if result == 1: return machine.console.values, machine.instrCnt
        if result: raise RuntimeError('Official simulator error code %s' % result)
        machine.ip += 1
    raise RuntimeError('Program counter out of range')


def main():
    module = load_engine(Path(sys.argv[1]))
    manifest_path = Path(sys.argv[2])
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    results = []
    for case in manifest:
        try:
            actual, steps = execute(module, manifest_path.parent / case['ir'], case['input'])
            assert actual == case['output'], (actual, case['output'])
            results.append(dict(name=case['name'], passed=True, instructions=steps))
        except Exception as error:
            results.append(dict(name=case['name'], passed=False, error=str(error)))
    summary = dict(engine='Original supplied irsim.pyc, headless Qt adapter',
                   python=sys.version.split()[0], passed=sum(c['passed'] for c in results),
                   total=len(results), cases=results)
    Path(sys.argv[3]).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('%s/%s official irsim cases passed' % (summary['passed'], summary['total']))
    for c in results:
        if not c['passed']: print(c)
    return int(summary['passed'] != summary['total'])


if __name__ == '__main__': sys.exit(main())
