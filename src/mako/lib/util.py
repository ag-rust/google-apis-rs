import re
import collections

re_linestart = re.compile('^', flags=re.MULTILINE)
re_first_4_spaces = re.compile('^ {1,4}', flags=re.MULTILINE)

USE_FORMAT = 'use_format_field'
TYPE_MAP = {'boolean' : 'bool',
            'integer' : USE_FORMAT,
            'number'  : USE_FORMAT,
            'uint32'  : 'u32',
            'double'  : 'f64',
            'int32'   : 'i32',
            'array'   : 'Vec',
            'string'  : 'String',
            'object'  : 'HashMap'}
TREF = '$ref'
IO_RESPONSE = 'response'
IO_REQUEST = 'request'
IO_TYPES = (IO_REQUEST, IO_RESPONSE)
INS_METHOD = 'insert'
DEL_METHOD = 'delete'

NESTED_TYPE_MARKER = 'is_nested'
SPACES_PER_TAB = 4

# ==============================================================================
## @name Filters
# ------------------------------------------------------------------------------
## @{

# rust module doc comment filter
def rust_module_doc_comment(s):
    return re_linestart.sub('//! ', s)

# rust doc comment filter
def rust_doc_comment(s):
    return re_linestart.sub('/// ', s)

# rust comment filter
def rust_comment(s):
    return re_linestart.sub('// ', s)

# hash-based comment filter
def hash_comment(s):
    return re_linestart.sub('# ', s)

# remove the first indentation (must be spaces !)
def unindent(s):
    return re_first_4_spaces.sub('', s)

# tabs: 1 tabs is 4 spaces
def unindent_first_by(tabs):
    def unindent_inner(s):
        return re_linestart.sub(' ' * tabs * SPACES_PER_TAB, s)
    return unindent_inner

# tabs: 1 tabs is 4 spaces
def indent_all_but_first_by(tabs):
    def indent_inner(s):
        try:
            i = s.index('\n')
        except ValueError:
            f = s
            p = ''
        else:
            f = s[:i+1]
            p = s[i+1:]
        return f + re_linestart.sub(' ' * (tabs * SPACES_PER_TAB), p)
    return indent_inner

# add 4 spaces to the beginning of a line.
# useful if you have defs embedded in an unindent block - they need to counteract. 
# It's a bit itchy, but logical
def indent(s):
    return re_linestart.sub('    ', s)

# return s, with trailing newline
def trailing_newline(s):
    if not s.endswith('\n'):
        return s + '\n'
    return s

# a rust test that doesn't run though
def rust_doc_test_norun(s):
    return "```test_harness,no_run\n%s```" % trailing_newline(s)

# a rust code block in (github) markdown
def markdown_rust_block(s):
    return "```Rust\n%s```" % trailing_newline(s)    

# wraps s into an invisible doc test function.
def rust_test_fn_invisible(s):
    return "# #[test] fn egal() {\n%s# }" % trailing_newline(s)

# markdown comments
def markdown_comment(s):
    return "<!---\n%s-->" % trailing_newline(s)

# escape each string in l with "s" and return the new list
def estr(l):
    return ['"%s"' % i for i in l]

## -- End Filters -- @}

# ==============================================================================
## @name Natural Language Utilities
# ------------------------------------------------------------------------------
## @{

# l must be a list, if it is more than one, 'and' will before last item
# l will also be coma-separtated
# Returns string
def put_and(l):
    if len(l) < 2:
        return l[0]
    return ', '.join(l[:-1]) + ' and ' + l[-1]

# ['foo', ...] with e == '*' -> ['*foo*', ...]
def enclose_in(e, l):
    return ['%s%s%s' % (e, s, e) for s in l]

def md_italic(l):
    return enclose_in('*', l)

def singular(s):
    if s.endswith('ies'):
        return s[:-3]+'y'
    if s[-1] == 's':
        return s[:-1]
    return s

def split_camelcase_s(s):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', s)
    return re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1).lower()

def camel_to_under(s):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', s)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

## -- End Natural Language Utilities -- @}


# ==============================================================================
## @name Rust TypeSystem
# ------------------------------------------------------------------------------
## @{

# Return transformed string that could make a good type name
def canonical_type_name(s):
    # can't use s.capitalize() as it will lower-case the remainder of the string
    return s[:1].upper() + s[1:]

def nested_type_name(sn, pn):
    return sn + pn.capitalize()

# Make properties which are reserved keywords usable
def mangle_ident(n):
    n = camel_to_under(n)
    if n == 'type':
        return n + '_'
    return n

# map a json type to an rust type
# sn = schema name
# pn = property name
# t = type dict
def to_rust_type(sn, pn, t, allow_optionals=True):
    def nested_type(nt):
        if nt.get('items', None) is not None:
            nt = nt.items
        elif nt.get('additionalProperties'):
            nt = nt.additionalProperties
        else:
            assert(is_nested_type_property(nt))
            # It's a nested type - we take it literally like $ref, but generate a name for the type ourselves
            # This of course assumes
            return nested_type_name(sn, pn)
        return to_rust_type(sn, pn, nt, allow_optionals=False)

    # unconditionally handle $ref types, which should point to another schema.
    if TREF in t:
        tn = t[TREF]
        if allow_optionals:
            return "Option<%s>" % tn
        return tn
    try:
        is_pod = True
        rust_type = TYPE_MAP[t.type]
        if t.type == 'array':
            rust_type = "%s<%s>" % (rust_type, nested_type(t))
            is_pod = False
        elif t.type == 'object':
            rust_type = "%s<String, %s>" % (rust_type, nested_type(t))
            is_pod = False
        elif t.type == 'string' and 'Count' in pn:
            rust_type = 'i64'
        elif rust_type == USE_FORMAT:
            rust_type = TYPE_MAP[t.format]
        if is_pod and allow_optionals:
            return "Option<%s>" % rust_type
        return rust_type
    except KeyError as err:
        raise AssertionError("%s: Property type '%s' unknown - add new type mapping: %s" % (str(err), t.type, str(t)))
    except AttributeError as err:
        raise AssertionError("%s: unknown dict layout: %s" % (str(err), t))

# return True if this property is actually a nested type
def is_nested_type_property(t):
    return 'type' in t and t.type == 'object' and 'properties' in t

# Return True if the schema is nested
def is_nested_type(s):
    return NESTED_TYPE_MARKER in s

# convert a rust-type to something that would be taken as input of a function
# even though our storage type is different
def activity_input_type(p):
    n = activity_rust_type(p, allow_optionals=False)
    if n == 'String':
        n = 'str'
    # pods are copied anyway
    elif is_pod_property(p):
        return n
    return '&%s' % n

def is_pod_property(p):
    return 'format' in p or p.type == 'boolean'

# return an iterator yielding fake-schemas that identify a nested type
def iter_nested_types(schemas):
    for s in schemas.values():
        if 'properties' not in s:
            continue
        for pn, p in s.properties.iteritems():
            if is_nested_type_property(p):
                ns = p.copy()
                ns.id = nested_type_name(s.id, pn)
                ns[NESTED_TYPE_MARKER] = True
                yield ns
        # end for ach property
    # end for aech schma

# Return sorted type names of all markers applicable to the given schema
def schema_markers(s, c):
    res = set()

    activities = c.sta_map.get(s.id, dict())
    if len(activities) == 0:
        res.add('Part')
    else:
        # it should have at least one activity that matches it's type to qualify for the Resource trait
        for fqan, iot in activities.iteritems():
            if activity_name_to_type_name(activity_split(fqan)[0]).lower() == s.id.lower():
                res.add('Resource')
            if IO_RESPONSE in iot:
                res.add('ResponseResult')
            if IO_REQUEST in iot:
                res.add('RequestResult')
        # end for each activity
    # end handle activites

    if is_nested_type(s):
        res.add('NestedType')

    return sorted(res)

## -- End Rust TypeSystem -- @}


# -------------------------
## @name Activity Utilities
# @{
# return (name, method)
def activity_split(fqan):
    t = fqan.split('.')
    assert len(t) == 3
    return t[1:]

# Shorthand to get a type from parameters of activities
def activity_rust_type(p, allow_optionals=True):
    return to_rust_type(None, p.name, p, allow_optionals=allow_optionals)

# the inverse of activity-split, but needs to know the 'name' of the API
def to_fqan(name, resource, method):
    return '%s.%s.%s' % (name, resource, method)

# videos -> Video
def activity_name_to_type_name(an):
    return an.capitalize()[:-1]

# yields (resource, activity, activity_data)
def iter_acitivities(c):
    return ((activity_split(an) + [a]) for an, a in c.fqan_map.iteritems())

# return a list of parameter structures of all params of the given method dict
# apply a prune filter to restrict the set of returned parameters.
# The order will always be: partOrder + alpha
def method_params(m, required=None, location=None):
    res = list()
    po = m.get('parameterOrder', [])
    for pn, p in m.parameters.iteritems():
        if required is not None and p.get('required', False) != required:
            continue
        if location is not None and p.get('location', '') != location:
            continue
        np = p.copy()
        np['name'] = pn
        try:
            # po = ['part', 'foo']
            # part_prio = 2 - 0 = 2
            # foo_prio = 2 - 1 = 1
            # default = 0
            prio = len(po) - po.index(pn)
        except ValueError:
            prio = 0
        np['priority'] = prio
        res.append(np)
    # end for each parameter
    return sorted(res, key=lambda p: (p.priority, p.name), reverse=True)


## -- End Activity Utilities -- @}


Context = collections.namedtuple('Context', ['sta_map', 'fqan_map', 'rta_map'])

# return a newly build context from the given data
def new_context(resources):
    # Returns (A, B) where
    # A: { SchemaTypeName -> { fqan -> ['request'|'response', ...]}
    # B: { fqan -> activity_method_data }
    # fqan = fully qualified activity name
    def build_activity_mappings(activities):
        res = dict()
        fqan = dict()
        for an, a in activities.iteritems():
            if 'methods' not in a:
                continue
            for mn, m in a.methods.iteritems():
                assert m.id not in fqan
                fqan[m.id] = m
                for in_out_type_name in IO_TYPES:
                    t = m.get(in_out_type_name, None)
                    if t is None:
                        continue
                    tn = to_rust_type(None, None, t, allow_optionals=False)
                    info = res.setdefault(tn, dict())
                    io_info = info.setdefault(m.id, [])
                    io_info.append(in_out_type_name)
                # end for each io type

                # handle delete/getrating/(possibly others)
                # delete: has no response or request
                # getrating: response is a 'SomethingResult', which is still related to activities name
                #            the latter is used to deduce the resource name
                an, _ = activity_split(m.id)
                tn = activity_name_to_type_name(an)
                info = res.setdefault(tn, dict())
                if m.id not in info:
                    info.setdefault(m.id, [])
                # end handle other cases
            # end for each method
        # end for each activity
        return res, fqan
    # end utility

    sta_map, fqan_map = build_activity_mappings(resources)
    rta_map = dict()
    for an in fqan_map:
        resource, activity = activity_split(an)
        rta_map.setdefault(resource, list()).append(activity)
    return Context(sta_map, fqan_map, rta_map)

# Expects v to be 'v\d+', throws otherwise
def to_api_version(v):
    assert len(v) >= 2 and v[0] == 'v'
    return v[1:]

# build a full library name (non-canonical)
def library_name(name, version):
    return name + to_api_version(version)

# return type name of a resource method builder, from a resource name
def rb_type(r):
    return "%sMethodsBuilder" % singular(canonical_type_name(r))

# return type name for a method on the given resource
def mb_type(r, m):
    return "%s%sMethodBuilder" % (singular(canonical_type_name(r)), m.capitalize())

def hub_type(canonicalName):
    return canonical_type_name(canonicalName)

# return e + d[n] + e + ' ' or ''
def get_word(d, n, e = ''):
    if n in d:
        v = e + d[n] + e
        if not v.endswith(' '):
            v += ' '
        return v
    else:
        return ''

# n = 'FooBar' -> _foo_bar
def property(n):
    return '_' + mangle_ident(n)

