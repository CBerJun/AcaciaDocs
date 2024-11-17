import os
from typing import (
    TYPE_CHECKING, Any, cast, Iterator, NamedTuple, TypeVar, TypeAlias
)
from enum import Enum
from sphinx.domains import Domain, ObjType
from sphinx.directives import ObjectDescription
from sphinx.locale import get_translation
from sphinx.util.docutils import ReferenceRole, SphinxRole
from sphinx.util.nodes import make_id, make_refnode
from sphinx.util import logging
from sphinx.roles import XRefRole
from sphinx import addnodes
from docutils import nodes
from docutils.parsers.rst import directives

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.addnodes import desc_signature, pending_xref
    from sphinx.util.typing import OptionSpec
    from sphinx.builders import Builder
    from sphinx.environment import BuildEnvironment
    from docutils.nodes import Node, system_message, Element

I18N_CATALOG = 'acacia_ext'
# These are used to parse the function signature
HEXDIGITS = '0123456789abcdef'
DECDIGITS = HEXDIGITS[:10]
BASES = {
    'X': 16,
    'B': 2,
    'O': 8,
}
OPS = '+-*/%=&.,><:'
TWOCHAR_OPS = ('->', '**', '>=', '<=', '==', '!=')
EXPRESSION_OPS = (
    '+', '-', '*', '/', '%', '.', '>', '<',
    '>=', '<=', '==', '!='
)
BRACKETS = {
    '(': ')',
    '[': ']',
    '{': '}',
}
CLOSE_BRACKETS = tuple(BRACKETS.values())

_ = get_translation(I18N_CATALOG)
logger = logging.getLogger(__name__)

class MCWikiRole(ReferenceRole):
    def run(self) -> tuple[list["Node"], list["system_message"]]:
        target = self.target
        if self.has_explicit_title:
            title = self.title
        else:
            if self.target.startswith("~"):
                target = self.target[1:]
                title = target
            else:
                title = _("MCWiki: %s") % target
        refuri = "https://%s.minecraft.wiki/w/%s" % (_("www"), target)
        reference = nodes.reference('', title, internal=False, refuri=refuri)
        return [reference], []

def push_module(name: str, env: "BuildEnvironment") -> None:
    modules: list[str | None] = env.ref_context.setdefault('aca:modules', [])
    modules.append(env.ref_context.get('aca:module'))
    env.ref_context['aca:module'] = name

def pop_module(env: "BuildEnvironment") -> None:
    modules: list[str | None] = env.ref_context['aca:modules']
    env.ref_context['aca:module'] = modules.pop()

def get_fullname(name: str, modname: str | None) -> str:
    return (modname + '.' if modname else '') + name

T = TypeVar('T')

class AttrOwning(Enum):
    NO_ATTR = 0
    ALL_STATIC = 1
    INSTANCE_AND_STATIC = 2

class AttrOwner(NamedTuple):
    fullname: str
    type: AttrOwning

AttrOwnerStack: TypeAlias = list[AttrOwner | None]

class BaseAcaciaObject(ObjectDescription[T]):
    option_spec: "OptionSpec" = {
        'no-index': directives.flag,
        'no-index-entry': directives.flag,
        'no-contents-entry': directives.flag,
        'no-typesetting': directives.flag,
    }

    attribute_owning: AttrOwning = AttrOwning.ALL_STATIC

    def full_name_from_partial(self, partial_name: str) -> str:
        return get_fullname(
            partial_name,
            self.env.ref_context.get('aca:module')
        )

    def partial_name_from_object(self, ob: T) -> str:
        raise NotImplementedError

    def get_index_name(self, fullname: str) -> str | None:
        return None

    def transform_content_name(self, partial_name: str) -> str:
        return partial_name

    def my_handle_signature(self, sig: str, sig_node: "desc_signature") -> T:
        raise NotImplementedError

    def handle_signature(self, sig: str, sig_node: "desc_signature") -> T:
        ob = self.my_handle_signature(sig, sig_node)
        sig_node['aca:partial_name'] = partial_name = \
            self.partial_name_from_object(ob)
        sig_node['aca:full_name'] = self.full_name_from_partial(partial_name)
        return ob

    def before_content(self):
        if self.attribute_owning is AttrOwning.NO_ATTR:
            return
        names: AttrOwnerStack = \
            self.env.ref_context.setdefault('aca:attr_owners', [])
        names.append(self.env.ref_context.get('aca:attr_owner'))
        fullname = self.full_name_from_partial(
            self.partial_name_from_object(self.names[0])
        )
        self.env.ref_context['aca:attr_owner'] = \
            AttrOwner(fullname, self.attribute_owning)

    def after_content(self):
        if self.attribute_owning is AttrOwning.NO_ATTR:
            return
        names: AttrOwnerStack = self.env.ref_context['aca:attr_owners']
        self.env.ref_context['aca:attr_owner'] = names.pop()

    def add_target_and_index(
        self, name: T, sig: str, signode: "desc_signature"
    ) -> None:
        fullname = signode['aca:full_name']
        node_id = make_id(self.env, self.state.document,
                          self.objtype, fullname)
        signode['ids'].append(node_id)
        self.state.document.note_explicit_target(signode)

        domain = cast(AcaciaDomain, self.env.get_domain('aca'))
        domain.note_object(self.objtype, fullname, node_id, location=signode)

        if 'no-index-entry' not in self.options:
            indexname = self.get_index_name(fullname)
            if indexname is not None:
                entry = ('single', indexname, node_id, '', None)
                self.indexnode['entries'].append(entry)

    def _toc_entry_name(self, sig_node: "desc_signature") -> str:
        if not sig_node.get('_toc_parts'):
            return ''
        return self.transform_content_name(sig_node['aca:partial_name'])

    def _object_hierarchy_parts(self, sig_node: "desc_signature") \
            -> tuple[str, ...]:
        full_name: str = sig_node['aca:full_name']
        return tuple(full_name.replace('::', '.').split('.'))

class AcaciaObject(BaseAcaciaObject[str]):
    def partial_name_from_object(self, ob: str):
        return ob

def function_type(argument: str | None) -> str | None:
    if argument in ('const', 'inline', None):
        return argument
    raise ValueError('invalid function type: %r' % argument)

class Token(NamedTuple):
    type: str
    value: str

class Argument(NamedTuple):
    name: str  # may be '' for special construct like *args
    type: list[Token]
    default: list[Token]
    prefix: list[Token]

class FunctionSignature(NamedTuple):
    name: str
    args: list[Argument]
    ret: list[Token]
    ret_prefix: list[Token]

def parse_function_signature(sig: str) -> FunctionSignature:
    # Tokenize
    tokens: list[Token] = []
    paren_stack: list[str] = []
    i = 0
    while i < len(sig):
        if sig[i].isspace():
            i += 1
        elif sig[i:i+3] == '...':
            tokens.append(Token('op', '...'))
            i += 3
        elif sig[i:i+2] in TWOCHAR_OPS:
            tokens.append(Token('op', sig[i:i+2]))
            i += 2
        elif sig[i] in OPS:
            tokens.append(Token('op', sig[i]))
            i += 1
        elif sig[i] in BRACKETS:
            tokens.append(Token('lparen', sig[i]))
            paren_stack.append(BRACKETS[sig[i]])
            i += 1
        elif sig[i] in CLOSE_BRACKETS:
            tokens.append(Token('rparen', sig[i]))
            if not paren_stack or paren_stack[-1] != sig[i]:
                raise ValueError('func sig: unmatched %s' % sig[i])
            paren_stack.pop()
            i += 1
        elif sig[i] in DECDIGITS:
            j = i + 1
            if (sig[i] == '0' and i + 1 < len(sig)
                    and (b := sig[i + 1].upper()) in BASES):
                j += 2
                base10 = False
                digits = HEXDIGITS[:BASES[b]]
            else:
                base10 = True
                digits = DECDIGITS
            while j < len(sig) and sig[j].lower() in digits:
                j += 1
            if base10 and j < len(sig) and sig[j] == '.':
                j += 1
                while j < len(sig) and sig[j] in DECDIGITS:
                    j += 1
            tokens.append(Token('number', sig[i:j]))
            i = j
        elif sig[i] == '"':
            j = i + 1
            while j < len(sig) and sig[j] != '"':
                if sig[j] == '\\':
                    j += 1
                j += 1
            if j >= len(sig):
                raise ValueError('func sig: unclosed string at char %d' % i)
            j += 1
            tokens.append(Token('string', sig[i:j]))
            i = j
        elif sig[i].isalpha() or sig[i] == '_':
            j = i + 1
            while (
                j < len(sig)
                and (sig[j].isalpha() or sig[j] in DECDIGITS or sig[j] == '_')
            ):
                j += 1
            word = sig[i:j]
            if word in ('const', 'None', 'False', 'True'):
                tokens.append(Token('keyword', word))
            else:
                tokens.append(Token('id', word))
            i = j
        else:
            raise ValueError('func sig: invalid syntax at char %d' % i)
    if paren_stack:
        raise ValueError('func sig: unclosed paren(s): %s' % paren_stack)
    # Parse
    if len(tokens) < 3:
        raise ValueError('func sig: less than 3 tokens')
    i = 0
    tok: Token = tokens[0]
    def forward(n: int = 1):
        nonlocal i, tok
        i += n
        if i < len(tokens):
            tok = tokens[i]
        else:
            tok = Token('eof', '')
    def parse_expression(res: list[Token]):
        nparens = 0
        while True:
            if (
                (
                    tok.type == 'op'
                    and (
                        tok.value in EXPRESSION_OPS
                        or (tok.value == ',' and nparens)
                    )
                )
                or tok.type in ('number', 'string', 'keyword')
            ):
                pass
            elif tok.type == 'id':
                words = [tok.value]
                forward()
                while tok.type == 'op' and tok.value == '.':
                    forward()
                    if tok.type != 'id':
                        raise ValueError('func sig: expect id after .')
                    words.append(tok.value)
                    forward()
                res.append(Token('dotname', '.'.join(words)))
                continue
            elif tok.type == 'lparen':
                nparens += 1
            elif tok.type == 'rparen':
                if nparens:
                    nparens -= 1
                else:
                    break
            else:
                break
            res.append(tok)
            forward()
    args: list[Argument] = []
    if tok.type != 'id':
        raise ValueError('func sig: first token must be an id')
    func_name = tok.value
    forward()
    if tok.type != 'lparen' or tok.value != '(':
        raise ValueError('func sig: second token must be left paren')
    forward()
    if tok.type == 'rparen' and tok.value == ')':
        forward()
    else:
        while i < len(tokens):
            # Main body
            if tok.type == 'op' and tok.value == '/':
                # Position only marker
                forward()
                args.append(Argument('', [], [], []))
            else:
                t_type = []
                t_default = []
                t_prefix = []
                # Read 'const' or '&'
                if (tok.type == 'keyword' and tok.value == 'const'
                        or tok.type == 'op' and tok.value == '&'):
                    t_prefix.append(tok)
                    forward()
                # Read '*', '**'
                maybe_marker = False
                if tok.type == 'op' and tok.value in ('*', '**'):
                    maybe_marker = (tok.value == '*' and not t_prefix)
                    t_prefix.append(tok)
                    forward()
                # Read argument name
                if tok.type == 'id':
                    t_name = tok.value
                    forward()
                    if tok.type == 'op' and tok.value == ':':
                        forward()
                        parse_expression(t_type)
                    if tok.type == 'op' and tok.value == '=':
                        forward()
                        parse_expression(t_default)
                elif maybe_marker:
                    t_name = ''
                else:
                    raise ValueError(
                        'func sig: expect argument name at token %d' % i
                    )
                args.append(Argument(t_name, t_type, t_default, t_prefix))
            # Comma (or rparen)
            if tok.type != 'op' or tok.value != ',':
                break
            forward()
        # Rparen
        if tok.type != 'rparen' or tok.value != ')':
            raise ValueError('func sig: expect rparen at token %d' % i)
        forward()
    # Return value
    returns = []
    ret_prefix = []
    if tok.type != 'eof':
        if tok.type != 'op' or tok.value != '->':
            raise ValueError('func sig: expect -> at token %d' % i)
        forward()
        if (tok.type == 'keyword' and tok.value == 'const'
                or tok.type == 'op' and tok.value == '&'):
            ret_prefix.append(tok)
            forward()
        parse_expression(returns)
    return FunctionSignature(func_name, args, returns, ret_prefix)

def token_to_node(token: Token) -> nodes.Node:
    v = token.value
    match token.type:
        case 'op':
            return addnodes.desc_sig_operator('', v)
        case 'lparen' | 'rparen':
            return addnodes.desc_sig_punctuation('', v)
        case 'number':
            return addnodes.desc_sig_literal_number('', v)
        case 'string':
            return addnodes.desc_sig_literal_string('', v)
        case 'keyword':
            return addnodes.desc_sig_keyword('', v)
        case 'dotname':
            return addnodes.desc_sig_name('', v)
        case _:
            raise ValueError('unknown token type: %s' % token.type)

def toklist_to_nodes(lst: list[Token], node: "Element"):
    for token in lst:
        node += token_to_node(token)

def prefix_to_nodes(lst: list[Token], node: "Element"):
    for pref in lst:
        node += token_to_node(pref)
        if pref.type == 'keyword':
            node += addnodes.desc_sig_space()

def signature_to_nodes(sig: FunctionSignature, node: "Element"):
    node += addnodes.desc_name(sig.name, sig.name)
    # Parameters
    paramlist = addnodes.desc_parameterlist()
    node += paramlist
    for arg in sig.args:
        param = addnodes.desc_parameter()
        paramlist += param
        prefix_to_nodes(arg.prefix, param)
        if arg.name:
            param += addnodes.desc_sig_name(arg.name, arg.name)
        if arg.type:
            param += addnodes.desc_sig_operator(':', ':')
            param += addnodes.desc_sig_space()
            toklist_to_nodes(arg.type, param)
        if arg.default:
            param += addnodes.desc_sig_space()
            param += addnodes.desc_sig_operator('=', '=')
            param += addnodes.desc_sig_space()
            toklist_to_nodes(arg.default, param)
    # Return
    if sig.ret:
        node += addnodes.desc_returns()
        prefix_to_nodes(sig.ret_prefix, node)
        toklist_to_nodes(sig.ret, node)

class AcaciaFunction(BaseAcaciaObject[FunctionSignature]):
    option_spec: "OptionSpec" = BaseAcaciaObject.option_spec.copy()
    option_spec.update({
        'type': function_type,
    })

    def get_index_name(self, fullname: str) -> str | None:
        return _('%s (function)') % fullname

    def transform_content_name(self, partial_name: str) -> str:
        return partial_name + '()'

    def my_handle_signature(self, sig: str, signode: "desc_signature") \
            -> FunctionSignature:
        try:
            parsed_sig = parse_function_signature(sig)
        except ValueError as e:
            logger.error(e.args[0], location=signode)
            raise
        logger.info(parsed_sig, location=signode)
        func_type = self.options.get('type')
        prefix = '' if func_type is None else func_type + ' '
        signode += addnodes.desc_annotation('', prefix + 'def')
        signode += addnodes.desc_sig_space()
        signature_to_nodes(parsed_sig, signode)
        return parsed_sig

    def partial_name_from_object(self, ob: FunctionSignature) -> str:
        return ob.name

    def before_content(self) -> None:
        super().before_content()
        sig = self.names[0]
        st = self.env.ref_context.setdefault('aca:param_stack', [])
        st.append([arg.name for arg in sig.args if arg.name])

    def after_content(self) -> None:
        self.env.ref_context['aca:param_stack'].pop()
        super().after_content()

class AcaciaModule(AcaciaObject):
    attribute_owning = AttrOwning.NO_ATTR

    def get_index_name(self, fullname: str) -> str | None:
        return _('%s (module)') % fullname

    def my_handle_signature(self, sig: str, signode: "desc_signature") -> str:
        partial_name = sig.strip()
        signode += addnodes.desc_annotation('', 'module')
        signode += addnodes.desc_sig_space()
        signode += addnodes.desc_name(sig, partial_name)
        return partial_name

    def before_content(self) -> None:
        super().before_content()
        push_module(self.names[0], self.env)

    def after_content(self) -> None:
        pop_module(self.env)
        super().after_content()

class AcaciaAttribute(AcaciaObject):
    option_spec: "OptionSpec" = BaseAcaciaObject.option_spec.copy()
    option_spec.update({
        'static': directives.flag,
    })

    # We disallow attributes of attributes for now because that makes
    # resolving roles like ``:attr:`` harder. Consider this::
    #
    #     This refers to :attr:`a` no doubt.
    #
    #     .. attribute:: a
    #
    #         Comment on ``a``.
    #
    #     .. attribute:: b
    #
    #         What should :attr:`this <a>` refer to?
    #
    #         .. attribute:: a
    #
    #             More comment...
    #
    attribute_owning = AttrOwning.NO_ATTR

    def full_name_from_partial(self, partial_name: str) -> str:
        attr_owner: AttrOwner | None = \
            self.env.ref_context.get('aca:attr_owner')
        if attr_owner is None:
            # We've logged this when handling signature
            return '<error attribute>'
        static = ('static' in self.options
                  or attr_owner.type is AttrOwning.ALL_STATIC)
        sep = '.' if static else '::'
        return attr_owner.fullname + sep + partial_name

    def get_index_name(self, fullname: str) -> str | None:
        return _('%s (attribute)') % fullname

    def my_handle_signature(self, sig: str, signode: "desc_signature") -> str:
        attr_owner: AttrOwner | None = \
            self.env.ref_context.get('aca:attr_owner')
        partial_name = sig.strip()
        if attr_owner is None:
            logger.error(
                "Attribute directives must be nested inside an object",
                location=signode
            )
            return f'<error attribute {partial_name}>'
        all_static = attr_owner.type is AttrOwning.ALL_STATIC
        explicit_static = 'static' in self.options
        if explicit_static:
            if all_static:
                logger.warning(
                    "No need to specify :static: as the owner only accepts "
                    "static attributes",
                    location=signode
                )
            else:
                assert attr_owner.type is AttrOwning.INSTANCE_AND_STATIC
                signode += addnodes.desc_annotation('', 'static')
                signode += addnodes.desc_sig_space()
        if all_static:
            signode += addnodes.desc_sig_punctuation('', '.')
        signode += addnodes.desc_name(sig, partial_name)
        return partial_name

class AcaciaType(AcaciaObject):
    attribute_owning = AttrOwning.INSTANCE_AND_STATIC

    def get_index_name(self, fullname: str) -> str | None:
        return _('%s (type)') % fullname

    def my_handle_signature(self, sig: str, signode: "desc_signature") -> str:
        partial_name = sig.strip()
        signode += addnodes.desc_annotation('', 'type')
        signode += addnodes.desc_sig_space()
        signode += addnodes.desc_name(sig, partial_name)
        return partial_name

class AcaciaXRefRole(XRefRole):
    def process_link(
        self, env: "BuildEnvironment", refnode: "Element",
        has_explicit_title: bool, title: str, target: str,
        suffix: str = ''
    ) -> tuple[str, str]:
        refnode['aca:module_attr'] = env.ref_context.get('aca:module')
        if has_explicit_title:
            return title, target
        if title.startswith('~'):
            target = target.removeprefix('~')
            dot = title.rfind('.')
            if dot != -1:
                title = title[dot + 1:]
            else:
                title = title[1:]  # len("~") == 1
        # Leave the prefixing '^' in `target` to be processed later by
        # `AcaciaDomain.resolve_xref`.
        title = title.removeprefix('^')
        return title + suffix, target

class AcaciaFunctionRole(AcaciaXRefRole):
    def process_link(
        self, env: "BuildEnvironment", refnode: "Element",
        has_explicit_title: bool, title: str, target: str
    ) -> tuple[str, str]:
        return super().process_link(
            env, refnode, has_explicit_title, title, target,
            suffix='()'
        )

class AcaciaParamRole(SphinxRole):
    def run(self) -> tuple[list["Node"], list["system_message"]]:
        st = self.env.ref_context.get('aca:param_stack', [])
        if not any(self.text in args for args in st):
            logger.warning('Unknown Acacia parameter %r' % self.text,
                           location=self.get_location())
        literal = nodes.literal(self.text, self.text)
        return [nodes.emphasis('', '', literal)], []

class AcaciaAttributeRole(AcaciaXRefRole):
    def process_link(
        self, env: "BuildEnvironment", refnode: "Element",
        has_explicit_title: bool, title: str, target: str
    ) -> tuple[str, str]:
        attr_owner: AttrOwner | None = env.ref_context.get('aca:attr_owner')
        refnode['aca:attr_owner_fullname'] = \
            None if attr_owner is None else attr_owner.fullname
        return super().process_link(
            env, refnode, has_explicit_title, title, target,
        )

class AcaciaTypeRole(AcaciaXRefRole):
    pass

class AcaciaDomain(Domain):
    name = 'aca'
    label = 'Acacia'

    object_types = {
        'function': ObjType(_('function'), 'fn'),
        'module': ObjType(_('module'), 'mod'),
        'attribute': ObjType(_('attribute'), 'attr'),
        'type': ObjType(_('type'), 'type'),
    }
    directives = {
        'function': AcaciaFunction,
        'module': AcaciaModule,
        'attribute': AcaciaAttribute,
        'type': AcaciaType,
    }
    roles = {
        'fn': AcaciaFunctionRole(),
        'mod': AcaciaXRefRole(),
        'arg': AcaciaParamRole(),
        'attr': AcaciaAttributeRole(),
        'type': AcaciaTypeRole(),
    }
    initial_data = {
        'objects': {},
    }

    @property
    def objects(self) -> dict[tuple[str, str], tuple[str, str]]:
        return self.data.setdefault('objects', {})

    def note_object(
        self, objtype: str, name: str, node_id: str, location=None
    ) -> None:
        if (objtype, name) in self.objects:
            docname, node_id = self.objects[objtype, name]
            logger.warning(
                'duplicate description of %s %s, other instance in %s'
                % (objtype, name, docname), location=location
            )

        self.objects[objtype, name] = (self.env.docname, node_id)

    def clear_doc(self, docname: str) -> None:
        for (typ, name), (doc, _node_id) in list(self.objects.items()):
            if doc == docname:
                del self.objects[typ, name]

    def merge_domaindata(
        self, docnames: list[str], otherdata: dict[str, Any]
    ) -> None:
        for (typ, name), (doc, node_id) in otherdata['objects'].items():
            if doc in docnames:
                self.objects[typ, name] = (doc, node_id)

    def resolve_xref(
        self, env: "BuildEnvironment", fromdocname: str, builder: "Builder",
        typ: str, target: str, node: "pending_xref", contnode: "Element",
    ) -> "Element | None":
        # Check prefixing '^' that indicates "full name already given"
        if already_fullname := target.startswith('^'):
            target = target[1:]
        # Decide where to search for the given name
        possible_targets = []
        if not already_fullname:
            if typ in ('attr',) and (aon := node['aca:attr_owner_fullname']):
                # Can refer to other attributes under the same attribute
                # owner
                possible_targets.append(aon + "::" + target)
                possible_targets.append(aon + "." + target)
            if (modname := node['aca:module_attr']) is not None:
                # Can refer to other objects in the same module
                possible_targets.append(get_fullname(target, modname))
        # Can search from toplevel (treat it as a full name) (least
        # priority)
        possible_targets.append(target)
        # Start checking if the targets are valid
        for full_target in possible_targets:
            objtypes = self.objtypes_for_role(typ)
            assert objtypes is not None
            for objtype in objtypes:
                result = self.objects.get((objtype, full_target))
                if result is None:
                    continue
                todocname, node_id = result
                # The `title` is something like "function spam.ham":
                title = f"{self.object_types[objtype].lname} {full_target}"
                return make_refnode(builder, fromdocname, todocname, node_id,
                                    contnode, title)
        return None

    def get_objects(self) -> Iterator[tuple[str, str, str, str, str, int]]:
        for (typ, name), (docname, node_id) in self.data['objects'].items():
            yield name, name, typ, docname, node_id, 1

def setup(app: "Sphinx"):
    app.add_domain(AcaciaDomain)
    app.add_role("mcwiki", MCWikiRole())
    package_dir = os.path.abspath(os.path.dirname(__file__))
    locale_dir = os.path.join(package_dir, 'locales')
    app.add_message_catalog(I18N_CATALOG, locale_dir)

    return {
        'version': '0.1',
        'env_version': 1,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
