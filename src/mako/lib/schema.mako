<%! from util import (schema_markers, rust_doc_comment, mangle_ident, to_rust_type, put_and, 
			  	      IO_TYPES, activity_split, enclose_in, REQUEST_MARKER_TRAIT, mb_type, indent_all_but_first_by,
			  	      NESTED_TYPE_SUFFIX) 
%>\
## Build a schema which must be an object
###################################################################################################################
###################################################################################################################
<%def name="_new_object(s, properties, c)">\
pub struct ${s.id}\
% if properties:
 {
% for pn, p in properties.iteritems():
	${p.get('description', 'no description provided') | rust_doc_comment, indent_all_but_first_by(1)}
	pub ${mangle_ident(pn)}: ${to_rust_type(s.id, pn, p)},
% endfor
}
% else: ## it's an empty struct, i.e. struct Foo;
;
% endif ## 'properties' in s
</%def>

## Create new schema with everything.
## 's' contains the schema structure from json to build
###################################################################################################################
###################################################################################################################
<%def name="new(s, c)">\
<% 
	markers = schema_markers(s, c)
%>\
<%block filter="rust_doc_comment">\
${doc(s, c)}\
</%block>
#[derive(RustcEncodable, RustcDecodable, Default, Clone)]
% if s.type == 'object':
${_new_object(s, s.get('properties'), c)}\
% elif s.type == 'array':
% if s.items.get('type') != 'object':
pub struct ${s.id}(${to_rust_type(s.id, NESTED_TYPE_SUFFIX, s)});
% else:
${_new_object(s, s.items.get('properties'), c)}\
% endif ## array item != 'object'
% else: ## probably any ... just represent it with NewType ... whatever that is
pub struct ${s.id};
% endif ## type == 'object'

% for marker_trait in markers:
impl ${marker_trait} for ${s.id} {}
% endfor

% if REQUEST_MARKER_TRAIT in markers:
impl ${s.id} {
	/// Return a comma separated list of members that are currently set, i.e. for which `self.member.is_some()`.
	/// The produced string is suitable for use as a parts list that indicates the parts you are sending, and/or
	/// the parts you want to see in the server response.
	fn to_parts(&self) -> String {
		let mut r = String::new();
		% for pn, p in s.properties.iteritems():
<%
			mn = 'self.' + mangle_ident(pn)
			rt = to_rust_type(s.id, pn, p)
			check = 'is_some()'
			if rt.startswith('Vec') or rt.startswith('HashMap'):
				check = 'len() > 0'
%>\
		if ${mn}.${check} { r = r + "${pn},"; }
		% endfor
		## remove (possibly non-existing) trailing comma
		r.pop();
		r
	}
}
% endif
</%def>

#########################################################################################################
#########################################################################################################
<%def name="doc(s, c)">\
${s.get('description', 'There is no detailed description.')}
% if s.id in c.sta_map:

# Activities

This type is used in activities, which are methods you may call on this type or where this type is involved in. 
The list links the activity name, along with information about where it is used (one of ${put_and(enclose_in('*', IO_TYPES))}).

${''.join("* [%s](struct.%s.html) (%s)\n" % (activity_split(a)[2], mb_type(*activity_split(a)[1:3]), iot and '|'.join(iot) or 'none') 
													for a, iot in c.sta_map[s.id].iteritems())}
% else:

This type is not used in any activity, and only used as *part* of another schema.
% endif
% if s.type != 'object':

## for some reason, it's not shown in rustdoc ... 
The contained type is `${to_rust_type(s.id, s.id, s)}`.
%endif
</%def>