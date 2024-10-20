import os
from typing import TYPE_CHECKING, Any, Optional, Iterator, NamedTuple, TypeVar
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
    modules = env.ref_context.setdefault('aca:modules', [])
    modules.append(env.ref_context.get('aca:module'))
    env.ref_context['aca:module'] = name

def pop_module(env: "BuildEnvironment") -> None:
    modules: list[str] = env.ref_context.setdefault('aca:modules', [])
    if modules:
        env.ref_context['aca:module'] = modules.pop()
    else:
        env.ref_context.pop('aca:module')

def get_fullname(name: str, modname: Optional[str]) -> str:
    return (modname + '.' if modname else '') + name

T = TypeVar('T')

class BaseAcaciaObject(ObjectDescription[T]):
    option_spec: "OptionSpec" = {
        'no-index': directives.flag,
        'no-index-entry': directives.flag,
        'no-contents-entry': directives.flag,
        'no-typesetting': directives.flag,
        'module': directives.unchanged
    }

    def get_fullname(self, name: str) -> str:
        modname = self.options.get(
            'module', self.env.ref_context.get('aca:module')
        )
        return get_fullname(name, modname)

    def get_index_name(self, fullname: str) -> Optional[str]:
        return None

    def _add_target_and_index(
        self, name: str, sig: str, signode: "desc_signature"
    ) -> None:
        fullname = self.get_fullname(name)
        node_id = make_id(self.env, self.state.document,
                          self.objtype, fullname)
        signode['ids'].append(node_id)
        self.state.document.note_explicit_target(signode)

        domain: AcaciaDomain = self.env.get_domain('aca')
        domain.note_object(self.objtype, fullname, node_id, location=signode)

        if 'no-index-entry' not in self.options:
            indexname = self.get_index_name(fullname)
            if indexname is not None:
                entry = ('single', indexname, node_id, '', None)
                self.indexnode['entries'].append(entry)

    def before_content(self) -> None:
        if 'module' in self.options:
            push_module(self.options['module'], self.env)

    def after_content(self) -> None:
        if 'module' in self.options:
            pop_module(self.env)

class AcaciaObject(BaseAcaciaObject[str]):
    def add_target_and_index(
        self, name: str, sig: str, signode: "desc_signature"
    ) -> None:
        self._add_target_and_index(name, sig, signode)

def function_type(argument: Optional[str]) -> str:
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

def toklist_to_nodes(lst: list[Token], signode: "desc_signature"):
    for token in lst:
        signode += token_to_node(token)

def prefix_to_nodes(lst: list[Token], signode: "desc_signature"):
    for pref in lst:
        signode += token_to_node(pref)
        if pref.type == 'keyword':
            signode += addnodes.desc_sig_space()

def signature_to_nodes(sig: FunctionSignature, signode: "desc_signature"):
    signode += addnodes.desc_name(sig.name, sig.name)
    # Parameters
    paramlist = addnodes.desc_parameterlist()
    signode += paramlist
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
        signode += addnodes.desc_returns()
        prefix_to_nodes(sig.ret_prefix, signode)
        toklist_to_nodes(sig.ret, signode)

class AcaciaFunction(BaseAcaciaObject[FunctionSignature]):
    option_spec: "OptionSpec" = BaseAcaciaObject.option_spec.copy()
    option_spec.update({
        'type': function_type,
    })

    def get_index_name(self, fullname: str) -> Optional[str]:
        return _('%s (function)') % fullname

    def handle_signature(self, sig: str, signode: "desc_signature") -> str:
        try:
            parsed_sig = parse_function_signature(sig)
        except ValueError as e:
            logger.error(e.args[0], location=signode)
            raise
        logger.info(parsed_sig, location=signode)
        signode['fullname'] = self.get_fullname(parsed_sig.name)
        func_type = self.options.get('type')
        prefix = '' if func_type is None else func_type + ' '
        signode += addnodes.desc_annotation('', prefix + 'def')
        signode += addnodes.desc_sig_space()
        signature_to_nodes(parsed_sig, signode)
        return parsed_sig

    def add_target_and_index(
        self, name: FunctionSignature, sig: str, signode: "desc_signature"
    ) -> None:
        return self._add_target_and_index(name.name, sig, signode)

    def before_content(self) -> None:
        super().before_content()
        sig = self.names[0]
        st = self.env.ref_context.setdefault('aca:param_stack', [])
        args = [arg.name for arg in sig.args if arg.name]
        st.append(args)

    def after_content(self) -> None:
        self.env.ref_context['aca:param_stack'].pop()
        super().after_content()

class AcaciaModule(AcaciaObject):
    def get_index_name(self, fullname: str) -> Optional[str]:
        return _('%s (module)') % fullname

    def handle_signature(self, sig: str, signode: "desc_signature") -> str:
        signode['fullname'] = sig.strip()
        signode += addnodes.desc_annotation('', 'module')
        signode += addnodes.desc_sig_space()
        signode += addnodes.desc_name(sig, sig)
        return sig

    def before_content(self) -> None:
        super().before_content()
        push_module(self.names[0], self.env)

    def after_content(self) -> None:
        pop_module(self.env)
        super().after_content()

class AcaciaXRefRole(XRefRole):
    def process_link(
        self, env: "BuildEnvironment", refnode: "Element",
        has_explicit_title: bool, title: str, target: str,
        suffix: str = ''
    ) -> tuple[str, str]:
        refnode['aca:module'] = env.ref_context.get('aca:module')
        if not has_explicit_title:
            target = target.lstrip('~')
            if title.startswith('~'):
                dot = title.rfind('.')
                if dot != -1:
                    title = title[dot + 1:]
                else:
                    title = title[1:]
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

class AcaciaDomain(Domain):
    name = 'aca'
    label = 'Acacia'

    object_types = {
        'function': ObjType(_('function'), 'fn'),
        'module': ObjType(_('module'), 'mod'),
    }
    directives = {
        'function': AcaciaFunction,
        'module': AcaciaModule,
    }
    roles = {
        'fn': AcaciaFunctionRole(),
        'mod': AcaciaXRefRole(),
        'arg': AcaciaParamRole(),
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
    ) -> Optional["Element"]:
        modname = node.get('aca:module')
        fulltarget = get_fullname(target, modname)
        objtypes = self.objtypes_for_role(typ)
        if not objtypes:
            return None
        for objtype in objtypes:
            result = self.objects.get((objtype, fulltarget))
            if not result:
                # Try without module name (in builtins scope)
                fulltarget = target
                result = self.objects.get((objtype, fulltarget))
            if result:
                todocname, node_id = result
                title = self.object_types[objtype].lname + ' ' + fulltarget
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
