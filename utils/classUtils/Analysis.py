import inspect
from collections import defaultdict
from .ObjIter import ObjIter

import re
def find_all_undeclared(object):
    source = inspect.getsource(object)
    members = set(vars(object).keys())
    ordered_attrs = re.findall('self\.(\w+)',source)
    attrs = set(ordered_attrs)
    declared = set(re.findall('self\.(\w+)\s*=', source))
    undeclared = set.difference(attrs, declared).difference(members)
    return sorted(undeclared, key=ordered_attrs.index)

class MethodList:
    class AnalysisMethod:
        def __init__(self, analysis, method, enabled=True, disable=False):
            self.analysis = analysis 
            self.method = method
            self.enabled = enabled
            self.disable = disable
            self._build_args()
            
        def _build_args(self):
            params = inspect.signature(self.method).parameters
            self.args = []
            self.use_kwargs = False
            for key, param in params.items():
                if key == 'self': continue
                if param.kind is inspect.Parameter.VAR_KEYWORD: 
                    self.use_kwargs = True 
                    break
                self.args.append(key)

        def __call__(self):
            if self.disable or not self.enabled: return
            if self.use_kwargs:
                result = self.method(self.analysis, **vars(self.analysis))
            else:
                result = self.method(self.analysis, *[ getattr(self.analysis, key, None) for key in self.args ])
            self.enabled = False
            return result
        @property
        def __name__(self): return self.method.__name__
        def __repr__(self): return f"<[{'disbaled' if self.disable else ('pending' if self.enabled else 'done')}] {self.__name__}>"
        def run(self):
            self.enabled = True
            return self()

    def __init__(self, analysis, ignore_error=True, **methods):
        self.analysis = analysis
        self.ignore_error = ignore_error
        self.methods = { key:self.AnalysisMethod(analysis, method) for key,method in methods.items() }
    @property
    def keys(self): return list(self.methods.keys())
    @property
    def values(self): return list(self.methods.values())
    def __repr__(self):
        lines = [ f"   {i}: {repr(method)}" for i, method in enumerate(self.methods.values()) ]
        return '<MethodList\n'+'\n'.join(lines)+'\n>'
    def __getiter__(self):
        return iter(self.methods.values())
    def __getitem__(self, key):
        if isinstance(key, str):
            return self.methods[key]
        elif isinstance(key, int):
            return self.values[key]
        elif isinstance(key, list):
            methods = [ self[k] for k in key ]
            methods = { method.__name__:method for method in methods }
        elif isinstance(key, slice):
            methods = { key: self.methods[key] for key in self.keys[key] }

        method_list = MethodList(self.analysis)
        method_list.methods = methods
        return method_list

    def run(self, runlist=None, **kwargs):
        if runlist is None: runlist = self.keys
        for i, (key, method) in enumerate(self.methods.items()): 
            if key not in runlist: 
                print(f'Skipping method: {key}')
                continue
            print(f'Running method: {key}')

            if self.ignore_error:
                try:
                    method()
                except Exception as e:
                    print(f'[Error]: {e}')
            else:
                method()

class Analysis:
    def __init__(self, name=None, runlist=None, ignore_error=True, signal=ObjIter([]), bkg=ObjIter([]), data=ObjIter([]), **kwargs):
        self.name = name
        if name is None:
            self.name = str(self.__class__.__name__)
            
        self.runlist = runlist
        self.signal = signal 
        self.bkg = bkg 
        self.data = data

        methods = { key : method for key, method in vars(self.__class__).items() if (not key.startswith('_') and callable(method)) }
        self.methods = MethodList(self, ignore_error=ignore_error, **methods)

        self.__dict__.update(**kwargs)

    def run(self, runlist=None, **kwargs):
        if runlist is None: runlist = self.runlist
        self.methods.run(runlist, **kwargs)

    @classmethod
    def get_args(cls):
        args = find_all_undeclared(cls)
        return args

    def __repr__(self):
        lines = [
            f'Analysis: {self.name}',
        ] + [
            repr(self.methods)
        ] 
        return '\n'.join(lines)
