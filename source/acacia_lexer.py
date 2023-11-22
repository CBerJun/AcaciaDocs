"""Lexer for Acacia."""

__all__ = ["AcaciaLexer"]

from pygments.lexer import RegexLexer, include, words, default, bygroups
from pygments.token import *

class AcaciaLexer(RegexLexer):
    name = "AcaciaMC"
    aliases = ["acacia", "aca"]
    filenames = ["*.aca"]

    _identifier = r"[a-zA-Z_]\w*"

    tokens = {
        "root": [
            (r"/\*", Punctuation, "multi_command"),
            (
                r"^(\s*)(/)",
                bygroups(Whitespace, Punctuation),
                "single_command"
            ),
            (
                r"^(\s*)(@(?:position|type|spawn_event):)",
                bygroups(Whitespace, Name.Label)
            ),
            include("ws"),
            include("numbers"),
            (r":=", Operator),
            (r"[:,()\[\]{}]", Punctuation),
            (r'"', String.Double, "string"),
            (
                r"->|!=|==|\+=|-=|\*=|/=|%=|[-+/*%=<>.|@]",
                Operator,
            ),
            (r"(and|or|not)\b", Operator.Word),
            include("keywords"),
            include("control_flow_keywords"),
            (r"def", Keyword.Declaration, "func_name"),
            (r"entity|struct", Keyword.Declaration, "class_name"),
            include("builtins"),
            (_identifier, Name),
        ],
        "ws": [
            # We split `\s+` into two rules, so that the rule that
            # requires checking `^` (i.e. single line commands) can
            # work correctly.
            (r"[^\S\n]+", Whitespace),
            (r"\n+", Whitespace),
            (r"\\\s*?$", Whitespace),
            (r"(?s)#\*.*?\*#", Comment.Multiline),
            (r"#.*?$", Comment.Single),
        ],
        "numbers": [
            (r"[+-]?0[xX][a-fA-F0-9]+", Number.Hex),
            (r"[+-]?0[bB][01]+", Number.Bin),
            (r"[+-]?0[oO][0-7]+", Number.Oct),
            (r"[+-]?\d+\.\d+", Number.Float),
            (r"[+-]?\d+", Number.Integer),
        ],
        "control_flow_keywords": [
            (
                words(
                    ("if", "elif", "else", "while", "pass", "for", "in"),
                    suffix=r"\b"
                ),
                Keyword.ControlFlow
            )
        ],
        "keywords": [
            (words(("True", "False", "None"), suffix=r"\b"), Keyword.Constant),
            (
                words(
                    (
                        "def", "interface", "inline", "entity", "extends",
                        "self", "result", "import", "as", "from", "virtual",
                        "override", "struct"
                    ),
                    suffix=r"\b"
                ),
                Keyword
            )
        ],
        "builtins": [
            (
                words(
                    (
                        "int", "bool", "Pos", "Rot", "Offset", "Engroup",
                        "Enfilter", "list", "map", "AbsPos", "ExternEngroup",
                        "Entity"
                    ),
                    prefix=r"(?<!\.)",
                    suffix=r"\b"
                ),
                Name.Builtin
            )
        ],
        "func_name": [
            include("ws"),
            ("__init__\b", Name.Function.Magic, "#pop"),
            (_identifier, Name.Function, "#pop"),
            default("#pop")
        ],
        "class_name": [
            include("ws"),
            (_identifier, Name.Class, "#pop"),
            default("#pop")
        ],
        "formatted_expr": [
            (r"\{", Punctuation, "formatted_expr_inner"),
            (r"\}", String.Interpol, "#pop"),
            include("root"),
        ],
        "formatted_expr_inner": [
            (r"\{", Punctuation, "#push"),
            (r"\}", Punctuation, "#pop"),
            include("root"),
        ],
        "single_command": [
            include("escape_fexpr"),
            (r"\n", Whitespace, "#pop"),
            (r"[^\n\$\\]+", String),
            (r"[\$\\]", String),
        ],
        "multi_command": [
            include("escape_fexpr"),
            (r"\n", Whitespace),
            (r"\*/", Punctuation, "#pop"),
            (r"[^\n\$\\\*]+", String),
            (r"[\$\\\*]", String),
        ],
        "string": [
            include("escape_fexpr"),
            (r'"', String.Double, "#pop"),
            (r"%%", String.Escape),
            (r"%%(\d|\{(\d+|%s)\})" % _identifier, String.Interpol),
            (r'[^"\n\\%\$]+', String.Double),
            (r"[\\%\$]", String.Double),
            default("#pop"),
        ],
        "escape_fexpr": [
            (r"\\#\(", String.Escape, "font_escape"),
            (
                r'\\([\\n#$]|u[a-fA-F0-9]{4}|'
                r"U[a-fA-F0-9]{8}|x[a-fA-F0-9]{2})",
                String.Escape,
            ),
            (r"\$\{", String.Interpol, "formatted_expr"),
        ],
        "font_escape": [
            (r"\)", String.Escape, "#pop"),
            (r",", Punctuation),
            (r"\s+", Whitespace),
            (
                words(
                    (
                        'reset', 'bold', 'italic', 'obfuscated',
                        'black', 'dark_blue', 'dark_green', 'dark_aqua',
                        'dark_red', 'dark_purple', 'gold', 'gray', 'dark_gray',
                        'blue', 'green', 'aqua', 'red', 'light_purple',
                        'yellow', 'white', 'minecoin_gold',
                        'material_quartz', 'material_iron',
                        'material_netherite', 'material_redstone',
                        'material_copper', 'material_gold',
                        'material_emerald', 'material_diamond',
                        'material_lapis', 'material_amethyst'
                    ),
                    suffix=r"\b"
                ),
                Name.Builtin.Pseudo
            ),
            (r"\w+", Name)
        ]
    }
