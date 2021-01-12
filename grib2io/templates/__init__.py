def _build_args(a,b):
    """
    """
    safe_dict = {}
    safe_dict['a'] = a
    args = []
    for i in b:
        if 'eval' in i:
            result = eval(i,{},safe_dict)
            if isinstance(result,list):
                for ii in result: args.append(ii)
            else:
                args.append(result)
        else:
           args.append(i)
    return args


def set_section1_keys(a):
    """
    """
    from .section1 import section1_template
    adict = {}
    for k,v in section1_template.items():
        func = v[0]
        args = _build_args(a,v[1])
        if func is None:
            if isinstance(args,list) and len(args) == 1:
                adict[k] = args[0]
            else:
                adict[k] = args
        else:
            adict[k] = func(*args)
    return adict
