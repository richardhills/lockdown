import ctypes
import gc
import inspect
import types


def proxy0(data):
    def proxy1(): return data
    return proxy1
_CELLTYPE = type(proxy0(None).func_closure[0])

def replace_all_refs(old_obj, new_obj):
    """
    :summary: Uses the :mod:`gc` module to replace all references to obj
              :attr:`old_obj` with :attr:`new_obj` (it tries it's best, 
              anyway). 
                      
    :param old_obj: The obj you want to replace. 
    
    :param new_obj: The new_obj you want in place of the old obj. 
    
    :returns: The old_obj
    
    Use looks like:
    
    >>> import pyjack
    >>> x = ('org', 1, 2, 3)
    >>> y = x
    >>> z = ('new', -1, -2, -3)
    >>> org_x = pyjack.replace_all_refs(x, z)
    >>> print x
    ('new', -1, -2, -3)    
    >>> print y 
    ('new', -1, -2, -3)    
    >>> print org_x 
    ('org', 1, 2, 3)
    To reverse the process, do something like this:
    >>> z = pyjack.replace_all_refs(z, org_x)
    >>> del org_x
    >>> print x
    ('org', 1, 2, 3)
    >>> print y 
    ('org', 1, 2, 3)
    >>> print z
    ('new', -1, -2, -3)    
        
    .. note:
        The obj returned is, by the way, the last copy of :attr:`old_obj` in 
        memory; if you don't save a copy, there is no way to put state of the 
        system back to original state.     
    
    .. warning:: 
       
       This function does not work reliably on strings, due to how the 
       Python runtime interns strings. 

        Inspired by https://benkurtovic.com/2015/01/28/python-object-replacement.html
    """

    gc.collect()
    
    hit = False    
    for referrer in gc.get_referrers(old_obj):
                
        # FRAMES -- PASS THEM UP
        if isinstance(referrer, types.FrameType):
            for local_var_name, local_var_value in referrer.f_locals.items():
                if local_var_value is old_obj:
                    referrer.f_locals[local_var_name] = new_obj
                    ctypes.pythonapi.PyFrame_LocalsToFast(
                        ctypes.py_object(referrer), ctypes.c_int(0)
                    )
                    hit = True

        # DICTS
        elif isinstance(referrer, dict):
             
            cls = None

            # THIS CODE HERE IS TO DEAL WITH DICTPROXY TYPES
            if '__dict__' in referrer and '__weakref__' in referrer:
                for cls in gc.get_referrers(referrer):
                    if inspect.isclass(cls) and cls.__dict__ == referrer:
                        break
            
            for key, value in referrer.items():
                # REMEMBER TO REPLACE VALUES ...
                if value is old_obj:
                    hit = True
                    value = new_obj
                    referrer[key] = value
                    if cls: # AGAIN, CLEANUP DICTPROXY PROBLEM
                        setattr(cls, key, new_obj)
                # AND KEYS.
                if key is old_obj:
                    hit = True
                    del referrer[key]
                    referrer[new_obj] = value
                                                                        
        # LISTS
        elif isinstance(referrer, list):
            for i, value in enumerate(referrer):
                if value is old_obj:
                    hit = True
                    referrer[i] = new_obj
        
        # SETS
        elif isinstance(referrer, set):
            referrer.remove(old_obj)
            referrer.add(new_obj)
            hit = True

        # TUPLE, FROZENSET
        elif isinstance(referrer, (tuple, frozenset,)):
            new_tuple = []
            for obj in referrer:
                if obj is old_obj:
                    new_tuple.append(new_obj)
                else:
                    new_tuple.append(obj)
            replace_all_refs(referrer, type(referrer)(new_tuple))

        # CELLTYPE        
        elif isinstance(referrer, _CELLTYPE):
            def proxy0(data):
                def proxy1(): return data
                return proxy1
            proxy = proxy0(new_obj)
            newcell = proxy.func_closure[0]
            replace_all_refs(referrer, newcell)            
        
        # FUNCTIONS
        elif isinstance(referrer, types.FunctionType):
            localsmap = {}
            for key in ['func_code', 'func_globals', 'func_name', 
                        'func_defaults', 'func_closure']:
                orgattr = getattr(referrer, key)
                if orgattr is old_obj:
                    localsmap[key.split('func_')[-1]] = new_obj
                else:
                    localsmap[key.split('func_')[-1]] = orgattr
            localsmap['argdefs'] = localsmap['defaults']
            del localsmap['defaults']
            newfn = types.FunctionType(**localsmap)
            replace_all_refs(referrer, newfn)

        # OTHER (IN DEBUG, SEE WHAT IS NOT SUPPORTED). 
        else:
            # debug: 
            print type(referrer)
            pass
            
    if hit is False:
        raise AttributeError("Object '%r' not found" % old_obj)

    return old_obj
