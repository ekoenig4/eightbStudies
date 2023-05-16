import numpy as np
import awkward as ak
from tqdm import tqdm
from threading import Thread
from multiprocess.pool import ThreadPool


class ObjThread(Thread):
    def __init__(self, obj, obj_function):
        super().__init__()
        self.obj = obj
        self.obj_function = obj_function
    def run(self):
        self.result = self.obj_function(self.obj)

class ThreadManager:
    def __init__(self, objs, obj_function):
        self.threads = [ ObjThread(obj, obj_function) for obj in objs ]

    def __enter__(self):
        return self
    
    def run(self, report=False):
        threads = self.threads
        for thread in threads: thread.start()

        waiting_for = list(range(len(threads)))
        pbar = tqdm(total=len(waiting_for)) if report else None
        while len(waiting_for) > 0:
            for i in waiting_for:
                thread = threads[i]
                if thread.is_alive(): continue

                waiting_for.remove(i)
                if pbar: pbar.update(1)
                thread.join()
        if pbar: pbar.close()

        # for thread in threads: thread.join()
        return [thread.result for thread in self.threads]
        
    def __exit__(self, *args):
        return

class ObjTransform:
    def __init__(self,**kwargs):
        self.__dict__.update(**kwargs)

        if hasattr(self,'init') and callable(self.init):
            self.init()
        
    def __getattr__(self, key):
        if key in self.__dict__: return self.__dict__[key]
        return None
        
class MethodIter:
    def __init__(self, objs, calls):
        self.objs = objs
        self.calls = calls
        self.calliter = zip(objs, calls)

    def __str__(self): return str(self.calls)
    def __iter__(self): return iter(self.calls)
    def __getitem__(self, key): return self.calls[key]

    def __call__(self, *a, args=lambda t: [], kwargs=lambda t: {}, **kw):
        f_args, f_kwargs = args, kwargs
        if not callable(f_args):
            def f_args(t): return args
        if not callable(f_kwargs):
            def f_kwargs(t): return kwargs

        def build_args(t): return list(a)+list(f_args(t))
        def build_kwargs(t): return dict(**f_kwargs(t), **kw)
        out = [call(*build_args(t), **build_kwargs(t)) for t, call in self.calliter]
        return ObjIter(out)

    def zip(self, objiter, *a, args=lambda t:[], kwargs=lambda t:{}, **kw):
        f_args, f_kwargs = args, kwargs
        if not callable(f_args):
            def f_args(t): return args
        if not callable(f_kwargs):
            def f_kwargs(t): return kwargs

        def build_args(t): return list(a)+list(f_args(t))
        def build_kwargs(t): return dict(**f_kwargs(t), **kw)
        out = [call(obj, *build_args(t), **build_kwargs(t)) for (t, call), obj in zip(self.calliter, objiter) ]
        return ObjIter(out)

    
def get_slice(obj,slices):
    if len(slices) == 1:
        return obj[slices[0]]
    if len(slices) == 2:
        return obj[slices[0],slices[1]]
    if len(slices) == 3:
        return obj[slices[0],slices[1],slices[2]]

class ObjIter:
    def __init__(self,objs):
        self.objs = list(objs)

    def __len__(self): return len(self.objs)
    def __str__(self): return str(self.objs)
    def __iter__(self): return iter(self.objs)
    def __repr__(self): return repr(self.objs)
    def __getitem__(self, key): 
        if isinstance(key,list):
            return ObjIter([ self.objs[k] for k in key ])
        if isinstance(key,tuple):
            objs = self.objs[key[0]] if isinstance(key[0],slice) else [ self.objs[k] for k in key[0] ]
            return ObjIter([ get_slice(obj,key[1:]) for obj in objs ])
        if isinstance(key,slice): return ObjIter(self.objs[key])
        if isinstance(key,int): return self.objs[key]
        if isinstance(key,str): return getattr(self, key)
        return ObjIter(self.objs[key])

    def __getattr__(self, key):
        attriter = [getattr(obj, key) for obj in self]
        if callable(attriter[0]):
            attriter = MethodIter(self.objs, attriter)
        else:
            attriter = ObjIter(attriter)
        return attriter
        
    def __add__(self,other):
        if type(other) == list: other = ObjIter(other)
        return ObjIter(self.objs+other.objs)

    def __format__(self, spec):
        return '['+', '.join([ format(value, spec) for value in self.objs ]) + ']'
    
    @property
    def numpy(self): return np.array(self.objs) 
    @property
    def npy(self): return np.array(self.objs)
    @property
    def awkward(self): return ak.from_regular(self.objs)
    @property
    def awk(self): return ak.from_regular(self.objs)
    @property
    def list(self): return self.objs
    @property
    def cat(self): return ak.concatenate(self.objs)



    def zip(self, other):
        return ObjIter(list(zip(self.objs, other.objs)))
    
    def filter(self,obj_filter):
        return ObjIter(list(filter(obj_filter,self)))
    
    def split(self,obj_filter):
        split_t = self.filter(obj_filter)
        split_f = self.filter(lambda obj : obj not in split_t)
        return split_t,split_f

    def parallel_apply(self, obj_function, report=False, nthreads=-1, **kwargs):

        with ThreadManager(self.objs, obj_function) as manager:
            results = manager.run(report=report)

        # if nthreads < 0: nthreads = len(self)
        # elif nthreads < 1: nthreads = int(nthreads*len(self))

        # with ThreadPool(nthreads) as pool:
        #     result = pool.imap(obj_function, self.objs, chunksize=len(self)//nthreads)

        #     if report:
        #         result = tqdm(result, total=len(self))

        #     results = list( result )

        return ObjIter(results)
    
    def pool_apply(self, obj_function, report=False, pool=None):
        if pool is None:
            pool = ThreadPool(len(self))

        result = pool.imap(obj_function, self.objs, chunksize=1)

        if report:
            result = tqdm(result, total=len(self))

        results = list( result )

        return ObjIter(results)

    
    def apply(self, obj_function, report=False, parallel=None, **kwargs):

        if parallel:
            return self.parallel_apply(obj_function, report=report, **kwargs)

        it = tqdm(self) if report else self
        out = ObjIter([ obj_function(obj) for obj in it ])
        
        return out
        
    def copy(self):
        return ObjIter([obj.copy() for obj in self])