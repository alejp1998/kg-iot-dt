defvalues = {
    'string' : '""',
    'long' : 0,
    'double' : 0.0,
    'boolean' : 'false',
    'datetime' : '2022-01-01T00:00:00'
    ''
}

queries = {
    'device_uids':"""
        match 
            $dev isa device, has uid $devuid;
        get
            $devuid;
    """,
    'modules_check' : """
        match
            $dev isa device, has uid $uiddev; $uiddev "{}";
            $includes (device: $dev, module: $mod) isa includes;
            $mod isa module, has uid $moduid;
        get 
            $moduid;
    """,
    'properties_check' : """
        match 
            $mod isa {}, has {} $prop_value;
        get
            $prop_value;
    """
}

